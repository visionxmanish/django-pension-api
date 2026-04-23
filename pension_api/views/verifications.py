from django.db.models import Q

from rest_framework import generics
from rest_framework.permissions import AllowAny

from drf_spectacular.utils import OpenApiParameter, extend_schema

from pension_api.models import NomineeVerification, Verification
from pension_api.serializers.outputs import NomineeVerificationSerializer, VerificationSerializer


class AdminVerificationListView(generics.ListAPIView):
    """
    Admin view of pensioner verifications.

    Query params:
    - pension_id
    - status (success|failure)
    - q (search pension_id)
    """

    permission_classes = [AllowAny]
    serializer_class = VerificationSerializer

    @extend_schema(
        summary="List pensioner verifications",
        description="Get paginated verification records for pension users.",
        tags=["Admin Verifications"],
        parameters=[
            OpenApiParameter(name="pension_id", description="Filter by pension ID", required=False, type=str),
            OpenApiParameter(name="status", description="success or failure", required=False, type=str),
            OpenApiParameter(name="q", description="Search pension ID or user name", required=False, type=str),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Verification.objects.select_related("user").all().order_by("-created_at")
        pension_id = self.request.query_params.get("pension_id")
        status_q = self.request.query_params.get("status")
        q = self.request.query_params.get("q")

        if pension_id:
            qs = qs.filter(user__pension_id=pension_id)
        if status_q in {"success", "failure"}:
            qs = qs.filter(status=status_q)
        if q:
            qs = qs.filter(Q(user__pension_id__icontains=q) | Q(user__name__icontains=q))
        return qs


class AdminNomineeVerificationListView(generics.ListAPIView):
    """
    Admin view of nominee verifications.

    Query params:
    - nominee_pension_id
    - pension_id (pensioner)
    - status (success|failure)
    - q (search nominee_pension_id / nominee name)
    """

    permission_classes = [AllowAny]
    serializer_class = NomineeVerificationSerializer

    @extend_schema(
        summary="List nominee verifications",
        description="Get paginated verification records for nominees.",
        tags=["Admin Verifications"],
        parameters=[
            OpenApiParameter(
                name="nominee_pension_id", description="Filter by nominee pension ID", required=False, type=str
            ),
            OpenApiParameter(name="pension_id", description="Filter by parent pension ID", required=False, type=str),
            OpenApiParameter(name="status", description="success or failure", required=False, type=str),
            OpenApiParameter(name="q", description="Search nominee ID or nominee name", required=False, type=str),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = NomineeVerification.objects.select_related("nominee", "nominee__user").all().order_by("-created_at")
        nominee_pension_id = self.request.query_params.get("nominee_pension_id")
        pension_id = self.request.query_params.get("pension_id")
        status_q = self.request.query_params.get("status")
        q = self.request.query_params.get("q")

        if nominee_pension_id:
            qs = qs.filter(nominee__nominee_pension_id=nominee_pension_id)
        if pension_id:
            qs = qs.filter(nominee__user__pension_id=pension_id)
        if status_q in {"success", "failure"}:
            qs = qs.filter(status=status_q)
        if q:
            qs = qs.filter(Q(nominee__nominee_pension_id__icontains=q) | Q(nominee__name__icontains=q))
        return qs

