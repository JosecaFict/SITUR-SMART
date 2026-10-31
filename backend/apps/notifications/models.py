from django.conf import settings
from django.db import models


class Notification(models.Model):
    """Aviso al usuario dentro de la app."""

    class Kind(models.TextChoices):
        BOOKING_CONFIRMED = "RESERVA_CONFIRMADA", "Reserva confirmada"
        BOOKING_EXPIRED = "RESERVA_VENCIDA", "Reserva vencida"
        BOOKING_CANCELLED = "RESERVA_CANCELADA", "Reserva cancelada"
        PAYMENT_ISSUE = "PAGO_REVISION", "Pago en revisión"
        REFUND_COMPLETED = "REEMBOLSO_COMPLETADO", "Reembolso completado"
        REFUND_FAILED = "REEMBOLSO_FALLIDO", "Reembolso fallido"
        BOOKING_REMINDER_24H = "RECORDATORIO_24H", "Recordatorio 24 horas antes"
        BOOKING_REMINDER_2H = "RECORDATORIO_2H", "Recordatorio 2 horas antes"

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


class PushDevice(models.Model):
    """Celular con la app instalada que recibe los avisos por Firebase."""

    class Platform(models.TextChoices):
        ANDROID = "ANDROID", "Android"
        IOS = "IOS", "iOS"

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column="id_usuario",
        on_delete=models.CASCADE,
        related_name="push_devices",
    )
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(db_column="plataforma", max_length=20, default=Platform.ANDROID)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="actualizado_en", auto_now=True)

    class Meta:
        managed = False
        db_table = "dispositivo_push"


class BookingReminderDelivery(models.Model):
    """Marca idempotente de cada recordatorio programado de una reserva."""

    id = models.BigAutoField(primary_key=True)
    booking = models.ForeignKey(
        "bookings.Booking",
        db_column="id_reserva",
        on_delete=models.CASCADE,
        related_name="reminder_deliveries",
    )
    kind = models.CharField(db_column="tipo", max_length=40)
    sent_at = models.DateTimeField(db_column="enviado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "recordatorio_reserva_enviado"
        constraints = [  # noqa: RUF012 - configuración declarativa de Django
            models.UniqueConstraint(
                fields=("booking", "kind"), name="uq_recordatorio_reserva_tipo"
            )
        ]
