from rest_framework import serializers


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
    verification_type = serializers.CharField(
        max_length=255, help_text="e.g., smile, move_head_left, move_head_right"
    )
    file = serializers.FileField()


class VerifyNomineeLivenessVideoInputSerializer(serializers.Serializer):
    nominee_pension_id = serializers.CharField(max_length=255)
    verification_type = serializers.CharField(
        max_length=255, help_text="e.g., smile, move_head_left, move_head_right"
    )
    file = serializers.FileField()


class MarkDeceasedInputSerializer(serializers.Serializer):
    pension_id = serializers.CharField(max_length=255)
    is_deceased = serializers.BooleanField()


class EditNomineeInputSerializer(serializers.Serializer):
    nominee_pension_id = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    relation = serializers.CharField(max_length=100, required=False, allow_blank=True)
    file = serializers.FileField(required=False)


class DeleteNomineeInputSerializer(serializers.Serializer):
    nominee_id = serializers.CharField(max_length=255)

