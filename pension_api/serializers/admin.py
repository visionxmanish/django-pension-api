from rest_framework import serializers


class UserAdminUpdateSerializer(serializers.Serializer):
    """Used for PATCH/PUT on /api-admin/users/{pension_id}/
    All fields are optional so partial updates are supported.
    """

    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    is_deceased = serializers.BooleanField(required=False)
    file = serializers.FileField(
        required=False,
        help_text="Optional new face photo. When provided, replaces the stored face encoding.",
    )


class UserAdminCreateSerializer(serializers.Serializer):
    pension_id = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=255)
    is_active = serializers.BooleanField(required=False, default=True)
    is_deceased = serializers.BooleanField(required=False, default=False)
    file = serializers.FileField(required=False, help_text="Optional face photo for registration")


class AdminNomineeCreateUpdateSerializer(serializers.Serializer):
    pension_id = serializers.CharField(max_length=255, required=False, help_text="Pensioner's ID")
    nominee_pension_id = serializers.CharField(max_length=255, required=False)
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    relation = serializers.CharField(max_length=100, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    file = serializers.FileField(required=False)


