from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.db.models import Prefetch, Q, QuerySet, Sum
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit.services import record_audit
from apps.bookings import services as booking_services
from apps.bookings.models import Booking, BookingDetail, BookingState, InventoryLock
from apps.rbac.services import require_permission, require_tenant_access

from .models import Payment, Refund


def _local_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.get_current_timezone())


def parse_date(params, key: str) -> date | None:
    raw = params.get(key)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError({key: "Usa el formato AAAA-MM-DD."}) from exc


def base_queryset() -> QuerySet[Payment]:
    return (
        Payment.objects.select_related(
            "booking__tenant", "booking__order__customer__user", "currency"
        )
        .prefetch_related(
            Prefetch("refunds", queryset=Refund.objects.order_by("requested_at", "id")),
            Prefetch(
                "booking__details",
                queryset=BookingDetail.objects.select_related(
                    "slot__product__product_type"
                ).order_by("id"),
            ),
        )
    )


def apply_filters(queryset: QuerySet[Payment], params) -> QuerySet[Payment]:
    if since := parse_date(params, "desde"):
        queryset = queryset.filter(created_at__gte=_local_start(since))
    if until := parse_date(params, "hasta"):
        queryset = queryset.filter(created_at__lt=_local_start(until + timedelta(days=1)))
    if status := params.get("estado", "").strip():
        queryset = queryset.filter(status=status)
    if method := params.get("metodo", "").strip():
        queryset = queryset.filter(method=method)
    if search := params.get("buscar", "").strip():
        queryset = queryset.filter(
            Q(booking__code__icontains=search)
            | Q(booking__order__customer__user__email__icontains=search)
            | Q(booking__order__customer__user__first_names__icontains=search)
            | Q(booking__order__customer__user__last_names__icontains=search)
        )
    return queryset.order_by("-created_at", "-id")


def customer_payments(*, user, params) -> QuerySet[Payment]:
    return apply_filters(base_queryset().filter(booking__order__customer_id=user.id), params)


def customer_payment(*, user, payment_id: int) -> Payment:
    payment = base_queryset().filter(id=payment_id, booking__order__customer_id=user.id).first()
    if payment is None:
        raise NotFound("Pago no encontrado.")
    return payment


def company_payments(*, actor, tenant_id: int, params) -> QuerySet[Payment]:
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "RESERVAS_LEER", tenant_id)
    return apply_filters(base_queryset().filter(booking__tenant_id=tenant_id), params)


def company_summary(*, actor, tenant_id: int, params) -> list[dict]:
    queryset = company_payments(actor=actor, tenant_id=tenant_id, params=params)
    currencies = queryset.order_by().values("currency__iso_code", "currency__symbol").annotate(
        cobrado=Sum("amount", filter=Q(status=Payment.State.APPROVED)),
        pendiente=Sum("amount", filter=Q(status=Payment.State.PENDING)),
    )
    refunded = {
        row["payment__currency__iso_code"]: row["total"]
        for row in Refund.objects.filter(
            payment__in=queryset, status=Refund.State.COMPLETED
        ).values("payment__currency__iso_code").annotate(total=Sum("amount"))
    }
    return [
        {
            "moneda": row["currency__iso_code"],
            "simbolo": row["currency__symbol"],
            "cobrado": f"{row['cobrado'] or 0:.2f}",
            "pendiente": f"{row['pendiente'] or 0:.2f}",
            "reembolsado": f"{refunded.get(row['currency__iso_code'], 0):.2f}",
            "neto": f"{(row['cobrado'] or 0) - refunded.get(row['currency__iso_code'], 0):.2f}",
        }
        for row in currencies
    ]


@transaction.atomic
def register_manual_payment(
    *, actor, tenant_id: int, booking_id: int, method: str, reference: str | None,
    idempotency_key: str, request=None,
) -> Payment:
    """Confirma el importe congelado de una reserva; el cliente no decide el monto."""
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "RESERVAS_GESTIONAR", tenant_id)
    if method not in (Payment.Method.CASH, Payment.Method.QR, Payment.Method.TRANSFER):
        raise ValidationError({"metodo": "Usa EFECTIVO, QR o TRANSFERENCIA."})
    reference = (reference or "").strip()
    if method != Payment.Method.CASH and not reference:
        raise ValidationError({"referencia": "La referencia es obligatoria para QR o transferencia."})
    if not idempotency_key:
        raise ValidationError({"Idempotency-Key": "Envía una clave para evitar pagos duplicados."})
    key = f"manual:{tenant_id}:{idempotency_key}"[:100]

    existing = Payment.objects.select_related("booking").filter(idempotency_key=key).first()
    if existing:
        if existing.booking.tenant_id != tenant_id:
            raise ValidationError("La clave de idempotencia ya fue utilizada.")
        return existing

    booking = (
        Booking.objects.select_for_update()
        .select_related("order__customer", "currency")
        .filter(id=booking_id, tenant_id=tenant_id)
        .first()
    )
    if booking is None:
        raise NotFound("Reserva no encontrada.")
    if booking.status != BookingState.CREATED:
        raise ValidationError("Solo se registra manualmente una reserva pendiente de pago.")
    if booking.final_amount is None or booking.final_amount <= 0:
        raise ValidationError("La reserva no tiene un importe válido.")
    if Payment.objects.filter(booking=booking, status=Payment.State.APPROVED).exists():
        raise ValidationError("La reserva ya tiene un pago aprobado.")

    now = timezone.now()
    Payment.objects.filter(booking=booking, status=Payment.State.PENDING).update(
        status=Payment.State.VOIDED, processed_at=now
    )
    provider_reference = reference or f"EFECTIVO-{tenant_id}-{booking.id}-{idempotency_key[-12:]}"
    payment = Payment.objects.create(
        booking=booking, payer_id=booking.order.customer_id, currency=booking.currency,
        amount=booking.final_amount, method=method, status=Payment.State.APPROVED,
        provider="MANUAL", reference=provider_reference[:150], idempotency_key=key,
        processed_at=now,
    )
    InventoryLock.objects.filter(
        booking=booking, status=InventoryLock.State.ACTIVE
    ).update(status=InventoryLock.State.CONSUMED)
    booking_services._transition(
        booking, BookingState.CONFIRMED, user=actor,
        reason=f"Pago manual {method} registrado por {actor.get_full_name()}.",
    )
    record_audit(
        actor=actor, tenant_id=tenant_id, action="REGISTRAR_PAGO_MANUAL",
        entity="pago", entity_id=str(payment.id),
        new_data={
            "reserva": booking.code, "metodo": method, "monto": str(payment.amount),
            "moneda": booking.currency.iso_code, "referencia": provider_reference,
        }, request=request,
    )
    return payment
