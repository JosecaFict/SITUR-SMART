from django.db import DatabaseError, connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.brevo import is_configured as brevo_is_configured
from apps.catalog.geocoding import is_configured as geocoding_is_configured
from apps.media.services import CloudinaryService
from apps.notifications.push import is_configured as push_is_configured


class HealthView(APIView):
    permission_classes = (AllowAny,)

    @staticmethod
    def database_is_available() -> bool:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            return False
        return True

    @staticmethod
    def integrations_status() -> dict[str, bool]:
        """Indica que integraciones externas tienen credenciales cargadas.

        Solo booleanos: este endpoint es publico y nunca debe exponer una
        credencial ni parte de ella. Verifica presencia, no validez: una API key
        vencida o mal copiada igual aparece como ``True``.
        """
        return {
            "cloudinary": CloudinaryService.is_configured(),
            "brevo": brevo_is_configured(),
            "openrouteservice": geocoding_is_configured(),
            "firebase": push_is_configured(),
        }

    @extend_schema(
        responses=inline_serializer(
            name="HealthResponse",
            fields={
                "status": serializers.CharField(),
                "database": serializers.CharField(),
                "integraciones": serializers.DictField(child=serializers.BooleanField()),
            },
        )
    )
    def get(self, request):
        database = "ok" if self.database_is_available() else "error"
        # Una integracion sin credenciales no degrada el estado: Railway usa este
        # endpoint para decidir si el contenedor esta sano y lo reiniciaria en vano.
        status_code = 200 if database == "ok" else 503
        return Response(
            {
                "status": "ok" if status_code == 200 else "degraded",
                "database": database,
                "integraciones": self.integrations_status(),
            },
            status=status_code,
        )


class ApiRootView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        responses=inline_serializer(
            name="ApiRootResponse",
            fields={
                "name": serializers.CharField(),
                "version": serializers.CharField(),
                "health": serializers.CharField(),
                "docs": serializers.CharField(),
                "schema": serializers.CharField(),
            },
        )
    )
    def get(self, request):
        return Response(
            {
                "name": "SITUR-SMART API",
                "version": "v1",
                "health": request.build_absolute_uri("/api/v1/health/"),
                "docs": request.build_absolute_uri("/api/docs/"),
                "schema": request.build_absolute_uri("/api/schema/"),
            }
        )
