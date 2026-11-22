"""Programación persistente con audiencia congelada y comprobaciones al despachar."""

import logging

from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from apps.accounts.models import User
from apps.audit.services import record_audit
from apps.promotions.models import Promotion

from . import marketing
from .email_content import personalize
from .models import (
    Communication,
    CommunicationDelivery,
    CommunicationEmail,
    Notification,
)

logger = logging.getLogger(__name__)


def validate_campaign(payload, tenant_id, *, dispatch=False):
    now = timezone.now()
    scheduled, expiry = payload.get("programado_en"), payload.get("vence_en")
    if scheduled and not dispatch and scheduled <= now:
        raise ValidationError({"programado_en": "Selecciona una fecha y hora futura."})
    effective = max(now, scheduled) if scheduled else now
    if expiry and expiry <= effective:
        raise ValidationError({"vence_en": "El vencimiento debe ser posterior al envío."})
    promotional = payload["tipo"] == Communication.Kind.PROMOTIONAL
    if promotional and not expiry:
        raise ValidationError({"vence_en": "Una campaña promocional requiere fecha de vencimiento."})
    promotion_id = payload.get("promocion_id")
    if promotion_id:
        if not promotional:
            raise ValidationError({"promocion_id": "Vincula ofertas solo a comunicaciones promocionales."})
        query = Promotion.objects.filter(pk=promotion_id)
        if tenant_id is not None:
            query = query.filter(tenant_id=tenant_id)
        promotion = query.first()
        if promotion is None:
            raise ValidationError({"promocion_id": "La promoción no pertenece al alcance seleccionado."})
        if promotion.state_at() not in ("VIGENTE", "PROGRAMADA") or not promotion.tenant.status == "ACTIVO":
            raise ValidationError({"promocion_id": "La promoción no está disponible."})
        if effective < promotion.starts_at or effective >= promotion.ends_at or expiry > promotion.ends_at:
            raise ValidationError({"vence_en": "El envío y el vencimiento deben estar dentro de la vigencia de la oferta."})


def prepare_schedule(item, ids):
    item.state = Communication.State.SCHEDULED
    item.email_enabled = True
    item.save(update_fields=("sender_name", "state", "email_enabled", "updated_at"))
    CommunicationDelivery.objects.bulk_create([
        CommunicationDelivery(communication=item, user_id=uid, push_status="PROGRAMADO", next_attempt_at=item.scheduled_at)
        for uid in ids
    ], batch_size=500)


def deliver(item, ids, *, scheduled=False):
    # Serialize quota accounting with other manual/automatic campaigns and preference changes.
    users = list(User.objects.filter(pk__in=ids).order_by("id").select_for_update())
    users_by_id = {user.pk: user for user in users}
    allowed = {u.pk for u in users if u.status == User.Status.ACTIVE}
    if item.kind == Communication.Kind.PROMOTIONAL:
        allowed &= marketing.eligible_ids(ids, item.tenant_id)
    item.state, item.published_at = Communication.State.PUBLISHED, timezone.now()
    item.email_enabled = True
    item.save(update_fields=("state", "published_at", "sender_name", "email_enabled", "updated_at"))
    reason = {
        "INTERNA": "Eres parte del personal destinatario de este aviso.",
        "OPERATIVA": "Estás vinculado a la audiencia de este aviso operativo.",
        "PROMOCIONAL": "Aceptaste recibir promociones de este remitente.",
    }[item.kind]
    notifications = []
    for uid in sorted(allowed):
        data = {"comunicacion_id": item.pk, "remitente": item.sender_name, "empresa_id": item.tenant_id,
                "motivo": reason, "tipo_comunicacion": item.kind, "ruta": "/notificaciones"}
        if item.expires_at:
            data["vence_en"] = item.expires_at.isoformat()
        if item.promotion_id:
            data["promocion_id"] = item.promotion_id
        if item.booking_id:
            data["reserva_id"] = item.booking_id
        user = users_by_id[uid]
        notifications.append(Notification(user_id=uid, kind="COMUNICACION", title=personalize(item.title, user, item.sender_name)[:150],
                                          message=personalize(item.message, user, item.sender_name), data=data))
    Notification.objects.bulk_create(notifications, batch_size=500)
    if scheduled:
        existing = {d.user_id: d for d in item.deliveries.all()}
        for notice in notifications:
            row = existing[notice.user_id]
            row.notification, row.push_status, row.next_attempt_at = notice, "PENDIENTE", timezone.now()
        for uid, row in existing.items():
            if uid not in allowed:
                row.push_status, row.last_error = "OMITIDO", "NOT_ELIGIBLE"
        CommunicationDelivery.objects.bulk_update(list(existing.values()),
            ("notification", "push_status", "next_attempt_at", "last_error"), batch_size=500)
    else:
        notices = {n.user_id: n for n in notifications}
        CommunicationDelivery.objects.bulk_create([
            CommunicationDelivery(communication=item, user_id=uid, notification=notices.get(uid),
                                  next_attempt_at=item.published_at,
                                  push_status="PENDIENTE" if uid in allowed else "OMITIDO") for uid in ids
        ], batch_size=500)
    addresses = {user.pk: user.email for user in users}
    CommunicationEmail.objects.bulk_create([
        CommunicationEmail(delivery=row, recipient_email=addresses[row.user_id], next_attempt_at=item.published_at)
        for row in item.deliveries.filter(user_id__in=allowed, notification__isnull=False)
    ], batch_size=500)


@transaction.atomic
def cancel(actor, tenant_id, communication_id, request=None):
    from .communications import get
    item = get(actor, tenant_id, communication_id, lock=True)
    if item.state == Communication.State.CANCELLED:
        return item
    if item.state not in (Communication.State.SCHEDULED, Communication.State.DRAFT, Communication.State.REVIEW):
        raise ValidationError("Solo puedes cancelar borradores o comunicaciones pendientes de envío.")
    item.state = Communication.State.CANCELLED
    item.save(update_fields=("state", "updated_at"))
    item.deliveries.filter(push_status="PROGRAMADO").update(push_status="OMITIDO", last_error="CANCELLED")
    record_audit(actor=actor, tenant_id=tenant_id, action="CANCELAR", entity="comunicacion",
                 entity_id=str(item.pk), request=request)
    return item


def process_due_campaigns(limit=100):
    from .communications import authorize, payload_for, resolve
    candidates = list(Communication.objects.filter(state=Communication.State.SCHEDULED,
                       scheduled_at__lte=timezone.now()).order_by("scheduled_at", "pk").values_list("pk", flat=True)[:limit])
    processed = 0
    for pk in candidates:
        with transaction.atomic():
            query = Communication.objects.select_for_update(skip_locked=connection.vendor == "postgresql")
            item = query.filter(pk=pk, state=Communication.State.SCHEDULED).first()
            if item is None:
                continue
            processed += 1
            if item.expires_at and item.expires_at <= timezone.now():
                item.state = Communication.State.EXPIRED
                item.save(update_fields=("state", "updated_at"))
                item.deliveries.update(push_status="VENCIDO", last_error="EXPIRED")
                continue
            try:
                with transaction.atomic():
                    authorize(item.author, item.tenant_id)
                    payload = payload_for(item)
                    validate_campaign(payload, item.tenant_id, dispatch=True)
                    audience = {**payload["audiencia"], "usuario_ids": []}
                    if audience.get("grupo") == "USUARIOS":
                        audience["grupo"] = "TODOS"
                    ids = list(item.deliveries.values_list("user_id", flat=True))
                    eligible = set(resolve(item.author, item.tenant_id, {**payload, "audiencia": audience})
                                   .filter(pk__in=ids).values_list("pk", flat=True))
                    # Never add people who were not included in the reviewed snapshot.
                    deliver(item, sorted(set(ids) & eligible), scheduled=True)
                    record_audit(actor=item.author, tenant_id=item.tenant_id, action="PUBLICAR", entity="comunicacion",
                                 entity_id=str(item.pk), new_data={"programada": True})
            except APIException:
                item.refresh_from_db()
                item.state, item.dispatch_error = Communication.State.REVIEW, "Revisa permisos, audiencia y vigencia antes de crear un nuevo envío."
                item.save(update_fields=("state", "dispatch_error", "updated_at"))
                logger.warning("Scheduled communication %s requires review", pk)
    return processed
