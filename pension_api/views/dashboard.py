from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema
from rest_framework import generics, status

from pension_api.models import User, Verification
from pension_api.serializers import DashboardResponseSerializer, UserSerializer

class LatestUsersView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return User.objects.all().order_by("-created_at")[:5]

    @extend_schema(
        summary="Get latest 5 users",
        description="Returns the 5 most recently registered users sorted by creation date.",
        tags=["Admin Dashboard"],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class DashboardDataView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Dashboard statistics",
        description="Aggregated enrollment and verification metrics for admin dashboard cards.",
        responses=DashboardResponseSerializer,
        tags=["Admin Dashboard"],
    )
    def get(self, request, *args, **kwargs):
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        total_enrollments = User.objects.count()
        today_enrollments = User.objects.filter(created_at__date=today).count()
        yesterday_enrollments = User.objects.filter(created_at__date=yesterday).count()

        enrollment_percentage = (
            ((today_enrollments - yesterday_enrollments) / yesterday_enrollments) * 100
            if yesterday_enrollments > 0
            else 0
        )

        total_verifications = Verification.objects.count()
        today_verifications = Verification.objects.filter(created_at__date=today).count()
        yesterday_verifications = Verification.objects.filter(created_at__date=yesterday).count()

        verification_percentage = (
            ((today_verifications - yesterday_verifications) / yesterday_verifications) * 100
            if yesterday_verifications > 0
            else 0
        )

        total_failed_verifications = Verification.objects.filter(status="failure").count()
        today_failed = Verification.objects.filter(created_at__date=today, status="failure").count()
        yesterday_failed = Verification.objects.filter(created_at__date=yesterday, status="failure").count()

        failed_percentage = (
            ((today_failed - yesterday_failed) / yesterday_failed) * 100 if yesterday_failed > 0 else 0
        )

        return Response(
            {
                "total_enrollments": total_enrollments,
                "percentage_change_in_enrollments": round(enrollment_percentage, 2),
                "total_verifications": total_verifications,
                "percentage_change_in_verifications": round(verification_percentage, 2),
                "total_failed_verifications": total_failed_verifications,
                "percentage_change_in_failed_verifications": round(failed_percentage, 2),
            },
            status=status.HTTP_200_OK,
        )

