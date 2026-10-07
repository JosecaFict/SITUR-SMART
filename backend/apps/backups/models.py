from typing import ClassVar

from django.conf import settings
from django.db import models


class BackupSchedule(models.Model):
    """Cada cuanto se respalda solo. Hay una unica fila (id = 1)."""

    class Frequency(models.TextChoices):
        OFF = "DESACTIVADA", "Desactivada"
        EVERY_3_DAYS = "CADA_3_DIAS", "Cada 3 días"
        WEEKLY = "SEMANAL", "Semanal"

    DAYS: ClassVar[dict[str, int]] = {Frequency.EVERY_3_DAYS: 3, Frequency.WEEKLY: 7}

    id = models.SmallIntegerField(primary_key=True, default=1)
    frequency = models.CharField(db_column="frecuencia", max_length=20, default=Frequency.WEEKLY)
    last_run = models.DateTimeField(db_column="ultima_ejecucion", null=True)
    updated_at = models.DateTimeField(db_column="actualizado_en", auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column="id_actualizado_por",
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )

    class Meta:
        managed = False
        db_table = "programacion_respaldo"


class StoredBackup(models.Model):
    """Copia guardada fuera de Railway. El archivo vive en el almacen, no aqui."""

    class Origin(models.TextChoices):
        SCHEDULED = "PROGRAMADA", "Programada"
        ON_DEMAND = "A_PEDIDO", "A pedido"

    id = models.BigAutoField(primary_key=True)
    filename = models.CharField(db_column="archivo", max_length=120)
    storage_id = models.CharField(db_column="id_almacen", max_length=255, unique=True)
    size = models.BigIntegerField(db_column="tamano_bytes")
    sha256 = models.CharField(max_length=64)
    origin = models.CharField(db_column="origen", max_length=20)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column="id_solicitada_por",
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "copia_seguridad"
        ordering = ("-created_at", "-id")
