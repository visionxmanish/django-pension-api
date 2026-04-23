from django.conf import settings
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from pension_api.serializers import HealthResponseSerializer, MetaResponseSerializer


class HealthView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Health check",
        description="Simple health endpoint for uptime checks.",
        responses=HealthResponseSerializer,
        tags=["System"],
    )
    def get(self, request, *args, **kwargs):
        return Response({"status": "ok", "time": timezone.now().isoformat()}, status=status.HTTP_200_OK)


class MetaView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="API metadata",
        description="Returns environment and discoverability metadata such as schema/docs paths.",
        responses=MetaResponseSerializer,
        tags=["System"],
    )
    def get(self, request, *args, **kwargs):
        return Response(
            {
                "debug": bool(getattr(settings, "DEBUG", False)),
                "timezone": str(getattr(settings, "TIME_ZONE", "")),
                "api_schema": "/api/schema/",
                "docs": "/docs/",
            },
            status=status.HTTP_200_OK,
        )

