from datetime import date, datetime, time, timedelta

from django.db.models import Prefetch, Q, QuerySet, Sum
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.bookings.models import BookingDetail
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
