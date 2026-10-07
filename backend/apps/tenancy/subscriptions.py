"""Ciclo de vida de la suscripcion de cada empresa (SaaS).

* Cada periodo dura un mes o un ano segun la periodicidad contratada.
* ``process_due`` lo corre el cron (``tareas_programadas``): avisa por correo 7
  y 1 dias antes, renueva las que tienen renovacion automatica y vence las
  demas.
* Una empresa con el plan vencido queda **restringida**: sus productos salen
  del Marketplace y su personal entra pero no puede crear ni editar oferta.
  Las reservas ya pagadas se respetan. No es una suspension: el estado de la
  empresa no cambia y al renovar todo vuelve solo.
* La empresa renueva pagando con Stripe Checkout desde "Mi plan"; el webhook
  (o la consulta de "Mi plan" si el webhook no llego) aplica el pago.
"""

import calendar
import logging
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.html import escape
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)

from apps.accounts.brevo import send_email
from apps.accounts.models import User
from apps.audit.services import record_audit
from apps.payments import gateway
from apps.rbac.models import Role, UserRole
from apps.rbac.services import is_superadmin, require_tenant_membership

from .models import Plan, Subscription, SubscriptionPayment, Tenant, UserTenant

logger = logging.getLogger(__name__)

NOTICE_DAYS = (7, 1)
# Desde cuantos dias antes "Mi plan" muestra que esta por vencer.
SOON_DAYS = 7
CHECKOUT_MINUTES = 35


class PlanExpired(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "El plan de la empresa venció. Renuévalo en Mi plan para volver a crear y publicar."
    default_code = "plan_vencido"


# --- Fechas --------------------------------------------------------------------


def add_months(day: date, months: int) -> date:
    """Mismo dia N meses despues; el 31 cae en el ultimo dia si el mes es corto."""
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def period_end(start: date, periodicity: str | None) -> date:
    return add_months(start, 12 if periodicity == Plan.Periodicity.YEARLY else 1)


# --- Restriccion ---------------------------------------------------------------


def restricted_tenant_ids():
    """Empresas con el plan vencido y sin uno activo (subconsulta para filtrar)."""
    active = Subscription.objects.filter(status=Subscription.Status.ACTIVE).values("tenant_id")
    return (
        Subscription.objects.filter(status=Subscription.Status.EXPIRED)
        .exclude(tenant_id__in=active)
        .values("tenant_id")
    )


def is_restricted(tenant_id: int) -> bool:
    return restricted_tenant_ids().filter(tenant_id=tenant_id).exists()


def require_active_plan(actor, tenant_id: int) -> None:
    """Corta la creacion y edicion de oferta de una empresa con el plan vencido.

    El SuperAdmin pasa: corregir datos de una empresa vencida es parte de su trabajo.
    """
    if is_superadmin(actor):
        return
    if is_restricted(tenant_id):
        raise PlanExpired()


# --- Consulta de "Mi plan" -------------------------------------------------------


def _owner_ids(tenant_id: int) -> list[int]:
    return list(
        UserRole.objects.filter(
            tenant_id=tenant_id, role__code="TENANT_ADMIN", role__scope=Role.Scope.TENANT
        ).values_list("user_id", flat=True)
    )


def _require_owner(actor, tenant_id: int) -> None:
    """Pagar o cambiar la renovacion es cosa del propietario (o del SuperAdmin)."""
    if is_superadmin(actor):
        return
    require_tenant_membership(actor, tenant_id)
    if actor.id not in _owner_ids(tenant_id):
        raise PermissionDenied("Solo el propietario de la empresa puede gestionar el plan.")


def _current(tenant_id: int) -> Subscription | None:
    """La activa o, si no hay, la ultima (vencida, cancelada...)."""
    base = Subscription.objects.select_related("plan", "plan__currency", "contracted_currency").filter(
        tenant_id=tenant_id
    )
    return base.filter(status=Subscription.Status.ACTIVE).first() or base.order_by("-created_at", "-id").first()


def summary(tenant_id: int) -> dict:
    """Plan, vencimiento y estado en una linea: la lista de empresas del SuperAdmin."""
    subscription = _current(tenant_id)
    if subscription is None:
        return {"nombre": None, "vence": None, "estado": "SIN_PLAN"}
    state = subscription.status
    if state == Subscription.Status.ACTIVE and subscription.end_date:
        if (subscription.end_date - timezone.localdate()).days <= SOON_DAYS:
            state = "POR_VENCER"
    return {"nombre": subscription.plan.name, "vence": subscription.end_date, "estado": state}


def plan_status(*, actor, tenant_id: int) -> dict:
    require_tenant_membership(actor, tenant_id)
    sync_pending_payments(tenant_id)
    tenant = Tenant.objects.filter(id=tenant_id).first()
    if tenant is None:
        raise NotFound("Empresa no encontrada.")
    subscription = _current(tenant_id)
    today = timezone.localdate()
    active = subscription is not None and subscription.status == Subscription.Status.ACTIVE
    days_left = (subscription.end_date - today).days if active and subscription.end_date else None
    if subscription is None:
        state = "SIN_PLAN"
    elif not active:
        state = "VENCIDA" if subscription.status == Subscription.Status.EXPIRED else subscription.status
    elif days_left is not None and days_left <= SOON_DAYS:
        state = "POR_VENCER"
    else:
        state = "ACTIVA"

    from apps.catalog.models import TourismProduct

    plan = subscription.plan if subscription else None
    usage = []
    if plan is not None:
        usage = [
            {
                "recurso": "usuarios",
                "etiqueta": "Usuarios",
                "usado": UserTenant.objects.filter(tenant_id=tenant_id, status=UserTenant.Status.ACTIVE).count(),
                "limite": plan.max_users,
            },
            {
                "recurso": "productos",
                "etiqueta": "Productos",
                "usado": TourismProduct.objects.filter(tenant_id=tenant_id).count(),
                "limite": plan.max_products,
            },
        ]
    is_owner = is_superadmin(actor) or actor.id in _owner_ids(tenant_id)
    return {
        "empresa": {"id": tenant.id, "nombre": tenant.trade_name, "estado": tenant.status},
        "estado": state,
        "restringida": is_restricted(tenant_id),
        "plan": None
        if plan is None
        else {
            "codigo": plan.code,
            "nombre": plan.name,
            "periodicidad": subscription.contracted_periodicity or plan.periodicity,
            "precio": str(subscription.contracted_price if subscription.contracted_price is not None else plan.price),
            "moneda": (subscription.contracted_currency or plan.currency).iso_code,
            "precio_renovacion": str(plan.price),
        },
        "inicio": subscription.start_date if subscription else None,
        "vence": subscription.end_date if subscription else None,
        "dias_restantes": days_left,
        "renovacion_automatica": bool(subscription and subscription.auto_renew),
        "uso": usage,
        "es_propietario": is_owner,
        "puede_pagar": is_owner and gateway.is_configured() and tenant.status == Tenant.Status.ACTIVE,
        "pagos": [
            {
                "id": payment.id,
                "plan": payment.plan.name,
                "monto": str(payment.amount),
                "moneda": payment.currency.iso_code,
                "estado": payment.status,
                "fecha": payment.processed_at or payment.created_at,
            }
            for payment in SubscriptionPayment.objects.select_related("plan", "currency").filter(
                tenant_id=tenant_id
            )[:5]
        ],
    }


def set_auto_renew(*, actor, tenant_id: int, value: bool, request=None) -> None:
    _require_owner(actor, tenant_id)
    subscription = Subscription.objects.filter(tenant_id=tenant_id, status=Subscription.Status.ACTIVE).first()
    if subscription is None:
        raise ValidationError({"renovacion_automatica": "La empresa no tiene un plan vigente."})
    previous = subscription.auto_renew
    subscription.auto_renew = value
    subscription.save(update_fields=["auto_renew"])
    record_audit(
        actor=actor,
        tenant_id=tenant_id,
        action="ACTUALIZAR",
        entity="suscripcion",
        entity_id=str(subscription.id),
        previous_data={"renovacion_automatica": previous},
        new_data={"renovacion_automatica": value},
        request=request,
    )


# --- Proceso automatico ----------------------------------------------------------


def process_due(today: date | None = None) -> dict:
    """Avisa, renueva y vence. Idempotente: el cron lo corre cada pocos minutos."""
    today = today or timezone.localdate()
    counts = {"avisos": 0, "renovadas": 0, "vencidas": 0}
    due = Subscription.objects.select_related("tenant", "plan", "plan__currency").filter(
        status=Subscription.Status.ACTIVE, end_date__isnull=False
    )
    for subscription in due:
        days_left = (subscription.end_date - today).days
        if days_left <= 0:
            with transaction.atomic():
                locked = Subscription.objects.select_for_update().get(id=subscription.id)
                if locked.status != Subscription.Status.ACTIVE:
                    continue
                if locked.auto_renew and subscription.tenant.status == Tenant.Status.ACTIVE:
                    _extend(locked, subscription.plan)
                    record_audit(
                        actor=None, tenant_id=locked.tenant_id, action="RENOVAR_PLAN", entity="suscripcion",
                        entity_id=str(locked.id), new_data={"vence": locked.end_date.isoformat(), "automatica": True},
                    )
                    counts["renovadas"] += 1
                    kind = "RENOVADA"
                else:
                    locked.status = Subscription.Status.EXPIRED
                    locked.save(update_fields=["status"])
                    record_audit(
                        actor=None, tenant_id=locked.tenant_id, action="VENCER_PLAN", entity="suscripcion",
                        entity_id=str(locked.id), new_data={"vencio": locked.end_date.isoformat()},
                    )
                    counts["vencidas"] += 1
                    kind = "VENCIDA"
            notify_owners(locked, kind)
        elif days_left in NOTICE_DAYS and subscription.last_notice_days != days_left:
            subscription.last_notice_days = days_left
            subscription.save(update_fields=["last_notice_days"])
            notify_owners(subscription, "AVISO", days_left=days_left)
            counts["avisos"] += 1
    return counts


def _extend(subscription: Subscription, plan: Plan) -> None:
    """Un periodo mas desde el fin del actual (o desde hoy si ya paso)."""
    start = max(subscription.end_date or timezone.localdate(), timezone.localdate())
    subscription.end_date = period_end(start, plan.periodicity)
    subscription.contracted_price = plan.price
    subscription.contracted_currency_id = plan.currency_id
    subscription.contracted_periodicity = plan.periodicity
    subscription.last_notice_days = None
    subscription.save(
        update_fields=[
            "end_date", "contracted_price", "contracted_currency", "contracted_periodicity", "last_notice_days",
        ]
    )


# --- Pago de la renovacion con Stripe ---------------------------------------------


def start_checkout(*, actor, tenant_id: int, plan_code: str | None = None, request=None) -> str:
    """Abre el pago de un periodo del plan (el actual u otro) y devuelve la URL de Stripe."""
    _require_owner(actor, tenant_id)
    tenant = Tenant.objects.filter(id=tenant_id).first()
    if tenant is None:
        raise NotFound("Empresa no encontrada.")
    if tenant.status != Tenant.Status.ACTIVE:
        raise ValidationError({"empresa": "La empresa no está activa. Comunícate con SITUR-SMART."})
    current = _current(tenant_id)
    code = plan_code or (current.plan.code if current else None)
    plan = Plan.objects.select_related("currency").filter(code=code, active=True).first() if code else None
    if plan is None:
        raise ValidationError({"plan_codigo": "Elige un plan válido."})
    if plan.price <= 0:
        raise ValidationError({"plan_codigo": "Este plan no requiere pago."})

    # Una sola renovacion abierta a la vez: las anteriores se anulan.
    for old in SubscriptionPayment.objects.filter(tenant_id=tenant_id, status=SubscriptionPayment.State.PENDING):
        if old.reference:
            gateway.expire_session(old.reference)
        old.status = SubscriptionPayment.State.VOIDED
        old.processed_at = timezone.now()
        old.save(update_fields=["status", "processed_at"])

    payment = SubscriptionPayment.objects.create(
        tenant=tenant, plan=plan, payer=actor, currency=plan.currency, amount=plan.price
    )
    panel = f"{settings.WEB_APP_URL.rstrip('/')}/mi-plan"
    session = gateway.create_checkout_session(
        reference=f"SUS-{payment.id}",
        description=f"SITUR-SMART plan {plan.name} ({plan.get_periodicity_display().lower()}) - {tenant.trade_name}",
        amount=plan.price,
        currency=plan.currency.iso_code,
        customer_email=actor.email,
        success_url=f"{panel}?pago=exito",
        cancel_url=f"{panel}?pago=cancelado",
        expires_at=timezone.now() + timedelta(minutes=CHECKOUT_MINUTES),
        idempotency_key=f"suscripcion-{payment.id}",
        metadata={"tipo": "SUSCRIPCION", "pago_suscripcion_id": str(payment.id), "empresa": str(tenant.id)},
    )
    payment.reference = session.id
    payment.save(update_fields=["reference"])
    record_audit(
        actor=actor, tenant_id=tenant_id, action="INICIAR_PAGO", entity="pago_suscripcion",
        entity_id=str(payment.id), new_data={"plan": plan.code, "monto": str(plan.price)}, request=request,
    )
    return session.url


def confirm_payment(session_id: str) -> SubscriptionPayment | None:
    """Aplica un pago cobrado: extiende el plan vigente o abre el nuevo. Idempotente."""
    with transaction.atomic():
        payment = (
            SubscriptionPayment.objects.select_for_update()
            .select_related("plan", "plan__currency", "tenant")
            .filter(provider=gateway.PROVIDER, reference=session_id)
            .first()
        )
        if payment is None or payment.status == SubscriptionPayment.State.APPROVED:
            return payment
        current = (
            Subscription.objects.select_for_update()
            .filter(tenant_id=payment.tenant_id, status=Subscription.Status.ACTIVE)
            .first()
        )
        if current is not None and current.plan_id == payment.plan_id:
            _extend(current, payment.plan)
            subscription = current
        else:
            from .services import _open_subscription

            subscription = _open_subscription(
                tenant=payment.tenant, plan=payment.plan, auto_renew=bool(current and current.auto_renew)
            )
        payment.status = SubscriptionPayment.State.APPROVED
        payment.processed_at = timezone.now()
        payment.subscription = subscription
        payment.save(update_fields=["status", "processed_at", "subscription"])
        record_audit(
            actor=payment.payer, tenant_id=payment.tenant_id, action="RENOVAR_PLAN", entity="suscripcion",
            entity_id=str(subscription.id),
            new_data={"plan": payment.plan.code, "vence": subscription.end_date.isoformat(), "pago": payment.id},
        )
        transaction.on_commit(lambda: notify_owners(subscription, "PAGADA"))
    return payment


def void_payment(session_id: str) -> None:
    SubscriptionPayment.objects.filter(
        provider=gateway.PROVIDER, reference=session_id, status=SubscriptionPayment.State.PENDING
    ).update(status=SubscriptionPayment.State.VOIDED, processed_at=timezone.now())


def sync_pending_payments(tenant_id: int) -> None:
    """Si el webhook no llego, pregunta a Stripe por los pagos abiertos."""
    for payment in SubscriptionPayment.objects.filter(
        tenant_id=tenant_id, status=SubscriptionPayment.State.PENDING
    ).exclude(reference=None):
        session = gateway.retrieve_session(payment.reference)
        if session is None:
            continue
        if session.paid:
            confirm_payment(session.id)
        elif session.status == "expired":
            void_payment(session.id)


# --- Correos -----------------------------------------------------------------------


def _day(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def notify_owners(subscription: Subscription, kind: str, *, days_left: int | None = None) -> int:
    """Correo al propietario: AVISO (por vencer), VENCIDA, RENOVADA o PAGADA."""
    subscription = Subscription.objects.select_related("tenant", "plan").get(id=subscription.id)
    company = escape(subscription.tenant.trade_name)
    plan = escape(subscription.plan.name)
    end = _day(subscription.end_date) if subscription.end_date else ""
    panel = f"{settings.WEB_APP_URL.rstrip('/')}/mi-plan"
    if kind == "AVISO":
        when = "mañana" if days_left == 1 else f"en {days_left} días"
        subject = f"Tu plan {subscription.plan.name} vence {when} - SITUR-SMART"
        body = (
            f"<p>El plan <strong>{plan}</strong> de <strong>{company}</strong> vence {when} ({end}).</p>"
            "<p>Si no se renueva, tus productos dejarán de mostrarse en el Marketplace y no podrás "
            "crear ni publicar oferta hasta renovarlo.</p>"
        )
    elif kind == "VENCIDA":
        subject = f"Tu plan {subscription.plan.name} venció - SITUR-SMART"
        body = (
            f"<p>El plan <strong>{plan}</strong> de <strong>{company}</strong> venció el {end}.</p>"
            "<p>Tus productos ya no se muestran en el Marketplace y no puedes crear ni publicar oferta. "
            "Las reservas ya pagadas se mantienen. Renueva el plan para volver a vender.</p>"
        )
    elif kind == "RENOVADA":
        subject = f"Tu plan {subscription.plan.name} se renovó - SITUR-SMART"
        body = f"<p>El plan <strong>{plan}</strong> de <strong>{company}</strong> se renovó automáticamente hasta el {end}.</p>"
    else:
        subject = "Recibimos el pago de tu plan - SITUR-SMART"
        body = f"<p>Gracias. El plan <strong>{plan}</strong> de <strong>{company}</strong> está vigente hasta el {end}.</p>"
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:520px;color:#0f172a">'
        f'<h2 style="color:#0f766e">SITUR-SMART</h2>{body}'
        f'<p><a href="{escape(panel)}" style="display:inline-block;padding:10px 18px;background:#0f766e;'
        'color:#fff;border-radius:8px;text-decoration:none;font-weight:600">Ver Mi plan</a></p></div>'
    )
    sent = 0
    for user in User.objects.filter(id__in=_owner_ids(subscription.tenant_id), status=User.Status.ACTIVE):
        if send_email(to_email=user.email, to_name=user.get_full_name(), subject=subject, html=html):
            sent += 1
    return sent
