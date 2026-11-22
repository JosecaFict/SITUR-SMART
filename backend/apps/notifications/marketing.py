"""Consentimiento y presupuesto de frecuencia compartidos por campañas y ofertas."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.models import User
from apps.bookings.models import Booking
from apps.tenancy.models import Tenant, UserTenant

from .models import CommunicationPreference, Notification

PROMOTIONAL_KINDS = Q(kind="OFERTA_INTERES") | Q(kind="COMUNICACION", data__tipo_comunicacion="PROMOCIONAL")


def limits():
    return {"por_empresa_24h": max(1, int(getattr(settings, "COMMUNICATION_PROMOTIONS_PER_SENDER", 1))),
            "total_24h": max(1, int(getattr(settings, "COMMUNICATION_PROMOTIONS_PER_DAY", 3)))}


def eligible_ids(user_ids, tenant_id, *, check_frequency=True):
    ids = set(CommunicationPreference.objects.filter(
        user_id__in=user_ids, tenant_id=tenant_id, promotions_enabled=True,
    ).values_list("user_id", flat=True))
    if not ids or not check_frequency:
        return ids
    recent = Notification.objects.filter(PROMOTIONAL_KINDS, user_id__in=ids,
                                         created_at__gte=timezone.now() - timedelta(hours=24))
    caps = limits()
    blocked = set(recent.values("user_id").annotate(total=Count("id"))
                  .filter(total__gte=caps["total_24h"]).values_list("user_id", flat=True))
    sender = recent.filter(data__empresa_id=tenant_id) if tenant_id is not None else recent.filter(data__empresa_id__isnull=True)
    blocked.update(sender.values("user_id").annotate(total=Count("id"))
                   .filter(total__gte=caps["por_empresa_24h"]).values_list("user_id", flat=True))
    return ids - blocked


def related_companies(user):
    memberships = UserTenant.objects.filter(user=user, status=UserTenant.Status.ACTIVE).values("tenant_id")
    bookings = Booking.objects.filter(order__customer_id=user.id).values("tenant_id")
    # Keep previously saved preferences visible so unsubscribing is always possible.
    preferences = CommunicationPreference.objects.filter(user=user, tenant__isnull=False).values("tenant_id")
    return Tenant.objects.filter(Q(pk__in=memberships) | Q(pk__in=bookings) | Q(pk__in=preferences)).order_by("trade_name")


def preferences_for(user):
    stored = dict(CommunicationPreference.objects.filter(user=user).values_list("tenant_id", "promotions_enabled"))
    return {"preferencias": [{"empresa_id": None, "nombre": "SITUR-SMART", "promociones": stored.get(None, False)},
                             *[{"empresa_id": t.id, "nombre": t.trade_name, "promociones": stored.get(t.id, False)}
                               for t in related_companies(user)]], "limites": limits()}


@transaction.atomic
def set_preference(user, tenant_id, enabled):
    # Same lock as publication: unsubscribe and frequency accounting are serialized per user.
    User.objects.select_for_update().get(pk=user.pk)
    if tenant_id is not None and not related_companies(user).filter(pk=tenant_id).exists():
        raise NotFound("La empresa no está vinculada a tu cuenta.")
    CommunicationPreference.objects.update_or_create(user=user, tenant_id=tenant_id,
                                                      defaults={"promotions_enabled": enabled})
    return preferences_for(user)


def suppression_reason(notification):
    """Revalidated immediately before push, not only at the time of publication."""
    data = notification.data or {}
    expires = data.get("vence_en")
    if expires:
        from django.utils.dateparse import parse_datetime
        deadline = parse_datetime(expires)
        if deadline is not None and deadline <= timezone.now():
            return "VENCIDO"
    if data.get("tipo_comunicacion") == "PROMOCIONAL" or notification.kind == "OFERTA_INTERES":
        if not User.objects.filter(pk=notification.user_id, status=User.Status.ACTIVE).exists():
            return "OMITIDO"
        if not CommunicationPreference.objects.filter(user_id=notification.user_id,
                tenant_id=data.get("empresa_id"), promotions_enabled=True).exists():
            return "DESUSCRITO"
        if data.get("promocion_id"):
            from apps.promotions.models import Promotion
            if not Promotion.objects.filter(pk=data["promocion_id"], administrative_status="HABILITADA",
                                            ends_at__gt=timezone.now(), tenant__status="ACTIVO").exists():
                return "VENCIDO"
    return None
