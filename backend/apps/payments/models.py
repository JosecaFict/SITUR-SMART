from typing import ClassVar

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


class Refund(models.Model):
    """Devolucion total o parcial de un pago aprobado."""

    class State(models.TextChoices):
        REQUESTED = "SOLICITADO", "Solicitado"
        PROCESSING = "PROCESANDO", "Procesando"
        COMPLETED = "COMPLETADO", "Completado"
        FAILED = "FALLIDO", "Fallido"
        CANCELLED = "CANCELADO", "Cancelado"

    id = models.BigAutoField(primary_key=True)
    payment = models.ForeignKey(
        Payment, db_column="id_pago", on_delete=models.DO_NOTHING, related_name="refunds"
    )
    cancellation = models.ForeignKey(
        "bookings.Cancellation",
        db_column="id_cancelacion",
        on_delete=models.DO_NOTHING,
        related_name="refunds",
    )
    currency = models.ForeignKey(
        "catalog.Currency", db_column="id_moneda", on_delete=models.DO_NOTHING, related_name="+"
    )
    amount = models.DecimalField(db_column="monto", max_digits=12, decimal_places=2)
    status = models.CharField(db_column="estado", max_length=20, default=State.REQUESTED)
    reason = models.TextField(db_column="motivo", null=True)
    provider = models.CharField(db_column="proveedor", max_length=60, default="STRIPE")
    provider_reference = models.CharField(
        db_column="referencia_proveedor", max_length=150, null=True
    )
    idempotency_key = models.CharField(db_column="idempotency_key", max_length=100, unique=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column="id_solicitado_por",
        on_delete=models.DO_NOTHING,
        related_name="+",
    )
    requested_at = models.DateTimeField(db_column="solicitado_en", auto_now_add=True)
    processed_at = models.DateTimeField(db_column="procesado_en", null=True)
    failure_reason = models.TextField(db_column="motivo_fallo", null=True)

    class Meta:
        managed = False
        db_table = "reembolso"
        ordering = ("-requested_at", "-id")


class ReconciliationIssue(models.Model):
    """Diferencia persistente entre SITUR-SMART y la pasarela de pago."""

    class Kind(models.TextChoices):
        PAYMENT_MISMATCH = "PAGO_NO_COINCIDE", "Pago no coincide"
        LATE_PAYMENT = "PAGO_TARDIO", "Pago tardío"
        REFUND_MISMATCH = "REEMBOLSO_NO_COINCIDE", "Reembolso no coincide"

    id = models.BigAutoField(primary_key=True)
    resource_type = models.CharField(db_column="tipo_recurso", max_length=20)
    resource_id = models.PositiveBigIntegerField(db_column="id_recurso")
    kind = models.CharField(db_column="tipo_incidencia", max_length=40, choices=Kind.choices)
    tenant = models.ForeignKey(
        "tenancy.Tenant", db_column="id_tenant", on_delete=models.PROTECT,
        related_name="payment_reconciliation_issues"
    )
    local_status = models.CharField(db_column="estado_local", max_length=30)
    provider_status = models.CharField(db_column="estado_proveedor", max_length=30)
    details = models.JSONField(db_column="detalle", default=dict, blank=True)
    resolved = models.BooleanField(db_column="resuelta", default=False)
    detected_at = models.DateTimeField(db_column="detectada_en", auto_now_add=True)
    last_seen_at = models.DateTimeField(db_column="ultima_deteccion_en", auto_now=True)
    resolved_at = models.DateTimeField(db_column="resuelta_en", null=True, blank=True)

    class Meta:
        db_table = "incidencia_conciliacion_pago"
        ordering = ("resolved", "-last_seen_at", "-id")
        constraints: ClassVar[list] = [
            models.UniqueConstraint(
                fields=("resource_type", "resource_id", "kind"),
                name="uq_incidencia_conciliacion_recurso",
            )
        ]
        indexes: ClassVar[list] = [
            models.Index(
                fields=("resolved", "-last_seen_at"),
                name="idx_conciliacion_abierta",
            )
        ]
