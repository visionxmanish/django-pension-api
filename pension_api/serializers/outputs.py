from rest_framework import serializers

from pension_api.models import (
    User,
    FaceEncoding,
    Verification,
    Nominee,
    NomineeFaceEncoding,
    NomineeVerification,
)


class FaceEncodingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FaceEncoding
        fields = ["id", "embedding"]


class NomineeFaceEncodingSerializer(serializers.ModelSerializer):
    class Meta:
        model = NomineeFaceEncoding
        fields = ["id", "embedding"]


class NomineeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Nominee
        fields = ["id", "nominee_pension_id", "name", "relation", "is_active", "created_at", "updated_at"]


class UserSerializer(serializers.ModelSerializer):
    nominees = NomineeSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "pension_id",
            "name",
            "is_active",
            "is_deceased",
            "created_at",
            "updated_at",
            "nominees",
        ]


class VerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Verification
        fields = ["id", "user", "status", "created_at"]


class UserResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "pension_id", "name", "is_active", "is_deceased", "created_at", "updated_at"]


class NomineeResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Nominee
        fields = ["id", "nominee_pension_id", "name", "relation", "is_active", "created_at", "updated_at"]


class VerificationResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField()
    meet_link = serializers.CharField(required=False, allow_null=True)


class NomineeVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = NomineeVerification
        fields = ["id", "nominee", "status", "created_at"]


class ParentUserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "pension_id", "name", "is_active", "is_deceased"]


class ParentNomineeListResponseSerializer(serializers.Serializer):
    parent = ParentUserSummarySerializer()
    nominees = NomineeResponseSerializer(many=True)


class HealthResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    time = serializers.CharField()


class MetaResponseSerializer(serializers.Serializer):
    debug = serializers.BooleanField()
    timezone = serializers.CharField()
    api_schema = serializers.CharField()
    docs = serializers.CharField()


class DashboardResponseSerializer(serializers.Serializer):
    total_enrollments = serializers.IntegerField()
    percentage_change_in_enrollments = serializers.FloatField()
    total_verifications = serializers.IntegerField()
    percentage_change_in_verifications = serializers.FloatField()
    total_failed_verifications = serializers.IntegerField()
    percentage_change_in_failed_verifications = serializers.FloatField()

