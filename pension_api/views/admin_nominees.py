import os

from django.db import transaction
from django.db.models import Q

from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

from pension_api.models import Nominee, NomineeFaceEncoding, User
from pension_api.serializers import (
    AdminNomineeCreateUpdateSerializer,
    NomineeResponseSerializer,
    ParentNomineeListResponseSerializer,
    ParentUserSummarySerializer,
)
from pension_api.services.face_service import get_face_embedding, validate_image_quality
from pension_api.services.utils import process_uploaded_image


class AdminNomineeListCreateView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = NomineeResponseSerializer

    def get_queryset(self):
        qs = Nominee.objects.select_related("user").all().order_by("-created_at")
        q = self.request.query_params.get("q")
        pension_id = self.request.query_params.get("pension_id")
        is_active = self.request.query_params.get("is_active")

        if q:
            qs = qs.filter(Q(nominee_pension_id__icontains=q) | Q(name__icontains=q))
        if pension_id:
            qs = qs.filter(user__pension_id=pension_id)
        if is_active in {"true", "false"}:
            qs = qs.filter(is_active=(is_active == "true"))
        return qs

    @extend_schema(
        summary="List nominees (admin)",
        description="Get paginated nominees. Supports filtering by search text, parent pension ID, and active status.",
        tags=["Admin Nominees"],
        parameters=[
            OpenApiParameter(name="q", description="Search nominee pension ID or nominee name", required=False, type=str),
            OpenApiParameter(name="pension_id", description="Filter by parent pensioner ID", required=False, type=str),
            OpenApiParameter(name="is_active", description="Filter active nominees: true/false", required=False, type=str),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Create nominee (admin)",
        description="Create a nominee for a parent pensioner using pension_id. Optionally include face image file.",
        tags=["Admin Nominees"],
    )
    def post(self, request, *args, **kwargs):
        serializer = AdminNomineeCreateUpdateSerializer(data=request.data, partial=False)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        pension_id = validated.get("pension_id")
        if not pension_id:
            return Response({"detail": "pension_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(pension_id=pension_id).first()
        if not user:
            return Response({"detail": "Pensioner not found"}, status=status.HTTP_404_NOT_FOUND)

        nominee_pension_id = validated["nominee_pension_id"]
        name = validated.get("name") or ""
        relation = validated.get("relation") or ""
        uploaded_file = validated.get("file")

        if Nominee.objects.filter(nominee_pension_id=nominee_pension_id).exists():
            return Response({"detail": "Nominee with this nominee_pension_id already exists"}, status=status.HTTP_409_CONFLICT)

        tmp_path = None
        try:
            with transaction.atomic():
                nominee = Nominee.objects.create(
                    user=user,
                    nominee_pension_id=nominee_pension_id,
                    name=name,
                    relation=relation,
                    is_active=validated.get("is_active", True),
                )

                if uploaded_file is not None:
                    tmp_path = process_uploaded_image(uploaded_file)
                    is_valid, msg = validate_image_quality(tmp_path)
                    if not is_valid:
                        raise ValueError(f"Image quality check failed: {msg}")
                    embedding = get_face_embedding(tmp_path, require_single=True)
                    if embedding is None:
                        raise ValueError("No face detected in the image")
                    NomineeFaceEncoding.objects.create(nominee=nominee, embedding=embedding)

        except ValueError as ve:
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        return Response(NomineeResponseSerializer(nominee).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(responses=NomineeResponseSerializer),
    patch=extend_schema(request=AdminNomineeCreateUpdateSerializer, responses=NomineeResponseSerializer),
    put=extend_schema(request=AdminNomineeCreateUpdateSerializer, responses=NomineeResponseSerializer),
    delete=extend_schema(responses={204: None}),
)
class AdminNomineeDetailView(APIView):
    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @extend_schema(summary="Get nominee by nominee ID", tags=["Admin Nominees"])
    def get(self, request, nominee_pension_id: str, *args, **kwargs):
        nominee = Nominee.objects.filter(nominee_pension_id=nominee_pension_id).first()
        if not nominee:
            return Response({"detail": "Nominee not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(NomineeResponseSerializer(nominee).data, status=status.HTTP_200_OK)

    @extend_schema(summary="Partially update nominee", tags=["Admin Nominees"])
    def patch(self, request, nominee_pension_id: str, *args, **kwargs):
        return self._update(request, nominee_pension_id=nominee_pension_id, partial=True)

    @extend_schema(summary="Replace nominee data", tags=["Admin Nominees"])
    def put(self, request, nominee_pension_id: str, *args, **kwargs):
        return self._update(request, nominee_pension_id=nominee_pension_id, partial=False)

    @extend_schema(summary="Delete nominee", tags=["Admin Nominees"])
    def delete(self, request, nominee_pension_id: str, *args, **kwargs):
        nominee = Nominee.objects.filter(nominee_pension_id=nominee_pension_id).first()
        if not nominee:
            return Response({"detail": "Nominee not found"}, status=status.HTTP_404_NOT_FOUND)
        nominee.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _update(self, request, nominee_pension_id: str, partial: bool):
        nominee = Nominee.objects.filter(nominee_pension_id=nominee_pension_id).select_related("user").first()
        if not nominee:
            return Response({"detail": "Nominee not found"}, status=status.HTTP_404_NOT_FOUND)

        payload = request.data.copy()
        if "nominee_pension_id" not in payload:
            payload["nominee_pension_id"] = nominee_pension_id

        serializer = AdminNomineeCreateUpdateSerializer(data=payload, partial=partial)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        uploaded_file = validated.get("file")
        tmp_path = None

        try:
            with transaction.atomic():
                if "pension_id" in validated:
                    user = User.objects.filter(pension_id=validated["pension_id"]).first()
                    if not user:
                        return Response({"detail": "Pensioner not found"}, status=status.HTTP_404_NOT_FOUND)
                    nominee.user = user

                if "nominee_pension_id" in validated and validated["nominee_pension_id"] != nominee_pension_id:
                    if Nominee.objects.filter(nominee_pension_id=validated["nominee_pension_id"]).exists():
                        return Response(
                            {"detail": "Nominee with this nominee_pension_id already exists"},
                            status=status.HTTP_409_CONFLICT,
                        )
                    nominee.nominee_pension_id = validated["nominee_pension_id"]

                if "name" in validated:
                    nominee.name = validated["name"]
                if "relation" in validated:
                    nominee.relation = validated["relation"]
                if "is_active" in validated:
                    nominee.is_active = validated["is_active"]

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
                        return Response({"detail": "No face detected in the image"}, status=status.HTTP_400_BAD_REQUEST)
                    nominee.face_encodings.all().delete()
                    NomineeFaceEncoding.objects.create(nominee=nominee, embedding=embedding)

                nominee.save()

        except ValueError as ve:
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        return Response(NomineeResponseSerializer(nominee).data, status=status.HTTP_200_OK)


class AdminUserNomineeListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = NomineeResponseSerializer

    def get_queryset(self):
        pension_id = self.kwargs["pension_id"]
        return Nominee.objects.filter(user__pension_id=pension_id).order_by("-created_at")


class ParentNomineeListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Get nominees by parent pension ID",
        description="Returns the parent pensioner details and the full nominee list registered under that parent.",
        responses=ParentNomineeListResponseSerializer,
        tags=["Nominee"],
    )
    def get(self, request, pension_id: str, *args, **kwargs):
        parent = User.objects.filter(pension_id=pension_id).first()
        if not parent:
            return Response({"detail": "Parent pensioner not found"}, status=status.HTTP_404_NOT_FOUND)

        nominees = Nominee.objects.filter(user__pension_id=pension_id).order_by("-created_at")
        data = {
            "parent": ParentUserSummarySerializer(parent).data,
            "nominees": NomineeResponseSerializer(nominees, many=True).data,
        }
        return Response(data, status=status.HTTP_200_OK)


class AdminNomineeDetailByParentAndIdView(APIView):
    """
    Compatibility endpoint for clients sending:
    /api-admin/nominees/{pension_id}/{nominee_id}/
    """

    permission_classes = [AllowAny]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def _get_nominee(self, pension_id: str, nominee_id: str):
        return Nominee.objects.filter(user__pension_id=pension_id, id=nominee_id).select_related("user").first()

    def get(self, request, pension_id: str, nominee_id: str, *args, **kwargs):
        nominee = self._get_nominee(pension_id, nominee_id)
        if not nominee:
            return Response({"detail": "Nominee not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(NomineeResponseSerializer(nominee).data, status=status.HTTP_200_OK)

    def patch(self, request, pension_id: str, nominee_id: str, *args, **kwargs):
        nominee = self._get_nominee(pension_id, nominee_id)
        if not nominee:
            return Response({"detail": "Nominee not found"}, status=status.HTTP_404_NOT_FOUND)
        return AdminNomineeDetailView()._update(
            request, nominee_pension_id=nominee.nominee_pension_id, partial=True
        )

    def put(self, request, pension_id: str, nominee_id: str, *args, **kwargs):
        nominee = self._get_nominee(pension_id, nominee_id)
        if not nominee:
            return Response({"detail": "Nominee not found"}, status=status.HTTP_404_NOT_FOUND)
        return AdminNomineeDetailView()._update(
            request, nominee_pension_id=nominee.nominee_pension_id, partial=False
        )

    def delete(self, request, pension_id: str, nominee_id: str, *args, **kwargs):
        nominee = self._get_nominee(pension_id, nominee_id)
        if not nominee:
            return Response({"detail": "Nominee not found"}, status=status.HTTP_404_NOT_FOUND)
        nominee.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

