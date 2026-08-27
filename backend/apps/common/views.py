from django.db import DatabaseError, connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


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

    @extend_schema(
        responses=inline_serializer(
            name="HealthResponse",
            fields={
                "status": serializers.CharField(),
                "database": serializers.CharField(),
            },
        )
    )
    def get(self, request):
        database = "ok" if self.database_is_available() else "error"
        status_code = 200 if database == "ok" else 503
        return Response({"status": "ok" if status_code == 200 else "degraded", "database": database}, status=status_code)


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
