import os

from django.db import transaction
from django.db.models import Q

from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

from pension_api.models import FaceEncoding, User
from pension_api.serializers import UserAdminCreateSerializer, UserAdminUpdateSerializer, UserSerializer
from pension_api.services.face_service import get_face_embedding, validate_image_quality
from pension_api.services.utils import process_uploaded_image


class UserListView(generics.ListCreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = User.objects.all().order_by("-created_at")

        q = self.request.query_params.get("q")
        is_active = self.request.query_params.get("is_active")
        is_deceased = self.request.query_params.get("is_deceased")

        if q:
            qs = qs.filter(Q(pension_id__icontains=q) | Q(name__icontains=q))
        if is_active in {"true", "false"}:
            qs = qs.filter(is_active=(is_active == "true"))
        if is_deceased in {"true", "false"}:
            qs = qs.filter(is_deceased=(is_deceased == "true"))

        return qs

    @extend_schema(
        summary="List users (admin)",
        description="Get paginated users with optional filters by search text, active status, and deceased status.",
        tags=["Admin Users"],
        parameters=[
            OpenApiParameter(name="q", description="Search by pension ID or user name", required=False, type=str),
            OpenApiParameter(name="is_active", description="Filter active users: true/false", required=False, type=str),
            OpenApiParameter(
                name="is_deceased", description="Filter deceased users: true/false", required=False, type=str
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create user (admin)",
        description="Create a new pension user. Optional face file can be uploaded during creation.",
        tags=["Admin Users"],
    )
    def post(self, request, *args, **kwargs):
        serializer = UserAdminCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        pension_id = validated["pension_id"]
        name = validated["name"]
        uploaded_file = validated.get("file")

        if User.objects.filter(pension_id=pension_id).exists():
            return Response({"detail": "User with this pension_id already exists"}, status=status.HTTP_409_CONFLICT)

        tmp_path = None
        try:
            with transaction.atomic():
                user = User.objects.create(
                    pension_id=pension_id,
                    name=name,
                    is_active=validated.get("is_active", True),
                    is_deceased=validated.get("is_deceased", False),
                )

                if uploaded_file is not None:
                    tmp_path = process_uploaded_image(uploaded_file)
                    is_valid, msg = validate_image_quality(tmp_path)
                    if not is_valid:
                        raise ValueError(f"Image quality check failed: {msg}")
                    embedding = get_face_embedding(tmp_path, require_single=True)
                    if embedding is None:
                        raise ValueError("No face detected in the image")
                    FaceEncoding.objects.create(user=user, embedding=embedding)

        except ValueError as ve:
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(responses=UserSerializer),
    patch=extend_schema(request=UserAdminUpdateSerializer, responses=UserSerializer),
    put=extend_schema(request=UserAdminUpdateSerializer, responses=UserSerializer),
    delete=extend_schema(responses={204: None}),
)
class UserDetailView(APIView):
    """
    Admin user detail/update endpoint.

    Supports PATCH/PUT with optional `file` (new face photo) which replaces stored encodings.
    """

    parser_classes = (MultiPartParser, FormParser, JSONParser)
    permission_classes = [AllowAny]

    @extend_schema(summary="Get user detail by pension ID", tags=["Admin Users"])
    def get(self, request, pension_id: str, *args, **kwargs):
        user = User.objects.filter(pension_id=pension_id).first()
        if not user:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

    @extend_schema(summary="Partially update user", tags=["Admin Users"])
    def patch(self, request, pension_id: str, *args, **kwargs):
        return self._update(request, pension_id=pension_id, partial=True)

    @extend_schema(summary="Replace user data", tags=["Admin Users"])
    def put(self, request, pension_id: str, *args, **kwargs):
        return self._update(request, pension_id=pension_id, partial=False)

    @extend_schema(summary="Delete user by pension ID", tags=["Admin Users"])
    def delete(self, request, pension_id: str, *args, **kwargs):
        user = User.objects.filter(pension_id=pension_id).first()
        if not user:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _update(self, request, pension_id: str, partial: bool):
        user = User.objects.filter(pension_id=pension_id).first()
        if not user:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserAdminUpdateSerializer(data=request.data, partial=partial)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        uploaded_file = validated.get("file")

        tmp_path = None
        try:
            with transaction.atomic():
                if "name" in validated:
                    user.name = validated["name"]
                if "is_active" in validated:
                    user.is_active = validated["is_active"]
                if "is_deceased" in validated:
                    user.is_deceased = validated["is_deceased"]

                if uploaded_file is not None:
                    tmp_path = process_uploaded_image(uploaded_file)
                    is_valid, msg = validate_image_quality(tmp_path)
                    if not is_valid:
                        return Response(
                            {"detail": f"Image quality check failed: {msg}"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    embedding = get_face_embedding(tmp_path, require_single=True)
                    if embedding is None:
                        return Response(
                            {"detail": "No face detected in the image"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    user.face_encodings.all().delete()
                    FaceEncoding.objects.create(user=user, embedding=embedding)

                user.save()

        except ValueError as ve:
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

