from django.conf import settings
from django.db import models


class Payment(models.Model):
    """Pago de una reserva (tabla ``pago`` de 001_initial_schema.sql).

    Con Stripe, ``reference`` guarda el id de la sesion de Checkout: es unico
    por proveedor, asi que el mismo aviso del webhook nunca crea dos pagos.
    """

    class State(models.TextChoices):
        PENDING = "PENDIENTE", "Pendiente"
        APPROVED = "APROBADO", "Aprobado"
        REJECTED = "RECHAZADO", "Rechazado"
        VOIDED = "ANULADO", "Anulado"

    class Method(models.TextChoices):
        QR = "QR", "QR"
        CARD = "TARJETA", "Tarjeta"
        TRANSFER = "TRANSFERENCIA", "Transferencia"
        CASH = "EFECTIVO", "Efectivo"
        OTHER = "OTRO", "Otro"

    id = models.BigAutoField(primary_key=True)
    booking = models.ForeignKey(
        "bookings.Booking", db_column="id_reserva", on_delete=models.DO_NOTHING, related_name="payments"
    )
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column="id_usuario_pagador",
        on_delete=models.DO_NOTHING,
        null=True,
        related_name="+",
    )
    currency = models.ForeignKey(
        "catalog.Currency", db_column="id_moneda", on_delete=models.DO_NOTHING, related_name="+"
    )
    amount = models.DecimalField(db_column="monto", max_digits=12, decimal_places=2)
    method = models.CharField(db_column="metodo", max_length=30)
    status = models.CharField(db_column="estado", max_length=20, default=State.PENDING)
    provider = models.CharField(db_column="proveedor", max_length=60, default="SIMULADO")
    reference = models.CharField(db_column="referencia", max_length=150, null=True)
    idempotency_key = models.CharField(db_column="idempotency_key", max_length=100, unique=True)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)
    processed_at = models.DateTimeField(db_column="procesado_en", null=True)

    class Meta:
        managed = False
        db_table = "pago"
