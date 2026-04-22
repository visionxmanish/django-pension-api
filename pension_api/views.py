import os
import tempfile
import shutil
from datetime import datetime, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny

from drf_spectacular.utils import extend_schema

from .models import User, FaceEncoding, Verification, Nominee, NomineeFaceEncoding, NomineeVerification
from .serializers import (
    UserSerializer, 
    UserResponseSerializer, 
    VerificationResponseSerializer,
    VerificationSerializer,
    RegisterInputSerializer,
    VerifyInputSerializer,
    VerifyLivenessVideoInputSerializer,
    RegisterNomineeInputSerializer,
    NomineeResponseSerializer,
    VerifyNomineeLivenessVideoInputSerializer,
    MarkDeceasedInputSerializer
)
from .services.face_service import get_face_embedding, validate_image_quality, verify_face, check_liveness
from .services.utils import generate_meet_link, process_uploaded_image
from .services.liveness_service import verify_video_liveness

class RegisterUserView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]

    @extend_schema(
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'pension_id': {'type': 'string'},
                    'name': {'type': 'string'},
                    'file': {'type': 'string', 'format': 'binary'},
                }
            },
        },
        responses=UserResponseSerializer
    )
    def post(self, request, *args, **kwargs):
        serializer = RegisterInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        pension_id = serializer.validated_data['pension_id']
        name = serializer.validated_data['name']
        file = serializer.validated_data['file']

        # Check if user already exists
        user = User.objects.filter(pension_id=pension_id).first()

        try:
            tmp_path = process_uploaded_image(file)
        except Exception as e:
            return Response({"detail": f"Invalid image format or file corrupted: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Validate Quality
            is_valid, msg = validate_image_quality(tmp_path)
            if not is_valid:
                return Response({"detail": f"Image quality check failed: {msg}"}, status=status.HTTP_400_BAD_REQUEST)

            # 2. Generate Embedding
            try:
                embedding = get_face_embedding(tmp_path, require_single=True)
            except ValueError as ve:
                return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
                
            if embedding is None:
                return Response({"detail": "No face detected in the image"}, status=status.HTTP_400_BAD_REQUEST)

            # 3. Save to DB
            if not user:
                user = User.objects.create(pension_id=pension_id, name=name)
            else:
                # Replace old encodings
                user.face_encodings.all().delete()
                user.name = name
                user.save()

            FaceEncoding.objects.create(user=user, embedding=embedding)

            serializer = UserResponseSerializer(user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

class VerifyUserView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]

    @extend_schema(
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'pension_id': {'type': 'string'},
                    'file': {'type': 'string', 'format': 'binary'},
                }
            },
        },
        responses=VerificationResponseSerializer
    )
    def post(self, request, *args, **kwargs):
        serializer = VerifyInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        pension_id = serializer.validated_data['pension_id']
        file = serializer.validated_data['file']

        # Fetch user
        user = User.objects.filter(pension_id=pension_id).first()
        if not user:
            return Response({
                "status": "failure",
                "message": "User not found",
                "meet_link": generate_meet_link()
            }, status=status.HTTP_200_OK)

        # Fetch stored embedding
        face_encoding = user.face_encodings.first()
        if not face_encoding:
            return Response({
                "status": "failure",
                "message": "No registered face data found for this user",
                "meet_link": generate_meet_link()
            }, status=status.HTTP_200_OK)
        
        stored_embedding = face_encoding.embedding

        try:
            tmp_path = process_uploaded_image(file)
        except Exception as e:
            return Response({
                "status": "failure",
                "message": f"Invalid image format or file corrupted: {str(e)}",
                "meet_link": generate_meet_link()
            }, status=status.HTTP_200_OK)

        try:
            # 1. Validate Quality
            is_valid, msg = validate_image_quality(tmp_path)
            if not is_valid:
                 return Response({
                    "status": "failure",
                    "message": f"Image quality check failed: {msg}",
                    "meet_link": generate_meet_link()
                }, status=status.HTTP_200_OK)

            # 2. Liveness Check
            is_real, liveness_msg = check_liveness(tmp_path)
            if not is_real:
                 return Response({
                    "status": "failure",
                    "message": liveness_msg,
                    "meet_link": generate_meet_link()
                }, status=status.HTTP_200_OK)

            # 3. Verify Face
            is_match, match_msg = verify_face(tmp_path, stored_embedding)
            
            # Create verification record
            verification_status = "success" if is_match else "failure"
            Verification.objects.create(user=user, status=verification_status)

            if is_match:
                return Response({
                    "status": "success",
                    "message": "Verification successful"
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "status": "failure",
                    "message": f"Verification failed: {match_msg}",
                    "meet_link": generate_meet_link()
                }, status=status.HTTP_200_OK)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

class VerifyLivenessVideoView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]

    @extend_schema(
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'pension_id': {'type': 'string'},
                    'verification_type': {'type': 'string'},
                    'file': {'type': 'string', 'format': 'binary'},
                }
            },
        },
        responses=VerificationResponseSerializer
    )
    def post(self, request, *args, **kwargs):
        serializer = VerifyLivenessVideoInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        pension_id = serializer.validated_data['pension_id']
        verification_type = serializer.validated_data['verification_type']
        file = serializer.validated_data['file']

        if not file.name.endswith(".mp4"):
            return Response({
                "status": "failure",
                "message": "File is not a video",
                "meet_link": generate_meet_link()
            }, status=status.HTTP_200_OK)

        # Fetch user
        user = User.objects.filter(pension_id=pension_id).first()
        if not user:
            return Response({
                "status": "failure",
                "message": "User not found",
                "meet_link": generate_meet_link()
            }, status=status.HTTP_200_OK)

        # Fetch stored embedding
        face_encoding = user.face_encodings.first()
        if not face_encoding:
             return Response({
                "status": "failure",
                "message": "No registered face data found for this user",
                "meet_link": generate_meet_link()
            }, status=status.HTTP_200_OK)
        
        stored_embedding = face_encoding.embedding

        # Save temp video file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
            for chunk in file.chunks():
                tmp_video.write(chunk)
            tmp_video_path = tmp_video.name

        best_frame_path = None
        try:
            # Map verification_type to required_actions
            actions_map = {
                "smile": "smile",
                "move_head_left": "turn_left",
                "move_head_right": "turn_right"
            }
            
            requested_types = [t.strip() for t in verification_type.split(",")]
            required_actions = []
            
            for rt in requested_types:
                if rt in actions_map:
                    required_actions.append(actions_map[rt])
                elif rt in ["turn_left", "turn_right", "smile"]:
                     required_actions.append(rt)
            
            if not required_actions:
                 required_actions = ["smile"] 

            # 1. Verify Liveness
            is_live, liveness_msg, best_frame_path = verify_video_liveness(
                tmp_video_path, 
                required_actions=required_actions
            )
            
            if not is_live:
                 return Response({
                    "status": "failure",
                    "message": liveness_msg,
                    "meet_link": generate_meet_link()
                }, status=status.HTTP_200_OK)

            # 2. Verify Face
            if best_frame_path:
                is_match, match_msg = verify_face(best_frame_path, stored_embedding)
                
                # Create verification record
                verification_status = "success" if is_match else "failure"
                Verification.objects.create(user=user, status=verification_status)

                if is_match:
                    return Response({
                        "status": "success",
                        "message": "Verification successful"
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        "status": "failure",
                        "message": f"Verification failed: {match_msg}",
                        "meet_link": generate_meet_link()
                    }, status=status.HTTP_200_OK)
            else:
                 return Response({
                    "status": "failure",
                    "message": "Could not extract a valid frame for face verification",
                    "meet_link": generate_meet_link()
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": "failure",
                "message": f"System error: {str(e)}",
                "meet_link": generate_meet_link()
            }, status=status.HTTP_200_OK)

        finally:
            if os.path.exists(tmp_video_path):
                os.remove(tmp_video_path)
            if best_frame_path and os.path.exists(best_frame_path):
                os.remove(best_frame_path)

class MarkUserDeceasedView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=MarkDeceasedInputSerializer,
        responses=UserResponseSerializer
    )
    def post(self, request, *args, **kwargs):
        serializer = MarkDeceasedInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        pension_id = serializer.validated_data['pension_id']
        is_deceased = serializer.validated_data['is_deceased']

        user = User.objects.filter(pension_id=pension_id).first()
        if not user:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        
        user.is_deceased = is_deceased
        user.save()

        return Response(UserResponseSerializer(user).data, status=status.HTTP_200_OK)

class RegisterNomineeView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]

    @extend_schema(
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'pension_id': {'type': 'string', 'description': 'Pensioner ID'},
                    'nominee_pension_id': {'type': 'string'},
                    'name': {'type': 'string'},
                    'relation': {'type': 'string'},
                    'file': {'type': 'string', 'format': 'binary'},
                }
            },
        },
        responses=NomineeResponseSerializer
    )
    def post(self, request, *args, **kwargs):
        serializer = RegisterNomineeInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        pension_id = serializer.validated_data['pension_id']
        nominee_pension_id = serializer.validated_data['nominee_pension_id']
        name = serializer.validated_data['name']
        relation = serializer.validated_data['relation']
        file = serializer.validated_data['file']

        # Check if pensioner exists
        user = User.objects.filter(pension_id=pension_id).first()
        if not user:
            return Response({"detail": "Pensioner not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check if nominee already exists
        nominee = Nominee.objects.filter(nominee_pension_id=nominee_pension_id).first()

        try:
            tmp_path = process_uploaded_image(file)
        except Exception as e:
            return Response({"detail": f"Invalid image format: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Validate Quality
            is_valid, msg = validate_image_quality(tmp_path)
            if not is_valid:
                return Response({"detail": f"Image quality check failed: {msg}"}, status=status.HTTP_400_BAD_REQUEST)

            # 2. Generate Embedding
            try:
                embedding = get_face_embedding(tmp_path, require_single=True)
            except ValueError as ve:
                return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
                
            if embedding is None:
                return Response({"detail": "No face detected in the image"}, status=status.HTTP_400_BAD_REQUEST)

            # 3. Save to DB
            if not nominee:
                nominee = Nominee.objects.create(
                    user=user, 
                    nominee_pension_id=nominee_pension_id, 
                    name=name,
                    relation=relation
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

class VerifyNomineeLivenessView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [AllowAny]

    @extend_schema(
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'nominee_pension_id': {'type': 'string'},
                    'verification_type': {'type': 'string'},
                    'file': {'type': 'string', 'format': 'binary'},
                }
            },
        },
        responses=VerificationResponseSerializer
    )
    def post(self, request, *args, **kwargs):
        serializer = VerifyNomineeLivenessVideoInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        nominee_pension_id = serializer.validated_data['nominee_pension_id']
        verification_type = serializer.validated_data['verification_type']
        file = serializer.validated_data['file']

        if not file.name.endswith(".mp4"):
            return Response({
                "status": "failure",
                "message": "File is not a video",
                "meet_link": generate_meet_link()
            }, status=status.HTTP_200_OK)

        # Fetch nominee
        nominee = Nominee.objects.filter(nominee_pension_id=nominee_pension_id).first()
        if not nominee:
            return Response({
                "status": "failure",
                "message": "Nominee not found",
                "meet_link": generate_meet_link()
            }, status=status.HTTP_200_OK)

        # Check if pensioner is deceased
        if not nominee.user.is_deceased:
            return Response({
                "status": "failure",
                "message": "Pensioner is still alive. Nominee verification not required.",
                "meet_link": generate_meet_link()
            }, status=status.HTTP_200_OK)

        # Fetch stored embedding
        face_encoding = nominee.face_encodings.first()
        if not face_encoding:
             return Response({
                "status": "failure",
                "message": "No registered face data found for this nominee",
                "meet_link": generate_meet_link()
            }, status=status.HTTP_200_OK)
        
        stored_embedding = face_encoding.embedding

        # Save temp video file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_video:
            for chunk in file.chunks():
                tmp_video.write(chunk)
            tmp_video_path = tmp_video.name

        best_frame_path = None
        try:
            # Map verification_type to required_actions
            actions_map = {
                "smile": "smile",
                "move_head_left": "turn_left",
                "move_head_right": "turn_right"
            }
            
            requested_types = [t.strip() for t in verification_type.split(",")]
            required_actions = []
            
            for rt in requested_types:
                if rt in actions_map:
                    required_actions.append(actions_map[rt])
                elif rt in ["turn_left", "turn_right", "smile"]:
                     required_actions.append(rt)
            
            if not required_actions:
                 required_actions = ["smile"] 

            # 1. Verify Liveness
            is_live, liveness_msg, best_frame_path = verify_video_liveness(
                tmp_video_path, 
                required_actions=required_actions
            )
            
            if not is_live:
                 return Response({
                    "status": "failure",
                    "message": liveness_msg,
                    "meet_link": generate_meet_link()
                }, status=status.HTTP_200_OK)

            # 2. Verify Face
            if best_frame_path:
                is_match, match_msg = verify_face(best_frame_path, stored_embedding)
                
                # Create verification record
                verification_status = "success" if is_match else "failure"
                NomineeVerification.objects.create(nominee=nominee, status=verification_status)

                if is_match:
                    return Response({
                        "status": "success",
                        "message": "Nominee verification successful"
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        "status": "failure",
                        "message": f"Nominee verification failed: {match_msg}",
                        "meet_link": generate_meet_link()
                    }, status=status.HTTP_200_OK)
            else:
                 return Response({
                    "status": "failure",
                    "message": "Could not extract a valid frame for face verification",
                    "meet_link": generate_meet_link()
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": "failure",
                "message": f"System error: {str(e)}",
                "meet_link": generate_meet_link()
            }, status=status.HTTP_200_OK)

        finally:
            if os.path.exists(tmp_video_path):
                os.remove(tmp_video_path)
            if best_frame_path and os.path.exists(best_frame_path):
                os.remove(best_frame_path)

class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

class UserDetailView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = 'pension_id'
    permission_classes = [AllowAny]

class DashboardDataView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, *args, **kwargs):
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        # --- ENROLLMENTS ---
        total_enrollments = User.objects.count()
        today_enrollments = User.objects.filter(created_at__date=today).count()
        yesterday_enrollments = User.objects.filter(created_at__date=yesterday).count()

        enrollment_percentage = (
            ((today_enrollments - yesterday_enrollments) / yesterday_enrollments) * 100
            if yesterday_enrollments > 0 else 0
        )

        # --- VERIFICATIONS ---
        total_verifications = Verification.objects.count()
        today_verifications = Verification.objects.filter(created_at__date=today).count()
        yesterday_verifications = Verification.objects.filter(created_at__date=yesterday).count()

        verification_percentage = (
            ((today_verifications - yesterday_verifications) / yesterday_verifications) * 100
            if yesterday_verifications > 0 else 0
        )

        # --- FAILED VERIFICATIONS ---
        total_failed_verifications = Verification.objects.filter(status="failure").count()
        today_failed = Verification.objects.filter(created_at__date=today, status="failure").count()
        yesterday_failed = Verification.objects.filter(created_at__date=yesterday, status="failure").count()

        failed_percentage = (
            ((today_failed - yesterday_failed) / yesterday_failed) * 100
            if yesterday_failed > 0 else 0
        )

        return Response({
            "total_enrollments": total_enrollments,
            "percentage_change_in_enrollments": round(enrollment_percentage, 2),
            "total_verifications": total_verifications,
            "percentage_change_in_verifications": round(verification_percentage, 2),
            "total_failed_verifications": total_failed_verifications,
            "percentage_change_in_failed_verifications": round(failed_percentage, 2),
        }, status=status.HTTP_200_OK)
