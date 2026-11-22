import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


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
        WEB = "WEB", "Navegador"

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


class Communication(models.Model):
    """Publicación interna u operativa; audiencia congelada al publicar."""

    class Kind(models.TextChoices):
        INTERNAL = "INTERNA", "Interna"
        OPERATIONAL = "OPERATIVA", "Operativa"
        PROMOTIONAL = "PROMOCIONAL", "Promocional"

    class State(models.TextChoices):
        DRAFT = "BORRADOR", "Borrador"
        PUBLISHED = "PUBLICADA", "Publicada"
        SCHEDULED = "PROGRAMADA", "Programada"
        CANCELLED = "CANCELADA", "Cancelada"
        EXPIRED = "VENCIDA", "Vencida"
        REVIEW = "REVISION", "Requiere revisión"

    tenant = models.ForeignKey("tenancy.Tenant", null=True, on_delete=models.PROTECT)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    title = models.CharField(max_length=150)
    message = models.TextField()
    kind = models.CharField(max_length=12, choices=Kind.choices)
    state = models.CharField(max_length=12, choices=State.choices, default=State.DRAFT)
    audience = models.JSONField(default=dict)
    booking = models.ForeignKey("bookings.Booking", null=True, on_delete=models.PROTECT)
    sender_name = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True)
    scheduled_at = models.DateTimeField(null=True)
    expires_at = models.DateTimeField(null=True)
    promotion = models.ForeignKey("promotions.Promotion", null=True, on_delete=models.PROTECT)
    dispatch_error = models.CharField(max_length=200, blank=True)
    email_enabled = models.BooleanField(default=True)

    class Meta:
        db_table = "comunicacion"
        ordering = ("-created_at", "-id")
        indexes = (models.Index(fields=("state", "scheduled_at"), name="idx_comunicacion_programada"),)


class CommunicationDelivery(models.Model):
    communication = models.ForeignKey(Communication, on_delete=models.CASCADE, related_name="deliveries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notification = models.OneToOneField(Notification, null=True, on_delete=models.SET_NULL)
    push_status = models.CharField(max_length=20, default="PENDIENTE")
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    locked_until = models.DateTimeField(null=True)
    last_error = models.CharField(max_length=200, blank=True)
    accepted_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "comunicacion_destinatario"
        constraints = (models.UniqueConstraint(fields=("communication", "user"), name="uq_comunicacion_usuario"),)
        indexes = (models.Index(fields=("push_status", "next_attempt_at"), name="idx_comunicacion_pendiente"),)


class PushAttempt(models.Model):
    delivery = models.ForeignKey(CommunicationDelivery, on_delete=models.CASCADE, related_name="push_attempts")
    device = models.ForeignKey(PushDevice, null=True, on_delete=models.SET_NULL)
    token = models.TextField()
    status = models.CharField(max_length=20, default="PENDIENTE")
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=200, blank=True)
    next_attempt_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "comunicacion_push_intento"
        constraints = (models.UniqueConstraint(fields=("delivery", "token"), name="uq_comunicacion_push_token"),)


class CommunicationPreference(models.Model):
    """Consentimiento publicitario por remitente; ausente significa no aceptado."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    tenant = models.ForeignKey("tenancy.Tenant", null=True, on_delete=models.CASCADE)
    promotions_enabled = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "comunicacion_preferencia"
        constraints = (
            models.UniqueConstraint(fields=("user", "tenant"), condition=models.Q(tenant__isnull=False),
                                    name="uq_preferencia_usuario_empresa"),
            models.UniqueConstraint(fields=("user",), condition=models.Q(tenant__isnull=True),
                                    name="uq_preferencia_usuario_plataforma"),
        )


class CommunicationEmail(models.Model):
    """Un correo por destinatario, independiente del estado de sus dispositivos."""

    delivery = models.OneToOneField(CommunicationDelivery, on_delete=models.CASCADE, related_name="email_delivery")
    recipient_email = models.EmailField(max_length=255)
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, default="PENDIENTE")
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    locked_until = models.DateTimeField(null=True)
    last_error = models.CharField(max_length=100, blank=True)
    provider_id = models.CharField(max_length=255, blank=True)
    accepted_at = models.DateTimeField(null=True)
    first_attempt_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "comunicacion_correo"
        indexes = (models.Index(fields=("status", "next_attempt_at"), name="idx_comunicacion_correo_cola"),)
