from rest_framework import serializers
from .models import User, FaceEncoding, Verification, Nominee, NomineeFaceEncoding, NomineeVerification

class FaceEncodingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FaceEncoding
        fields = ['id', 'embedding']

class NomineeFaceEncodingSerializer(serializers.ModelSerializer):
    class Meta:
        model = NomineeFaceEncoding
        fields = ['id', 'embedding']

class NomineeSerializer(serializers.ModelSerializer):
    face_encodings = NomineeFaceEncodingSerializer(many=True, read_only=True)

    class Meta:
        model = Nominee
        fields = ['id', 'nominee_pension_id', 'name', 'relation', 'is_active', 'created_at', 'updated_at', 'face_encodings']

class UserSerializer(serializers.ModelSerializer):
    face_encodings = FaceEncodingSerializer(many=True, read_only=True)
    nominees = NomineeSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ['id', 'pension_id', 'name', 'is_active', 'is_deceased', 'created_at', 'updated_at', 'face_encodings', 'nominees']

class VerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Verification
        fields = ['id', 'user', 'status', 'created_at']

class UserResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'pension_id', 'name', 'is_active', 'is_deceased', 'created_at', 'updated_at']

class NomineeResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Nominee
        fields = ['id', 'nominee_pension_id', 'name', 'relation', 'is_active', 'created_at', 'updated_at']

class VerificationResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField()
    meet_link = serializers.CharField(required=False, allow_null=True)

class RegisterInputSerializer(serializers.Serializer):
    pension_id = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=255)
    file = serializers.FileField()

class RegisterNomineeInputSerializer(serializers.Serializer):
    pension_id = serializers.CharField(max_length=255, help_text="Pensioner's ID")
    nominee_pension_id = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=255)
    relation = serializers.CharField(max_length=100)
    file = serializers.FileField()

class VerifyInputSerializer(serializers.Serializer):
    pension_id = serializers.CharField(max_length=255)
    file = serializers.FileField()

class VerifyLivenessVideoInputSerializer(serializers.Serializer):
    pension_id = serializers.CharField(max_length=255)
    verification_type = serializers.CharField(max_length=255, help_text="e.g., smile, move_head_left, move_head_right")
    file = serializers.FileField()

class VerifyNomineeLivenessVideoInputSerializer(serializers.Serializer):
    nominee_pension_id = serializers.CharField(max_length=255)
    verification_type = serializers.CharField(max_length=255, help_text="e.g., smile, move_head_left, move_head_right")
    file = serializers.FileField()

class MarkDeceasedInputSerializer(serializers.Serializer):
    pension_id = serializers.CharField(max_length=255)
    is_deceased = serializers.BooleanField()
