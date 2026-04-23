import os
import tempfile

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from pension_api.models import FaceEncoding, User, Verification
from pension_api.serializers import (
    MarkDeceasedInputSerializer,
    RegisterInputSerializer,
    UserResponseSerializer,
    VerificationResponseSerializer,
    VerifyInputSerializer,
    VerifyLivenessVideoInputSerializer,
)
from pension_api.services.face_service import (
    check_liveness,
    get_face_embedding,
    validate_image_quality,
    verify_face,
)
from pension_api.services.liveness_service import verify_video_liveness
from pension_api.services.api_helpers import failure_response, parse_verification_actions
from pension_api.services.utils import process_uploaded_image


class RegisterUserView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "pension_id": {"type": "string"},
                    "name": {"type": "string"},
                    "file": {"type": "string", "format": "binary"},
                },
            },
        },
        responses=UserResponseSerializer,
    )
    def post(self, request, *args, **kwargs):
        serializer = RegisterInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        pension_id = serializer.validated_data["pension_id"]
        name = serializer.validated_data["name"]
        file = serializer.validated_data["file"]

        user = User.objects.filter(pension_id=pension_id).first()

        try:
            tmp_path = process_uploaded_image(file)
        except Exception as e:
            return Response(
                {"detail": f"Invalid image format or file corrupted: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            is_valid, msg = validate_image_quality(tmp_path)
            if not is_valid:
                return Response(
                    {"detail": f"Image quality check failed: {msg}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                embedding = get_face_embedding(tmp_path, require_single=True)
            except ValueError as ve:
                return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)

            if embedding is None:
                return Response({"detail": "No face detected in the image"}, status=status.HTTP_400_BAD_REQUEST)

            if not user:
                user = User.objects.create(pension_id=pension_id, name=name)
            else:
                user.face_encodings.all().delete()
                user.name = name
                user.save()

            FaceEncoding.objects.create(user=user, embedding=embedding)

            return Response(UserResponseSerializer(user).data, status=status.HTTP_201_CREATED)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class VerifyUserView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "pension_id": {"type": "string"},
                    "file": {"type": "string", "format": "binary"},
                },
            },
        },
        responses=VerificationResponseSerializer,
    )
    def post(self, request, *args, **kwargs):
        serializer = VerifyInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        pension_id = serializer.validated_data["pension_id"]
        file = serializer.validated_data["file"]

        user = User.objects.filter(pension_id=pension_id).first()
        if not user:
            return failure_response("User not found")

        face_encoding = user.face_encodings.first()
        if not face_encoding:
            return failure_response("No registered face data found for this user")

        stored_embedding = face_encoding.embedding

        try:
            tmp_path = process_uploaded_image(file)
        except Exception as e:
            return failure_response(f"Invalid image format or file corrupted: {str(e)}")

        try:
            is_valid, msg = validate_image_quality(tmp_path)
            if not is_valid:
                return failure_response(f"Image quality check failed: {msg}")

            is_real, liveness_msg = check_liveness(tmp_path)
            if not is_real:
                return failure_response(liveness_msg)

            is_match, match_msg = verify_face(tmp_path, stored_embedding)

            Verification.objects.create(user=user, status="success" if is_match else "failure")

            if is_match:
                return Response({"status": "success", "message": "Verification successful"}, status=status.HTTP_200_OK)
            return failure_response(f"Verification failed: {match_msg}")

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class VerifyLivenessVideoView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "pension_id": {"type": "string"},
                    "verification_type": {"type": "string"},
                    "file": {"type": "string", "format": "binary"},
                },
            },
        },
        responses=VerificationResponseSerializer,
    )
    def post(self, request, *args, **kwargs):
        serializer = VerifyLivenessVideoInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        pension_id = serializer.validated_data["pension_id"]
        verification_type = serializer.validated_data["verification_type"]
        file = serializer.validated_data["file"]

        if not file.name.endswith(".mp4"):
            return failure_response("File is not a video")

        user = User.objects.filter(pension_id=pension_id).first()
        if not user:
            return failure_response("User not found")

        face_encoding = user.face_encodings.first()
        if not face_encoding:
            return failure_response("No registered face data found for this user")

        stored_embedding = face_encoding.embedding

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
            for chunk in file.chunks():
                tmp_video.write(chunk)
            tmp_video_path = tmp_video.name

        best_frame_path = None
        try:
            required_actions = parse_verification_actions(verification_type)

            is_live, liveness_msg, best_frame_path = verify_video_liveness(
                tmp_video_path, required_actions=required_actions
            )
            if not is_live:
                return failure_response(liveness_msg)

            if not best_frame_path:
                return failure_response("Could not extract a valid frame for face verification")

            is_match, match_msg = verify_face(best_frame_path, stored_embedding)
            Verification.objects.create(user=user, status="success" if is_match else "failure")

            if is_match:
                return Response({"status": "success", "message": "Verification successful"}, status=status.HTTP_200_OK)
            return failure_response(f"Verification failed: {match_msg}")

        except Exception as e:
            return failure_response(f"System error: {str(e)}")
        finally:
            if os.path.exists(tmp_video_path):
                os.remove(tmp_video_path)
            if best_frame_path and os.path.exists(best_frame_path):
                os.remove(best_frame_path)


class MarkUserDeceasedView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=MarkDeceasedInputSerializer, responses=UserResponseSerializer, tags=["Pensioner Status"])
    def post(self, request, *args, **kwargs):
        serializer = MarkDeceasedInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        pension_id = serializer.validated_data["pension_id"]
        is_deceased = serializer.validated_data["is_deceased"]

        user = User.objects.filter(pension_id=pension_id).first()
        if not user:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        user.is_deceased = is_deceased
        user.save()

        return Response(UserResponseSerializer(user).data, status=status.HTTP_200_OK)

