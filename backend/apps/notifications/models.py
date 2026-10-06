from django.conf import settings
from django.db import models


class Notification(models.Model):
    """Aviso al usuario dentro de la app."""

    class Kind(models.TextChoices):
        BOOKING_CONFIRMED = "RESERVA_CONFIRMADA", "Reserva confirmada"
        BOOKING_EXPIRED = "RESERVA_VENCIDA", "Reserva vencida"
        BOOKING_CANCELLED = "RESERVA_CANCELADA", "Reserva cancelada"
        PAYMENT_ISSUE = "PAGO_REVISION", "Pago en revisión"

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column="id_usuario",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(db_column="tipo", max_length=40)
    title = models.CharField(db_column="titulo", max_length=150)
    message = models.TextField(db_column="mensaje")
    data = models.JSONField(db_column="datos", default=dict)
    read_at = models.DateTimeField(db_column="leida_en", null=True)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "notificacion"
        ordering = ("-created_at", "-id")
