"""Audiencias verificadas y publicación atómica, sin llamadas a Firebase."""

import json
from collections import Counter
from datetime import UTC, datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)

from apps.accounts.models import User
from apps.audit.services import record_audit
from apps.bookings.models import Booking, BookingState
from apps.catalog.models import Availability
from apps.rbac.models import Role, UserRole
from apps.rbac.services import is_superadmin, require_permission, require_tenant_access
from apps.tenancy.models import Tenant, UserTenant

from . import marketing
from .models import Communication

PERMISSION = "COMUNICACIONES_GESTIONAR"
MAX_RECIPIENTS = 10000
GROUPS = {"TODOS", "PERSONAL", "CLIENTES", "PROPIETARIOS", "EMPLEADOS", "USUARIOS"}
CUSTOMER_STATES = (BookingState.CREATED, BookingState.PARTIAL, BookingState.CONFIRMED, BookingState.COMPLETED)


class AudienceChanged(APIException):
    status_code = 409
    default_detail = "La comunicación o los destinatarios cambiaron. Revisa nuevamente la audiencia."


def authorize(actor, tenant_id):
    if getattr(actor, "status", User.Status.ACTIVE) != User.Status.ACTIVE:
        raise PermissionDenied("La cuenta remitente no está activa.")
    if tenant_id is None:
        if not is_superadmin(actor):
            raise PermissionDenied("Solo el SuperAdmin puede publicar comunicaciones de plataforma.")
    else:
        require_tenant_access(actor, tenant_id)
        owner = UserRole.objects.filter(
            user=actor, tenant_id=tenant_id, role__code="TENANT_ADMIN", role__scope=Role.Scope.TENANT,
        ).exists()
        if not owner:
            require_permission(actor, PERMISSION, tenant_id)


def scoped(actor, tenant_id):
    authorize(actor, tenant_id)
    return Communication.objects.filter(tenant_id=tenant_id).select_related("tenant", "author", "booking")


def get(actor, tenant_id, communication_id, *, lock=False):
    query = scoped(actor, tenant_id)
    if lock:
        query = query.select_related(None).select_for_update()
    item = query.filter(pk=communication_id).first()
    if item is None:
        raise NotFound("Comunicación no encontrada en este contexto.")
    return item


def _ids(audience, key):
    values = audience.get(key, [])
    if not isinstance(values, list) or len(values) > MAX_RECIPIENTS:
        raise ValidationError({"audiencia": f"Lista inválida: {key}."})
    if any(type(value) is not int or value <= 0 for value in values):
        raise ValidationError({"audiencia": f"Identificadores inválidos: {key}."})
    return sorted(set(values))


def resolve(actor, tenant_id, payload):
    authorize(actor, tenant_id)
    audience = payload["audiencia"]
    group = audience.get("grupo", "TODOS")
    if group not in GROUPS:
        raise ValidationError({"audiencia": "Grupo de destinatarios inválido."})
    company_ids = _ids(audience, "empresa_ids")
    role_ids = _ids(audience, "rol_ids")
    user_ids = _ids(audience, "usuario_ids")
    if tenant_id is not None:
        if company_ids and company_ids != [tenant_id]:
            raise PermissionDenied("No puedes contactar usuarios de otra empresa.")
        company_ids = [tenant_id]
    elif company_ids and Tenant.objects.filter(id__in=company_ids).count() != len(company_ids):
        raise ValidationError({"audiencia": "Una empresa seleccionada no existe."})
    members = UserTenant.objects.filter(status=UserTenant.Status.ACTIVE)
    bookings = Booking.objects.filter(status__in=CUSTOMER_STATES)
    assignments = UserRole.objects.all()
    if company_ids:
        members = members.filter(tenant_id__in=company_ids)
        bookings = bookings.filter(tenant_id__in=company_ids)
        assignments = assignments.filter(tenant_id__in=company_ids)
    staff = Q(pk__in=members.values("user_id"))
    if not company_ids:
        staff |= Q(pk__in=assignments.filter(tenant__isnull=True, role__scope=Role.Scope.GLOBAL)
                   .exclude(role__code="CLIENTE").values("user_id"))
    customers = Q(pk__in=bookings.values("order__customer_id")) if company_ids else Q(customer_profile__isnull=False)
    owners = Q(pk__in=assignments.filter(role__code="TENANT_ADMIN", role__scope=Role.Scope.TENANT).values("user_id"))
    internal = payload["tipo"] == Communication.Kind.INTERNAL
    base = staff if internal else staff | customers
    if tenant_id is None and not company_ids and not internal and group in {"TODOS", "USUARIOS"}:
        # Platform notices include active accounts even before their first booking or assignment.
        base = Q()
    if group == "CLIENTES":
        if internal:
            raise ValidationError({"tipo": "Los avisos internos son exclusivamente para el personal."})
        base &= customers
    elif group == "PERSONAL":
        base &= staff
    elif group == "PROPIETARIOS":
        base &= staff & owners
    elif group == "EMPLEADOS":
        base &= staff & ~owners
    elif group == "USUARIOS" and not user_ids:
        raise ValidationError({"audiencia": "Selecciona al menos una persona."})
    if role_ids:
        roles = Role.objects.filter(pk__in=role_ids)
        if company_ids:
            roles = roles.filter(scope=Role.Scope.TENANT).filter(Q(tenant_id__isnull=True) | Q(tenant_id__in=company_ids))
        if roles.count() != len(role_ids):
            raise PermissionDenied("Uno de los roles no pertenece al alcance seleccionado.")
        base &= Q(pk__in=assignments.filter(role_id__in=role_ids).values("user_id"))
    booking_id = audience.get("reserva_id") or payload.get("reserva_id")
    slot_id = audience.get("salida_id")
    if booking_id or slot_id:
        if internal:
            raise ValidationError({"audiencia": "Una audiencia de reservas corresponde a avisos operativos."})
        if booking_id:
            if type(booking_id) is not int or booking_id <= 0:
                raise ValidationError({"audiencia": "Reserva inválida."})
            if not bookings.filter(pk=booking_id).exists():
                raise ValidationError({"audiencia": "Reserva fuera del alcance o sin destinatarios activos."})
            bookings = bookings.filter(pk=booking_id)
        if slot_id:
            if type(slot_id) is not int or slot_id <= 0:
                raise ValidationError({"audiencia": "Salida inválida."})
            slots = Availability.objects.filter(pk=slot_id)
            if company_ids:
                slots = slots.filter(tenant_id__in=company_ids)
            if not slots.exists():
                raise PermissionDenied("La salida no pertenece al alcance seleccionado.")
            bookings = bookings.filter(details__slot_id=slot_id)
        base &= Q(pk__in=bookings.values("order__customer_id"))
    users = User.objects.filter(status=User.Status.ACTIVE).filter(base).distinct()
    if user_ids:
        allowed = set(users.filter(pk__in=user_ids).values_list("id", flat=True))
        if allowed != set(user_ids):
            raise PermissionDenied("Uno o más destinatarios no están autorizados en esta audiencia.")
        users = users.filter(pk__in=user_ids)
    return users.order_by("id")


def preview(actor, tenant_id, payload):
    from .campaigns import validate_campaign
    users_query = resolve(actor, tenant_id, payload)
    validate_campaign(payload, tenant_id)
    users = list(users_query.values("id", "first_names", "last_names", "email")[:MAX_RECIPIENTS + 1])
    if len(users) > MAX_RECIPIENTS:
        raise ValidationError(f"Máximo {MAX_RECIPIENTS} destinatarios por publicación; segmenta la audiencia.")
    excluded = 0
    if payload["tipo"] == Communication.Kind.PROMOTIONAL:
        allowed = marketing.eligible_ids([u["id"] for u in users], tenant_id,
                                         check_frequency=payload.get("programado_en") is None)
        excluded = sum(u["id"] not in allowed for u in users)
        users = [u for u in users if u["id"] in allowed]
    def canonical_date(value):
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat()
        raise TypeError("Dato no serializable en la comunicación.")
    canonical = json.dumps({"contexto": tenant_id, "contenido": payload, "usuarios": [u["id"] for u in users]},
                           sort_keys=True, default=canonical_date)
    fingerprint = salted_hmac("comunicacion.audiencia", canonical, algorithm="sha256").hexdigest()
    return {"total": len(users), "huella": fingerprint, "excluidos_promociones": excluded,
            "destinatarios": [{"id": u["id"], "nombre": f'{u["first_names"]} {u["last_names"]}'.strip(),
                               "email": u["email"]} for u in users]}


def payload_for(item):
    return {"titulo": item.title, "mensaje": item.message, "tipo": item.kind,
            "audiencia": item.audience, "reserva_id": item.booking_id,
            "programado_en": item.scheduled_at, "vence_en": item.expires_at, "promocion_id": item.promotion_id,
            "enviar_correo": item.email_enabled or item.state in (Communication.State.DRAFT, Communication.State.SCHEDULED)}


@transaction.atomic
def save(actor, tenant_id, payload, *, communication_id=None, request=None):
    from .campaigns import validate_campaign
    resolve(actor, tenant_id, payload)
    validate_campaign(payload, tenant_id)
    booking_id = payload.get("reserva_id")
    if booking_id and payload["audiencia"].get("reserva_id") not in (None, booking_id):
        raise ValidationError({"reserva_id": "La reserva y la audiencia deben coincidir."})
    item = get(actor, tenant_id, communication_id, lock=True) if communication_id else Communication(tenant_id=tenant_id, author=actor)
    if item.state != Communication.State.DRAFT:
        raise ValidationError("Una comunicación publicada no puede modificarse.")
    item.title, item.message, item.kind = payload["titulo"], payload["mensaje"], payload["tipo"]
    item.audience, item.booking_id = payload["audiencia"], booking_id
    item.scheduled_at, item.expires_at = payload.get("programado_en"), payload.get("vence_en")
    item.promotion_id = payload.get("promocion_id")
    item.email_enabled = True
    item.save()
    record_audit(actor=actor, tenant_id=tenant_id, action="ACTUALIZAR" if communication_id else "CREAR",
                 entity="comunicacion", entity_id=str(item.id), new_data={"estado": item.state}, request=request)
    return item


@transaction.atomic
def publish(actor, tenant_id, communication_id, fingerprint, request=None):
    from .campaigns import deliver, prepare_schedule
    item = get(actor, tenant_id, communication_id, lock=True)
    if item.state in (Communication.State.PUBLISHED, Communication.State.SCHEDULED):
        return item
    if item.state != Communication.State.DRAFT:
        raise ValidationError("Esta comunicación ya no puede publicarse.")
    audience = preview(actor, tenant_id, payload_for(item))
    if not constant_time_compare(audience["huella"], fingerprint):
        raise AudienceChanged()
    if not audience["total"]:
        raise ValidationError("La audiencia no tiene destinatarios habilitados.")
    item.sender_name = item.tenant.trade_name if tenant_id else "SITUR-SMART"
    ids = [user["id"] for user in audience["destinatarios"]]
    if item.scheduled_at:
        prepare_schedule(item, ids)
    else:
        deliver(item, ids)
    record_audit(actor=actor, tenant_id=tenant_id, action="PROGRAMAR" if item.scheduled_at else "PUBLICAR",
                 entity="comunicacion", entity_id=str(item.id),
                 new_data={"destinatarios": audience["total"], "tipo": item.kind}, request=request)
    return item


def as_dict(item):
    from .models import CommunicationEmail
    counts = Counter(item.deliveries.values_list("push_status", flat=True))
    email_counts = Counter(CommunicationEmail.objects.filter(delivery__communication=item).values_list("status", flat=True))
    return {"id": item.id, **payload_for(item), "estado": item.state,
            "remitente": item.sender_name or (item.tenant.trade_name if item.tenant_id else "SITUR-SMART"),
            "creado_en": item.created_at, "publicado_en": item.published_at,
            "total_destinatarios": sum(counts.values()),
            "leidas": item.deliveries.filter(notification__read_at__isnull=False).count(),
            "push_pendientes": counts["PENDIENTE"], "push_aceptados": counts["ACEPTADO"],
            "push_fallidos": counts["FALLIDO"], "sin_dispositivo": counts["SIN_DISPOSITIVO"],
            "programados": counts["PROGRAMADO"], "omitidos": counts["OMITIDO"] + counts["DESUSCRITO"] + counts["VENCIDO"],
            "error_envio": item.dispatch_error,
            "vencida": bool(item.expires_at and item.expires_at <= timezone.now()),
            "correos_pendientes": email_counts["PENDIENTE"], "correos_aceptados": email_counts["ACEPTADO"],
            "correos_fallidos": email_counts["FALLIDO"], "correos_omitidos": email_counts["OMITIDO"],
            "correos_revision": email_counts["REVISION"]}
