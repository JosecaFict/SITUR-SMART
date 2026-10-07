"""Administracion de las cuentas de los turistas (SuperAdmin o rol con CLIENTES_GESTIONAR).

La plataforma controla la *cuenta*: verla, bloquearla, desbloquearla, cerrar
sus sesiones y mandarle el codigo para recuperar la contrasena. No edita sus
datos personales (eso es del turista) ni entra en su nombre. Cada accion lleva
motivo y queda en la bitacora.

Bloquear corta al turista al instante en la web y en el movil: el access token
deja de valer en cuanto la cuenta no esta activa, y las sesiones se revocan
para que no pueda renovarlo.
"""

from collections import defaultdict

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, QuerySet, Sum
from django.utils import timezone
from django.utils.html import escape
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit.models import AuditLog
from apps.audit.services import record_audit
from apps.rbac.services import require_permission

from .brevo import send_email
from .models import User, UserSession

PERMISSION = "CLIENTES_GESTIONAR"
AUDIT_ENTITY = "cliente"


def require_customer_management(actor) -> None:
    require_permission(actor, PERMISSION)


def _customers() -> QuerySet[User]:
    """Turistas: cuentas con perfil de cliente que no son personal ni SuperAdmin."""
    return User.objects.filter(customer_profile__isnull=False).exclude(
        Q(user_roles__role__code="SUPER_ADMIN") | Q(tenant_memberships__isnull=False)
    )


def _customer(user_id: int) -> User:
    customer = _customers().filter(id=user_id).first()
    if customer is None:
        raise NotFound("Cliente no encontrado.")
    return customer


def list_customers(*, actor, search: str = "", status: str = "", with_bookings: str = "") -> QuerySet[User]:
    require_customer_management(actor)
    queryset = _customers().annotate(
        bookings_count=Count("customer_profile__orders__bookings", distinct=True)
    )
    if search:
        queryset = queryset.filter(
            Q(email__icontains=search) | Q(first_names__icontains=search) | Q(last_names__icontains=search)
        )
    if status:
        queryset = queryset.filter(status=status)
    if with_bookings == "si":
        queryset = queryset.filter(bookings_count__gt=0)
    elif with_bookings == "no":
        queryset = queryset.filter(bookings_count=0)
    return queryset.order_by("-created_at", "-id")


def summary_counts(*, actor) -> dict:
    require_customer_management(actor)
    customers = _customers()
    month_start = timezone.localdate().replace(day=1)
    return {
        "total": customers.count(),
        "nuevos_mes": customers.filter(created_at__date__gte=month_start).count(),
        "con_reservas": customers.filter(customer_profile__orders__bookings__isnull=False).distinct().count(),
        "bloqueados": customers.filter(status=User.Status.BLOCKED).count(),
    }


def paid_totals(user_ids: list[int]) -> dict[int, list[dict]]:
    """Total pagado por cada turista, separado por moneda."""
    from apps.payments.models import Payment

    rows = (
        Payment.objects.filter(
            booking__order__customer__user_id__in=user_ids, status=Payment.State.APPROVED
        )
        .values("booking__order__customer__user_id", "currency__iso_code")
        .annotate(total=Sum("amount"))
    )
    totals: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        totals[row["booking__order__customer__user_id"]].append(
            {"moneda": row["currency__iso_code"], "total": f"{row['total']:.2f}"}
        )
    return totals


def customer_detail(*, actor, user_id: int) -> dict:
    """La ficha: cuenta, actividad, dispositivos y el historial de acciones sobre ella."""
    from apps.bookings.models import Booking
    from apps.bookings.serializers import BookingSerializer
    from apps.bookings.services import OCCUPYING_STATES
    from apps.notifications.models import PushDevice

    require_customer_management(actor)
    customer = _customer(user_id)
    bookings = list(
        Booking.objects.filter(order__customer__user=customer)
        .select_related("tenant", "currency", "order")
        .prefetch_related("details__slot__product__product_type", "details__slot__product__city",
                          "details__slot__product__room__establishment__product", "payments")
        .order_by("-created_at", "-id")[:20]
    )
    serializer = BookingSerializer()
    history = AuditLog.objects.filter(entity=AUDIT_ENTITY, entity_id=str(customer.id)).select_related("user")
    by_status = Booking.objects.filter(order__customer__user=customer).values("status").annotate(n=Count("id"))
    counts = {row["status"]: row["n"] for row in by_status}
    return {
        "cliente": customer,
        "actividad": {
            "reservas": sum(counts.values()),
            "pagadas": sum(counts.get(state, 0) for state in OCCUPYING_STATES),
            "pendientes": counts.get("CREADA", 0),
            "canceladas": counts.get("CANCELADA", 0) + counts.get("EXPIRADA_LIBERADA", 0),
            "total_pagado": paid_totals([customer.id]).get(customer.id, []),
        },
        "sesiones_abiertas": UserSession.objects.filter(
            user=customer, revoked_at__isnull=True, expires_at__gt=timezone.now()
        ).count(),
        "dispositivos_push": PushDevice.objects.filter(user=customer).count(),
        "reservas": [
            {
                "id": booking.id,
                "codigo": booking.code,
                "estado": booking.status,
                "empresa": booking.tenant.trade_name,
                "producto": (serializer.get_producto(booking) or {}).get("nombre"),
                "fechas": serializer.get_fechas(booking),
                "total": serializer.get_importe(booking)["total"],
                "moneda": booking.currency.iso_code,
                "creado_en": booking.created_at,
            }
            for booking in bookings
        ],
        "historial": [
            {
                "fecha": log.created_at,
                "accion": log.action,
                "por": log.user.get_full_name() if log.user_id else "Sistema",
                "motivo": (log.new_data or {}).get("motivo"),
            }
            for log in history.order_by("-created_at")[:20]
        ],
    }


def _revoke_sessions(customer: User) -> int:
    return UserSession.objects.filter(user=customer, revoked_at__isnull=True).update(revoked_at=timezone.now())


def _reason(reason: str) -> str:
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationError({"motivo": "Explica el motivo (al menos 5 caracteres)."})
    return reason[:500]


def block_customer(*, actor, user_id: int, reason: str, request=None) -> User:
    """Suspende la cuenta: sesiones fuera, sin push y sin reservas pendientes.

    Las reservas pagadas se mantienen: el turista ya pago y la empresa lo espera.
    """
    from apps.bookings.services import cancel_unpaid_for_customer
    from apps.notifications.models import PushDevice

    require_customer_management(actor)
    reason = _reason(reason)
    with transaction.atomic():
        customer = _customer(user_id)
        if customer.status == User.Status.BLOCKED:
            raise ValidationError({"estado": "La cuenta ya está bloqueada."})
        previous = customer.status
        customer.status = User.Status.BLOCKED
        customer.save(update_fields=["status", "updated_at"])
        sessions = _revoke_sessions(customer)
        PushDevice.objects.filter(user=customer).delete()
        cancelled = cancel_unpaid_for_customer(
            customer=customer, actor=actor, reason=f"Cuenta suspendida por la plataforma: {reason}"
        )
        record_audit(
            actor=actor, action="BLOQUEAR_CLIENTE", entity=AUDIT_ENTITY, entity_id=str(customer.id),
            previous_data={"estado": previous},
            new_data={"estado": customer.status, "motivo": reason, "sesiones_cerradas": sessions,
                      "reservas_canceladas": cancelled},
            request=request,
        )
    _email(
        customer,
        "Tu cuenta de SITUR-SMART fue suspendida",
        f"<p>Tu cuenta fue suspendida por el siguiente motivo:</p><p><strong>{escape(reason)}</strong></p>"
        "<p>Tus reservas ya pagadas se mantienen. Si crees que es un error, escríbenos a "
        f"<a href=\"mailto:{escape(settings.SOPORTE_EMAIL)}\">{escape(settings.SOPORTE_EMAIL)}</a>.</p>",
    )
    return customer


def unblock_customer(*, actor, user_id: int, reason: str, request=None) -> User:
    require_customer_management(actor)
    reason = _reason(reason)
    customer = _customer(user_id)
    if customer.status != User.Status.BLOCKED:
        raise ValidationError({"estado": "La cuenta no está bloqueada."})
    customer.status = User.Status.ACTIVE
    customer.save(update_fields=["status", "updated_at"])
    record_audit(
        actor=actor, action="DESBLOQUEAR_CLIENTE", entity=AUDIT_ENTITY, entity_id=str(customer.id),
        previous_data={"estado": User.Status.BLOCKED}, new_data={"estado": customer.status, "motivo": reason},
        request=request,
    )
    _email(
        customer,
        "Tu cuenta de SITUR-SMART está activa de nuevo",
        "<p>Ya puedes iniciar sesión y reservar con normalidad.</p>",
    )
    return customer


def close_sessions(*, actor, user_id: int, reason: str, request=None) -> int:
    """Saca al turista de todos sus dispositivos sin bloquear la cuenta (p. ej. celular robado)."""
    require_customer_management(actor)
    reason = _reason(reason)
    customer = _customer(user_id)
    closed = _revoke_sessions(customer)
    record_audit(
        actor=actor, action="CERRAR_SESIONES_CLIENTE", entity=AUDIT_ENTITY, entity_id=str(customer.id),
        new_data={"motivo": reason, "sesiones_cerradas": closed}, request=request,
    )
    return closed


def send_password_reset(*, actor, user_id: int, request=None) -> None:
    from .services import request_password_reset_otp

    require_customer_management(actor)
    customer = _customer(user_id)
    if not customer.is_active:
        raise ValidationError({"estado": "La cuenta no está activa: desbloquéala primero."})
    request_password_reset_otp(email=customer.email, request=request)
    record_audit(
        actor=actor, action="ENVIAR_RECUPERACION", entity=AUDIT_ENTITY, entity_id=str(customer.id),
        request=request,
    )


def _email(customer: User, subject: str, body: str) -> None:
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:520px;color:#0f172a">'
        f'<h2 style="color:#0f766e">SITUR-SMART</h2><p>Hola {escape(customer.first_names)},</p>{body}</div>'
    )
    send_email(to_email=customer.email, to_name=customer.get_full_name(), subject=f"{subject} - SITUR-SMART", html=html)
