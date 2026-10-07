"""Reservas vistas por la empresa que vende (y por el SuperAdmin, para soporte).

Cada empresa ve solo sus reservas y el contacto de quien le reservo; nunca a
los turistas en general. Valida el voucher cuando el cliente llega (una sola
vez) y puede reportar a un cliente a la plataforma, que es quien decide si lo
bloquea.

Permisos: RESERVAS_LEER para ver, RESERVAS_GESTIONAR para marcar llegadas y
reportar. Ya estan en los roles de empresa desde 002_seed_catalogs.sql.
"""

from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models import Min, Prefetch, Q, QuerySet, Sum
from django.utils import timezone
from django.utils.html import escape
from rest_framework.exceptions import NotFound, ValidationError

from apps.accounts.brevo import send_email
from apps.accounts.models import User
from apps.audit.services import record_audit
from apps.payments.models import Payment
from apps.rbac.services import require_permission, require_tenant_access

from .models import Booking, BookingDetail, BookingState, CustomerReport
from .services import OCCUPYING_STATES, read_voucher

READ = "RESERVAS_LEER"
MANAGE = "RESERVAS_GESTIONAR"


def _require(actor, tenant_id: int, permission: str) -> None:
    require_tenant_access(actor, tenant_id)
    require_permission(actor, permission, tenant_id)


def _local_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.get_current_timezone())


def _bookings(tenant_id: int) -> QuerySet[Booking]:
    return (
        Booking.objects.filter(tenant_id=tenant_id)
        .select_related("order__customer__user", "currency", "tenant", "checked_in_by")
        .prefetch_related(
            Prefetch(
                "details",
                queryset=BookingDetail.objects.select_related(
                    "slot__product__product_type", "slot__product__city",
                    "slot__product__room__establishment__product",
                ).order_by("slot__start"),
            ),
            Prefetch("payments", queryset=Payment.objects.order_by("-created_at")),
        )
        .annotate(first_slot=Min("details__slot__start"))
    )


def list_bookings(*, actor, tenant_id: int, filters: dict) -> QuerySet[Booking]:
    """Filtros: desde/hasta (dia del servicio), estado, producto_id, buscar, llegadas=hoy."""
    _require(actor, tenant_id, READ)
    queryset = _bookings(tenant_id)
    if filters.get("desde"):
        queryset = queryset.filter(first_slot__gte=_local_start(filters["desde"]))
    if filters.get("hasta"):
        queryset = queryset.filter(first_slot__lt=_local_start(filters["hasta"] + timedelta(days=1)))
    if filters.get("estado"):
        queryset = queryset.filter(status=filters["estado"])
    if filters.get("producto_id"):
        queryset = queryset.filter(details__slot__product_id=filters["producto_id"]).distinct()
    if filters.get("llegadas_hoy"):
        today = timezone.localdate()
        queryset = queryset.filter(
            status__in=OCCUPYING_STATES,
            first_slot__gte=_local_start(today),
            first_slot__lt=_local_start(today + timedelta(days=1)),
        )
    if search := (filters.get("buscar") or "").strip():
        queryset = queryset.filter(
            Q(code__icontains=search)
            | Q(order__customer__user__first_names__icontains=search)
            | Q(order__customer__user__last_names__icontains=search)
            | Q(order__customer__user__email__icontains=search)
        )
    return queryset.order_by("first_slot", "id")


def summary(*, actor, tenant_id: int) -> dict:
    _require(actor, tenant_id, READ)
    today = timezone.localdate()
    base = Booking.objects.filter(tenant_id=tenant_id).annotate(first_slot=Min("details__slot__start"))
    month_start = today.replace(day=1)
    income = (
        Payment.objects.filter(
            booking__tenant_id=tenant_id, status=Payment.State.APPROVED, processed_at__date__gte=month_start
        )
        .values("currency__iso_code")
        .annotate(total=Sum("amount"))
    )
    return {
        "llegadas_hoy": base.filter(
            status__in=OCCUPYING_STATES,
            first_slot__gte=_local_start(today),
            first_slot__lt=_local_start(today + timedelta(days=1)),
        ).count(),
        "proximas": base.filter(status__in=OCCUPYING_STATES, first_slot__gte=_local_start(today)).count(),
        "pendientes_pago": base.filter(status=BookingState.CREATED).count(),
        "ingresos_mes": [{"moneda": row["currency__iso_code"], "total": f"{row['total']:.2f}"} for row in income],
    }


def get_booking(*, actor, tenant_id: int, booking_id: int) -> Booking:
    _require(actor, tenant_id, READ)
    booking = _bookings(tenant_id).filter(id=booking_id).first()
    if booking is None:
        raise NotFound("Reserva no encontrada.")
    return booking


def lookup_voucher(*, actor, tenant_id: int, value: str) -> dict:
    """Encuentra la reserva por su codigo (RES-...) o por el contenido del QR.

    Devuelve la reserva y si se puede marcar la llegada ahora, con el motivo si no.
    """
    _require(actor, tenant_id, READ)
    value = (value or "").strip()
    if not value:
        raise ValidationError({"codigo": "Escribe el código de la reserva."})
    booking = None
    if value.upper().startswith("RES-"):
        booking = _bookings(tenant_id).filter(code__iexact=value).first()
    else:
        try:
            data = read_voucher(value)
        except (signing.BadSignature, ValueError, KeyError):
            data = None
        if data:
            booking = _bookings(tenant_id).filter(id=data.get("r"), code=data.get("c")).first()
    if booking is None:
        # Igual si no existe o es de otra empresa: no se revela cual.
        raise NotFound("No hay una reserva de tu empresa con ese código.")
    return {"reserva": booking, **_check_in_status(booking)}


def _check_in_status(booking: Booking) -> dict:
    if booking.checked_in_at:
        local = timezone.localtime(booking.checked_in_at).strftime("%d/%m/%Y %H:%M")
        who = booking.checked_in_by.get_full_name() if booking.checked_in_by_id else "personal"
        return {"puede_marcar_llegada": False, "motivo": f"Ya se marcó la llegada el {local} ({who})."}
    if booking.status == BookingState.CREATED:
        return {"puede_marcar_llegada": False, "motivo": "La reserva todavía no está pagada."}
    if booking.status not in OCCUPYING_STATES:
        return {"puede_marcar_llegada": False, "motivo": "La reserva no está activa (cancelada o vencida)."}
    first = getattr(booking, "first_slot", None)
    if first is not None and timezone.localtime(first).date() > timezone.localdate():
        day = timezone.localtime(first).strftime("%d/%m/%Y")
        return {"puede_marcar_llegada": True, "motivo": f"Atención: la reserva es para el {day}."}
    return {"puede_marcar_llegada": True, "motivo": None}


def check_in(*, actor, tenant_id: int, booking_id: int, request=None) -> Booking:
    _require(actor, tenant_id, MANAGE)
    with transaction.atomic():
        booking = Booking.objects.select_for_update().filter(tenant_id=tenant_id, id=booking_id).first()
        if booking is None:
            raise NotFound("Reserva no encontrada.")
        status = _check_in_status(get_booking(actor=actor, tenant_id=tenant_id, booking_id=booking_id))
        if not status["puede_marcar_llegada"]:
            raise ValidationError({"llegada": status["motivo"]})
        booking.checked_in_at = timezone.now()
        booking.checked_in_by = actor
        booking.save(update_fields=["checked_in_at", "checked_in_by", "updated_at"])
        record_audit(
            actor=actor, tenant_id=tenant_id, action="VALIDAR_LLEGADA", entity="reserva",
            entity_id=str(booking.id), new_data={"codigo": booking.code}, request=request,
        )
    return get_booking(actor=actor, tenant_id=tenant_id, booking_id=booking_id)


def report_customer(*, actor, tenant_id: int, booking_id: int, reason: str, request=None) -> CustomerReport:
    """Avisa al SuperAdmin; no bloquea al cliente."""
    _require(actor, tenant_id, MANAGE)
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationError({"motivo": "Explica el problema (al menos 5 caracteres)."})
    booking = get_booking(actor=actor, tenant_id=tenant_id, booking_id=booking_id)
    customer = booking.order.customer.user
    report = CustomerReport.objects.create(
        tenant_id=tenant_id, customer=customer, booking=booking, reported_by=actor, reason=reason[:2000]
    )
    record_audit(
        actor=actor, tenant_id=tenant_id, action="REPORTAR_CLIENTE", entity="cliente",
        entity_id=str(customer.id), new_data={"reserva": booking.code, "motivo": reason[:500]}, request=request,
    )
    _notify_platform(report)
    return report


def _notify_platform(report: CustomerReport) -> None:
    panel = f"{settings.WEB_APP_URL.rstrip('/')}/clientes"
    company = escape(report.tenant.trade_name)
    customer = escape(f"{report.customer.get_full_name()} ({report.customer.email})")
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:520px;color:#0f172a">'
        '<h2 style="color:#0f766e">SITUR-SMART</h2>'
        f"<p><strong>{company}</strong> reportó a un cliente: <strong>{customer}</strong>.</p>"
        f"<p>Motivo: {escape(report.reason)}</p>"
        f'<p><a href="{escape(panel)}">Revisar en Clientes</a></p></div>'
    )
    admins = User.objects.filter(
        status=User.Status.ACTIVE, user_roles__role__code="SUPER_ADMIN", user_roles__tenant__isnull=True
    ).distinct()
    for admin in admins:
        send_email(to_email=admin.email, to_name=admin.get_full_name(), subject="Cliente reportado - SITUR-SMART", html=html)


def reports_for_customer(customer_id: int) -> list[dict]:
    """Para la ficha del cliente que ve el SuperAdmin."""
    return [
        {
            "fecha": report.created_at,
            "empresa": report.tenant.trade_name,
            "reserva": report.booking.code if report.booking_id else None,
            "por": report.reported_by.get_full_name() if report.reported_by_id else None,
            "motivo": report.reason,
        }
        for report in CustomerReport.objects.select_related("tenant", "booking", "reported_by").filter(
            customer_id=customer_id
        )[:20]
    ]

