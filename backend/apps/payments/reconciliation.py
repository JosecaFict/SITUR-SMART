"""Conciliación diaria de cobros y devoluciones contra Stripe."""

from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services import record_audit
from apps.bookings import services as bookings

from . import gateway
from .models import Payment, ReconciliationIssue, Refund
from .refunds import apply_provider_result

ACTION = "CONCILIAR_PAGOS"


def _issue(*, resource_type: str, resource_id: int, kind: str, tenant_id: int,
           local_status: str, provider_status: str, details: dict) -> None:
    ReconciliationIssue.objects.update_or_create(
        resource_type=resource_type, resource_id=resource_id, kind=kind,
        defaults={
            "tenant_id": tenant_id, "local_status": local_status,
            "provider_status": provider_status, "details": details,
            "resolved": False, "resolved_at": None,
        },
    )


def _resolve(resource_type: str, resource_id: int) -> int:
    return ReconciliationIssue.objects.filter(
        resource_type=resource_type, resource_id=resource_id, resolved=False
    ).update(resolved=True, resolved_at=timezone.now())


def _payments() -> dict[str, int]:
    checked = corrected = issues = unavailable = 0
    queryset = Payment.objects.filter(provider=gateway.PROVIDER).exclude(reference=None)
    for payment in queryset.select_related("booking").iterator():
        checked += 1
        session = gateway.retrieve_session(payment.reference)
        if session is None:
            unavailable += 1
            continue
        provider_status = "PAGADO" if session.paid else session.status.upper()
        if payment.status == Payment.State.PENDING and session.paid:
            bookings.confirm_paid_session(payment.reference)
            corrected += 1
            _resolve("PAGO", payment.id)
        elif payment.status == Payment.State.PENDING and session.status == "expired":
            bookings.expire_session(payment.reference)
            corrected += 1
            _resolve("PAGO", payment.id)
        elif payment.status == Payment.State.APPROVED and not session.paid:
            _issue(
                resource_type="PAGO", resource_id=payment.id,
                kind=ReconciliationIssue.Kind.PAYMENT_MISMATCH,
                tenant_id=payment.booking.tenant_id, local_status=payment.status,
                provider_status=provider_status,
                details={"reserva_id": payment.booking_id, "referencia": payment.reference},
            )
            issues += 1
        elif payment.status == Payment.State.VOIDED and session.paid:
            # El servicio existente protege contra doble ingreso y notifica si
            # ya había un pago manual aprobado.
            bookings.confirm_paid_session(payment.reference)
            payment.refresh_from_db(fields=("status",))
            if payment.status == Payment.State.VOIDED:
                _issue(
                    resource_type="PAGO", resource_id=payment.id,
                    kind=ReconciliationIssue.Kind.LATE_PAYMENT,
                    tenant_id=payment.booking.tenant_id, local_status=payment.status,
                    provider_status=provider_status,
                    details={"reserva_id": payment.booking_id, "referencia": payment.reference},
                )
                issues += 1
            else:
                corrected += 1
                _resolve("PAGO", payment.id)
        else:
            _resolve("PAGO", payment.id)
    return {"revisados": checked, "corregidos": corrected, "incidencias": issues,
            "no_consultados": unavailable}


def _refunds() -> dict[str, int]:
    checked = corrected = issues = unavailable = 0
    queryset = Refund.objects.filter(provider=gateway.PROVIDER).exclude(provider_reference=None)
    for refund in queryset.select_related("payment__booking").iterator():
        checked += 1
        result = gateway.retrieve_refund(refund.provider_reference)
        if result is None:
            unavailable += 1
            continue
        before = refund.status
        if result.succeeded or result.failed:
            refund = apply_provider_result(refund, result)
            corrected += int(refund.status != before)
        agrees = (
            (refund.status == Refund.State.COMPLETED and result.succeeded)
            or (refund.status == Refund.State.FAILED and result.failed)
            or (refund.status in (Refund.State.REQUESTED, Refund.State.PROCESSING)
                and not result.succeeded and not result.failed)
        )
        if agrees:
            _resolve("REEMBOLSO", refund.id)
        else:
            _issue(
                resource_type="REEMBOLSO", resource_id=refund.id,
                kind=ReconciliationIssue.Kind.REFUND_MISMATCH,
                tenant_id=refund.payment.booking.tenant_id, local_status=refund.status,
                provider_status=result.status.upper(),
                details={"pago_id": refund.payment_id,
                         "reserva_id": refund.payment.booking_id,
                         "referencia": refund.provider_reference},
            )
            issues += 1
    return {"revisados": checked, "corregidos": corrected, "incidencias": issues,
            "no_consultados": unavailable}


def run(*, force: bool = False, actor=None) -> dict:
    """Ejecuta como máximo una vez por día, salvo la acción manual del admin."""
    today = timezone.localdate()
    if not force and AuditLog.objects.filter(action=ACTION, created_at__date=today).exists():
        return {"omitida": True, "pagos": {}, "reembolsos": {}}
    payments = _payments()
    refunds = _refunds()
    retry = payments["no_consultados"] > 0 or refunds["no_consultados"] > 0
    result = {
        "omitida": False, "pendiente_reintento": retry,
        "pagos": payments, "reembolsos": refunds,
    }
    # Si Stripe estuvo inaccesible, el cron vuelve a intentar en su siguiente
    # pasada; no se consume falsamente la conciliación del día.
    if not retry:
        record_audit(
            actor=actor, action=ACTION, entity="conciliacion_pago",
            new_data=result,
        )
    return result
