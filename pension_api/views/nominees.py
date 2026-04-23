import os
import tempfile

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from pension_api.models import Nominee, NomineeFaceEncoding, NomineeVerification, User
from pension_api.serializers import (
    DeleteNomineeInputSerializer,
    EditNomineeInputSerializer,
    NomineeResponseSerializer,
    RegisterNomineeInputSerializer,
    VerificationResponseSerializer,
    VerifyNomineeLivenessVideoInputSerializer,
)
from pension_api.services.face_service import get_face_embedding, validate_image_quality, verify_face
from pension_api.services.api_helpers import failure_response, parse_verification_actions
from pension_api.services.liveness_service import verify_video_liveness
from pension_api.services.utils import process_uploaded_image


class RegisterNomineeView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "pension_id": {"type": "string", "description": "Pensioner ID"},
                    "nominee_pension_id": {"type": "string"},
                    "name": {"type": "string"},
                    "relation": {"type": "string"},
                    "file": {"type": "string", "format": "binary"},
                },
            },
        },
        responses=NomineeResponseSerializer,
        tags=["Nominee"],
    )
    def post(self, request, *args, **kwargs):
        serializer = RegisterNomineeInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        pension_id = serializer.validated_data["pension_id"]
        nominee_pension_id = serializer.validated_data["nominee_pension_id"]
        name = serializer.validated_data["name"]
        relation = serializer.validated_data["relation"]
        file = serializer.validated_data["file"]

        user = User.objects.filter(pension_id=pension_id).first()
        if not user:
            return Response({"detail": "Pensioner not found"}, status=status.HTTP_404_NOT_FOUND)

        nominee = Nominee.objects.filter(nominee_pension_id=nominee_pension_id).first()

        try:
            tmp_path = process_uploaded_image(file)
        except Exception as e:
            return Response({"detail": f"Invalid image format: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            is_valid, msg = validate_image_quality(tmp_path)
            if not is_valid:
                return Response({"detail": f"Image quality check failed: {msg}"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                embedding = get_face_embedding(tmp_path, require_single=True)
            except ValueError as ve:
                return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)

            if embedding is None:
                return Response({"detail": "No face detected in the image"}, status=status.HTTP_400_BAD_REQUEST)

            if not nominee:
                nominee = Nominee.objects.create(
                    user=user,
                    nominee_pension_id=nominee_pension_id,
                    name=name,
                    relation=relation,
                )
            else:
                nominee.face_encodings.all().delete()
                nominee.name = name
                nominee.relation = relation
                nominee.user = user
                nominee.save()

            NomineeFaceEncoding.objects.create(nominee=nominee, embedding=embedding)

            return Response(NomineeResponseSerializer(nominee).data, status=status.HTTP_201_CREATED)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class EditNomineeView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "nominee_pension_id": {"type": "string"},
                    "name": {"type": "string"},
                    "relation": {"type": "string"},
                    "file": {"type": "string", "format": "binary"},
                },
            },
        },
        responses=NomineeResponseSerializer,
        tags=["Nominee"],
    )
    def post(self, request, *args, **kwargs):
        serializer = EditNomineeInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        nominee_pension_id = serializer.validated_data["nominee_pension_id"]
        name = serializer.validated_data.get("name")
        relation = serializer.validated_data.get("relation")
        file = serializer.validated_data.get("file")

        nominee = Nominee.objects.filter(nominee_pension_id=nominee_pension_id).first()
        if not nominee:
            return Response({"detail": "Nominee not found"}, status=status.HTTP_404_NOT_FOUND)

        if name:
            nominee.name = name
        if relation:
            nominee.relation = relation

        tmp_path = None
        try:
            if file:
                tmp_path = process_uploaded_image(file)
                is_valid, msg = validate_image_quality(tmp_path)
                if not is_valid:
                    return Response({"detail": f"Image quality check failed: {msg}"}, status=status.HTTP_400_BAD_REQUEST)

                try:
                    embedding = get_face_embedding(tmp_path, require_single=True)
                except ValueError as ve:
                    return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)

                if embedding is None:
                    return Response({"detail": "No face detected in the image"}, status=status.HTTP_400_BAD_REQUEST)

                nominee.face_encodings.all().delete()
                NomineeFaceEncoding.objects.create(nominee=nominee, embedding=embedding)

            nominee.save()
            return Response(NomineeResponseSerializer(nominee).data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"detail": f"Error updating nominee: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)


class DeleteNomineeView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=DeleteNomineeInputSerializer,
        responses={"200": {"type": "object", "properties": {"detail": {"type": "string"}}}},
        tags=["Nominee"],
    )
    def post(self, request, *args, **kwargs):
        serializer = DeleteNomineeInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        nominee_id = serializer.validated_data["nominee_id"]
        nominee = Nominee.objects.filter(nominee_pension_id=nominee_id).first()
        if not nominee:
            return Response({"detail": "Nominee not found"}, status=status.HTTP_404_NOT_FOUND)

        nominee.delete()
        return Response({"detail": "Nominee deleted successfully"}, status=status.HTTP_200_OK)


class VerifyNomineeLivenessView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "nominee_pension_id": {"type": "string"},
                    "verification_type": {"type": "string"},
                    "file": {"type": "string", "format": "binary"},
                },
            },
        },
        responses=VerificationResponseSerializer,
        tags=["Nominee"],
    )
    def post(self, request, *args, **kwargs):
        serializer = VerifyNomineeLivenessVideoInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        nominee_pension_id = serializer.validated_data["nominee_pension_id"]
        verification_type = serializer.validated_data["verification_type"]
        file = serializer.validated_data["file"]

        if not file.name.endswith(".mp4"):
            return failure_response("File is not a video")

        nominee = Nominee.objects.filter(nominee_pension_id=nominee_pension_id).first()
        if not nominee:
            return failure_response("Nominee not found")

        if not nominee.user.is_deceased:
            return failure_response("Pensioner is still alive. Nominee verification not required.")

        face_encoding = nominee.face_encodings.first()
        if not face_encoding:
            return failure_response("No registered face data found for this nominee")

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
            NomineeVerification.objects.create(nominee=nominee, status="success" if is_match else "failure")

            if is_match:
                return Response(
                    {"status": "success", "message": "Nominee verification successful"},
                    status=status.HTTP_200_OK,
                )
            return failure_response(f"Nominee verification failed: {match_msg}")

        except Exception as e:
            return failure_response(f"System error: {str(e)}")
        finally:
            if os.path.exists(tmp_video_path):
                os.remove(tmp_video_path)
            if best_frame_path and os.path.exists(best_frame_path):
                os.remove(best_frame_path)

