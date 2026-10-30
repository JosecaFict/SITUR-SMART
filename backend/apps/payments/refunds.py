"""Cancelacion pagada y reembolsos: una sola regla para web, movil y cron."""

from decimal import Decimal

from django.db import transaction
from django.db.models import Min, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_audit
from apps.bookings import services as bookings
from apps.bookings.models import Booking, BookingState, Cancellation, InventoryLock
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.rbac.services import require_permission, require_tenant_access

from . import gateway
from .models import Payment, Refund


def _notify(refund: Refund, *, completed: bool) -> None:
    booking = refund.payment.booking
    customer = booking.order.customer.user
    if completed:
        notify(
            user=customer,
            kind=Notification.Kind.REFUND_COMPLETED,
            title="Reembolso completado",
            message=f"Devolvimos {booking.currency.symbol} {refund.amount:.2f} de la reserva {booking.code}.",
            data={"reserva_id": booking.id, "reembolso_id": refund.id, "codigo": booking.code},
        )
    else:
        notify(
            user=customer,
            kind=Notification.Kind.REFUND_FAILED,
            title="No se pudo completar el reembolso",
            message=f"La devolución de la reserva {booking.code} requiere revisión.",
            data={"reserva_id": booking.id, "reembolso_id": refund.id, "codigo": booking.code},
        )


def _cancel_after_refund(*, refund: Refund) -> None:
    """Cancela y libera una sola vez, únicamente tras confirmar el dinero."""
    booking = Booking.objects.select_for_update().get(id=refund.payment.booking_id)
    if booking.status == BookingState.CANCELLED:
        return
    if booking.status not in bookings.OCCUPYING_STATES:
        raise ValidationError("La reserva ya no se puede cancelar.")
    InventoryLock.objects.filter(
        booking=booking,
        status__in=(InventoryLock.State.ACTIVE, InventoryLock.State.CONSUMED),
    ).update(status=InventoryLock.State.RELEASED)
    bookings._transition(
        booking,
        BookingState.CANCELLED,
        user=refund.requested_by,
        reason=f"Reembolso {refund.provider_reference or refund.id} completado.",
    )


@transaction.atomic
def complete_refund(*, refund_id: int, provider_reference: str | None = None) -> Refund:
    refund = (
        Refund.objects.select_for_update()
        .select_related("payment__booking__order__customer__user", "payment__booking__currency")
        .get(id=refund_id)
    )
    if refund.status == Refund.State.COMPLETED:
        return refund
    refund.status = Refund.State.COMPLETED
    refund.provider_reference = provider_reference or refund.provider_reference
    refund.processed_at = timezone.now()
    refund.failure_reason = None
    refund.save(
        update_fields=("status", "provider_reference", "processed_at", "failure_reason")
    )
    _cancel_after_refund(refund=refund)
    record_audit(
        actor=refund.requested_by,
        tenant_id=refund.payment.booking.tenant_id,
        action="COMPLETAR_REEMBOLSO",
        entity="reembolso",
        entity_id=str(refund.id),
        new_data={"estado": refund.status, "monto": str(refund.amount)},
    )
    record_audit(
        actor=refund.requested_by,
        tenant_id=refund.payment.booking.tenant_id,
        action="CANCELAR_RESERVA",
        entity="reserva",
        entity_id=str(refund.payment.booking_id),
        new_data={
            "reembolso_id": refund.id,
            "reembolso": str(refund.amount),
            "estado": BookingState.CANCELLED,
        },
    )
    transaction.on_commit(lambda: _notify(refund, completed=True))
    return refund


@transaction.atomic
def fail_refund(*, refund_id: int, reason: str | None = None) -> Refund:
    refund = (
        Refund.objects.select_for_update()
        .select_related("payment__booking__order__customer__user", "payment__booking__currency")
        .get(id=refund_id)
    )
    if refund.status in (Refund.State.COMPLETED, Refund.State.FAILED):
        return refund
    refund.status = Refund.State.FAILED
    refund.failure_reason = (reason or "Stripe rechazó el reembolso.")[:1000]
    refund.processed_at = timezone.now()
    refund.save(update_fields=("status", "failure_reason", "processed_at"))
    record_audit(
        actor=refund.requested_by,
        tenant_id=refund.payment.booking.tenant_id,
        action="FALLAR_REEMBOLSO",
        entity="reembolso",
        entity_id=str(refund.id),
        new_data={"estado": refund.status, "motivo": refund.failure_reason},
    )
    transaction.on_commit(lambda: _notify(refund, completed=False))
    return refund


def apply_provider_result(refund: Refund, result: gateway.RefundResult) -> Refund:
    Refund.objects.filter(id=refund.id).update(provider_reference=result.id)
    if result.succeeded:
        return complete_refund(refund_id=refund.id, provider_reference=result.id)
    if result.failed:
        return fail_refund(refund_id=refund.id, reason=result.failure_reason)
    Refund.objects.filter(id=refund.id).update(
        status=Refund.State.PROCESSING, provider_reference=result.id
    )
    refund.refresh_from_db()
    return refund


def reconcile_refund(refund: Refund) -> Refund:
    if refund.status not in (Refund.State.REQUESTED, Refund.State.PROCESSING):
        return refund
    if not refund.provider_reference:
        return refund
    result = gateway.retrieve_refund(refund.provider_reference)
    return apply_provider_result(refund, result) if result else refund


def _submit_refund(refund: Refund) -> Refund:
    """Envia o reintenta una solicitud que aun no obtuvo referencia externa."""
    if refund.status != Refund.State.REQUESTED or refund.provider_reference:
        return reconcile_refund(refund)
    payment = refund.payment
    if not payment.reference:
        raise ValidationError("El pago no tiene una referencia reembolsable.")
    result = gateway.create_refund(
        session_id=payment.reference,
        amount=refund.amount,
        idempotency_key=refund.idempotency_key,
        metadata={
            "tipo": "REEMBOLSO_RESERVA",
            "reembolso_id": str(refund.id),
            "reserva_id": str(payment.booking_id),
        },
    )
    return apply_provider_result(refund, result)


def reconcile_pending() -> int:
    count = 0
    for refund in Refund.objects.filter(
        status__in=(Refund.State.REQUESTED, Refund.State.PROCESSING)
    ).exclude(provider_reference=None):
        previous = refund.status
        current = reconcile_refund(refund)
        if current.status != previous:
            count += 1
    return count


def handle_provider_event(data) -> Refund | None:
    metadata = data.get("metadata") or {}
    local_id = metadata.get("reembolso_id")
    refund = Refund.objects.filter(id=local_id).first() if str(local_id).isdigit() else None
    if refund is None:
        refund = Refund.objects.filter(
            provider=gateway.PROVIDER, provider_reference=data.get("id")
        ).first()
    if refund is None:
        return None
    result = gateway.RefundResult(
        id=data["id"],
        status=data.get("status") or "pending",
        failure_reason=data.get("failure_reason"),
    )
    return apply_provider_result(refund, result)


def request_booking_cancellation(
    *, user, booking_id: int, reason: str | None, idempotency_key: str | None, request=None
) -> tuple[Cancellation, Refund | None]:
    """Congela la cancelacion y solicita la devolucion sin duplicarla."""
    booking = bookings.get_customer_booking(user=user, booking_id=booking_id)
    existing = Cancellation.objects.filter(booking=booking).first()
    if existing is not None:
        refund = existing.refunds.select_related("payment__booking").first()
        return existing, _submit_refund(refund) if refund else None

    quote = bookings.quote_paid_cancellation(user=user, booking_id=booking_id)
    key = f"{user.id}:{idempotency_key or f'cancelar-reserva-{booking_id}'}"[:100]

    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(id=booking_id)
        if booking.status not in bookings.OCCUPYING_STATES or booking.checked_in_at is not None:
            raise ValidationError("La reserva ya no se puede cancelar.")
        first_slot = booking.details.aggregate(first=Min("slot__start"))["first"]
        if first_slot is not None and first_slot <= timezone.now():
            raise ValidationError("La empresa solo puede cancelar antes de que comience el servicio.")
        cancellation, created = Cancellation.objects.get_or_create(
            booking=booking,
            defaults={
                "penalty_rule_id": quote.rule_id,
                "reason": (reason or "").strip() or None,
                "advance_days": quote.advance_days,
                "applied_percentage": quote.penalty_percentage,
                "penalty_amount": quote.penalty_amount,
                "refund_amount": quote.refund_amount,
            },
        )
        if not created:
            refund = cancellation.refunds.select_related("payment__booking").first()
            return cancellation, refund

        if quote.refund_amount == Decimal("0.00"):
            InventoryLock.objects.filter(
                booking=booking,
                status__in=(InventoryLock.State.ACTIVE, InventoryLock.State.CONSUMED),
            ).update(status=InventoryLock.State.RELEASED)
            bookings._transition(
                booking,
                BookingState.CANCELLED,
                user=user,
                reason="Cancelada según la política aceptada, sin monto reembolsable.",
            )
            record_audit(
                actor=user,
                tenant_id=booking.tenant_id,
                action="CANCELAR_RESERVA",
                entity="reserva",
                entity_id=str(booking.id),
                new_data={"reembolso": "0.00", "penalizacion": str(quote.penalty_amount)},
                request=request,
            )
            return cancellation, None

        payment = (
            Payment.objects.select_for_update()
            .filter(booking=booking, status=Payment.State.APPROVED)
            .order_by("id")
            .first()
        )
        if payment is None or not payment.reference:
            raise ValidationError("No existe un pago aprobado que se pueda reembolsar.")
        already = payment.refunds.exclude(
            status__in=(Refund.State.FAILED, Refund.State.CANCELLED)
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        if already + quote.refund_amount > payment.amount:
            raise ValidationError("El reembolso superaría el monto pagado.")
        refund = Refund.objects.create(
            payment=payment,
            cancellation=cancellation,
            currency_id=payment.currency_id,
            amount=quote.refund_amount,
            reason=cancellation.reason,
            provider=gateway.PROVIDER,
            idempotency_key=key,
            requested_by=user,
        )
        record_audit(
            actor=user,
            tenant_id=booking.tenant_id,
            action="SOLICITAR_REEMBOLSO",
            entity="reembolso",
            entity_id=str(refund.id),
            new_data={"estado": refund.status, "monto": str(refund.amount)},
            request=request,
        )

    return cancellation, _submit_refund(refund)


def request_company_cancellation(
    *, actor, tenant_id: int, booking_id: int, reason: str,
    idempotency_key: str | None, manual_refund_confirmed: bool = False,
    manual_reference: str | None = None, request=None,
) -> tuple[Cancellation, Refund]:
    """Cancela por decisión de la empresa y devuelve el 100 % pagado.

    Stripe se confirma mediante su API/webhook. Un pago externo solo se marca
    devuelto cuando el operador declara que ya hizo el reintegro y aporta su
    referencia; SITUR-SMART nunca finge mover ese dinero.
    """
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "RESERVAS_GESTIONAR", tenant_id)
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationError({"motivo": "Explica el motivo (al menos 5 caracteres)."})
    if not idempotency_key:
        raise ValidationError({"Idempotency-Key": "Envía una clave para evitar reembolsos duplicados."})

    with transaction.atomic():
        booking = (
            Booking.objects.select_for_update()
            .select_related("currency")
            .filter(id=booking_id, tenant_id=tenant_id)
            .first()
        )
        if booking is None:
            raise ValidationError("Reserva no encontrada.")
        existing = Cancellation.objects.filter(booking=booking).first()
        if existing is not None:
            refund = existing.refunds.select_related("payment__booking").first()
            if refund is None:
                raise ValidationError("La cancelación existente no tiene un reembolso asociado.")
            return existing, refund
        if booking.status not in bookings.OCCUPYING_STATES or booking.checked_in_at is not None:
            raise ValidationError("La reserva ya no se puede cancelar.")
        payment = (
            Payment.objects.select_for_update()
            .filter(booking=booking, status=Payment.State.APPROVED)
            .order_by("-processed_at", "-id")
            .first()
        )
        if payment is None:
            raise ValidationError("No existe un pago aprobado que se pueda reembolsar.")
        is_manual = payment.provider == "MANUAL"
        manual_reference = (manual_reference or "").strip()
        if is_manual and not manual_refund_confirmed:
            raise ValidationError({
                "reembolso_manual_confirmado":
                    "Confirma que el dinero ya fue devuelto fuera de SITUR-SMART."
            })
        if is_manual and not manual_reference:
            raise ValidationError({
                "referencia_reembolso": "Registra el comprobante o referencia del reintegro."
            })
        advance_days = max(0, (timezone.localdate(first_slot) - timezone.localdate()).days) if first_slot else 0
        cancellation = Cancellation.objects.create(
            booking=booking, penalty_rule=None, reason=reason,
            advance_days=advance_days, applied_percentage=Decimal("0.00"),
            penalty_amount=Decimal("0.00"), refund_amount=payment.amount,
        )
        refund = Refund.objects.create(
            payment=payment, cancellation=cancellation, currency_id=payment.currency_id,
            amount=payment.amount, reason=reason,
            provider="MANUAL" if is_manual else gateway.PROVIDER,
            provider_reference=manual_reference or None,
            idempotency_key=f"empresa:{tenant_id}:{idempotency_key}"[:100],
            requested_by=actor,
        )
        record_audit(
            actor=actor, tenant_id=tenant_id, action="SOLICITAR_REEMBOLSO_EMPRESA",
            entity="reembolso", entity_id=str(refund.id),
            new_data={"reserva": booking.code, "monto": str(refund.amount), "motivo": reason},
            request=request,
        )

    if is_manual:
        return cancellation, complete_refund(
            refund_id=refund.id, provider_reference=manual_reference
        )
    return cancellation, _submit_refund(refund)
