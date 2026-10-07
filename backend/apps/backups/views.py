from typing import ClassVar

from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import scheduled, storage
from .models import BackupSchedule, StoredBackup
from .services import generate_backup, require_backup_management


class BackupDownloadView(APIView):
    throttle_classes: ClassVar[list[type[ScopedRateThrottle]]] = [ScopedRateThrottle]
    throttle_scope = "backup"

    def post(self, request):
        artifact = generate_backup(actor=request.user, request=request)
        response = FileResponse(
            artifact.file,
            as_attachment=True,
            filename=artifact.filename,
            content_type="application/octet-stream",
        )
        response["Content-Length"] = str(artifact.size)
        response["X-Backup-SHA256"] = artifact.sha256
        response["Cache-Control"] = "no-store"
        return response


class ScheduleSerializer(serializers.Serializer):
    frecuencia = serializers.ChoiceField(choices=BackupSchedule.Frequency.choices)


def _schedule_data(schedule: BackupSchedule) -> dict:
    upcoming = scheduled.next_run(schedule)
    return {
        "frecuencia": schedule.frequency,
        "ultima_ejecucion": schedule.last_run,
        "proxima_ejecucion": upcoming,
        "almacen_configurado": storage.is_configured(),
    }


def _backup_data(backup: StoredBackup) -> dict:
    return {
        "id": backup.id,
        "archivo": backup.filename,
        "tamano_bytes": backup.size,
        "sha256": backup.sha256,
        "origen": backup.origin,
        "creado_en": backup.created_at,
    }


class _SuperAdminOnly(APIView):
    permission_classes = (IsAuthenticated,)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_backup_management(request.user)


class BackupScheduleView(_SuperAdminOnly):
    """Cada cuanto se respalda solo: GET la consulta, PUT la cambia."""

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(_schedule_data(scheduled.get_schedule()))

    @extend_schema(request=ScheduleSerializer, responses=OpenApiTypes.OBJECT)
    def put(self, request):
        serializer = ScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        schedule = scheduled.update_schedule(
            actor=request.user, frequency=serializer.validated_data["frecuencia"], request=request
        )
        return Response(_schedule_data(schedule))


class StoredBackupListView(_SuperAdminOnly):
    """Copias guardadas (las ultimas 8). POST genera una ahora y avisa por correo."""

    throttle_classes: ClassVar[list[type[ScopedRateThrottle]]] = [ScopedRateThrottle]
    throttle_scope = "backup"

    def get_throttles(self):
        # Listar no gasta nada; solo generar una copia esta limitado.
        return super().get_throttles() if self.request.method == "POST" else []

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response([_backup_data(backup) for backup in scheduled.list_backups()])

    @extend_schema(request=None, responses={201: OpenApiTypes.OBJECT})
    def post(self, request):
        backup = scheduled.create_backup(
            origin=StoredBackup.Origin.ON_DEMAND, actor=request.user, request=request
        )
        enviados = scheduled.notify(backup=backup)
        return Response({**_backup_data(backup), "correos_enviados": enviados}, status=status.HTTP_201_CREATED)


class StoredBackupLinkView(_SuperAdminOnly):
    """Enlace firmado para bajar una copia guardada; vence en minutos."""

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request, pk):
        url = scheduled.download_link(actor=request.user, backup_id=pk, request=request)
        return Response({"url": url, "vence_en_segundos": storage.LINK_SECONDS})
