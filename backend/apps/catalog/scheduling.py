"""Publicacion programada de productos y hospedajes.

La empresa elige "Publicar el ..." y/o "Retirar el ..." en la web. El cron
(``tareas_programadas``, cada 10 minutos) llama a ``process_due``: publica lo
que llego a su hora revisando las mismas reglas que una publicacion a mano (un
hotel necesita una habitacion con precio; una empresa con el plan vencido no
publica), retira lo que vencio y avisa por correo al propietario. Todo queda en
la bitacora como accion automatica.
"""

import logging
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.html import escape
from rest_framework.exceptions import NotFound, ValidationError

from apps.accounts.brevo import send_email
from apps.accounts.models import User
from apps.audit.services import record_audit
from apps.rbac.services import require_permission, require_tenant_access
from apps.tenancy.subscriptions import is_restricted, owner_ids, require_active_plan

from .models import ROOM_PRODUCT_CODE, LodgingEstablishment, TourismProduct

logger = logging.getLogger(__name__)


def _product(tenant_id: int, product_id: int) -> TourismProduct:
    product = TourismProduct.objects.select_related("product_type").filter(tenant_id=tenant_id, id=product_id).first()
    if product is None:
        raise NotFound("Producto no encontrado en esta empresa.")
    return product


def set_schedule(
    *, actor, tenant_id: int, product_id: int, publish_at: datetime | None, unpublish_at: datetime | None, request=None
) -> TourismProduct:
    """Programa (o quita, con None) la publicacion y el retiro de un producto o un hotel."""
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "PRODUCTOS_GESTIONAR", tenant_id)
    require_active_plan(actor, tenant_id)
    product = _product(tenant_id, product_id)
    if product.product_type.code == ROOM_PRODUCT_CODE:
        raise ValidationError({"publicar_en": "Las habitaciones se publican con su hospedaje: programa el hospedaje."})
    now = timezone.now()
    if publish_at is not None:
        if publish_at <= now:
            raise ValidationError({"publicar_en": "Elige una fecha y hora futuras."})
        if product.status == TourismProduct.Status.PUBLISHED:
            raise ValidationError({"publicar_en": "Ya está publicado. Puedes programar solo su retiro."})
    if unpublish_at is not None:
        if unpublish_at <= now:
            raise ValidationError({"retirar_en": "Elige una fecha y hora futuras."})
        if publish_at is not None and unpublish_at <= publish_at:
            raise ValidationError({"retirar_en": "El retiro tiene que ser después de la publicación."})
        if publish_at is None and product.status != TourismProduct.Status.PUBLISHED:
            raise ValidationError({"retirar_en": "Solo se programa el retiro de algo publicado o que se va a publicar."})
    previous = {"publicar_en": _iso(product.publish_at), "retirar_en": _iso(product.unpublish_at)}
    product.publish_at = publish_at
    product.unpublish_at = unpublish_at
    product.save(update_fields=["publish_at", "unpublish_at", "updated_at"])
    record_audit(
        actor=actor, tenant_id=tenant_id, action="PROGRAMAR_PUBLICACION", entity="producto_turistico",
        entity_id=str(product.id), previous_data=previous,
        new_data={"publicar_en": _iso(publish_at), "retirar_en": _iso(unpublish_at)}, request=request,
    )
    return product


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _publish_problem(product: TourismProduct) -> str | None:
    """Por que no se puede publicar ahora, o None si se puede."""
    from .services import _has_publishable_room

    if product.tenant.status != "ACTIVO":
        return "la empresa no está activa"
    if is_restricted(product.tenant_id):
        return "el plan de la empresa venció"
    lodging = LodgingEstablishment.objects.filter(product_id=product.id).first()
    if lodging is not None and not _has_publishable_room(lodging.id):
        return "el hospedaje no tiene ninguna habitación publicada con precio"
    if lodging is None and product.base_price <= 0:
        return "el producto no tiene precio"
    return None


def process_due(now: datetime | None = None) -> dict:
    """Publica y retira lo que llego a su hora. Idempotente: corre cada pocos minutos."""
    now = now or timezone.now()
    counts = {"publicados": 0, "retirados": 0, "fallidos": 0}

    due = TourismProduct.objects.select_related("tenant").filter(publish_at__lte=now)
    for product in due:
        with transaction.atomic():
            locked = TourismProduct.objects.select_for_update().select_related("tenant").get(id=product.id)
            if locked.publish_at is None or locked.publish_at > now:
                continue
            problem = _publish_problem(locked)
            locked.publish_at = None
            if problem is None:
                locked.status = TourismProduct.Status.PUBLISHED
                locked.auto_published_at = now
                locked.save(update_fields=["status", "publish_at", "auto_published_at", "updated_at"])
                record_audit(
                    actor=None, tenant_id=locked.tenant_id, action="PUBLICACION_AUTOMATICA",
                    entity="producto_turistico", entity_id=str(locked.id), new_data={"nombre": locked.name},
                )
                counts["publicados"] += 1
            else:
                locked.save(update_fields=["publish_at", "updated_at"])
                record_audit(
                    actor=None, tenant_id=locked.tenant_id, action="PUBLICACION_AUTOMATICA_FALLIDA",
                    entity="producto_turistico", entity_id=str(locked.id), new_data={"motivo": problem},
                )
                counts["fallidos"] += 1
        _notify(locked, "PUBLICADO" if problem is None else "FALLIDO", problem)

    expiring = TourismProduct.objects.select_related("tenant").filter(unpublish_at__lte=now)
    for product in expiring:
        with transaction.atomic():
            locked = TourismProduct.objects.select_for_update().select_related("tenant").get(id=product.id)
            if locked.unpublish_at is None or locked.unpublish_at > now:
                continue
            locked.unpublish_at = None
            withdrawn = locked.status == TourismProduct.Status.PUBLISHED
            if withdrawn:
                locked.status = TourismProduct.Status.INACTIVE
            locked.save(update_fields=["status", "unpublish_at", "updated_at"])
            if withdrawn:
                record_audit(
                    actor=None, tenant_id=locked.tenant_id, action="RETIRO_AUTOMATICO",
                    entity="producto_turistico", entity_id=str(locked.id), new_data={"nombre": locked.name},
                )
                counts["retirados"] += 1
        if withdrawn:
            _notify(locked, "RETIRADO")
    return counts


def _notify(product: TourismProduct, kind: str, problem: str | None = None) -> None:
    name = escape(product.name)
    panel = f"{settings.WEB_APP_URL.rstrip('/')}/productos"
    if kind == "PUBLICADO":
        subject = f"{product.name} ya está publicado - SITUR-SMART"
        body = f"<p><strong>{name}</strong> se publicó automáticamente, como lo programaste. Ya aparece en el Marketplace.</p>"
    elif kind == "RETIRADO":
        subject = f"{product.name} se retiró del Marketplace - SITUR-SMART"
        body = f"<p><strong>{name}</strong> se retiró automáticamente, como lo programaste. Las reservas ya pagadas se mantienen.</p>"
    else:
        subject = f"No se pudo publicar {product.name} - SITUR-SMART"
        body = (
            f"<p>La publicación programada de <strong>{name}</strong> no se hizo porque {escape(problem or '')}.</p>"
            "<p>Quedó en borrador. Corrígelo y vuelve a programarlo o publícalo a mano.</p>"
        )
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:520px;color:#0f172a">'
        f'<h2 style="color:#0f766e">SITUR-SMART</h2>{body}<p><a href="{escape(panel)}">Ver mi catálogo</a></p></div>'
    )
    for user in User.objects.filter(id__in=owner_ids(product.tenant_id), status=User.Status.ACTIVE):
        if not send_email(to_email=user.email, to_name=user.get_full_name(), subject=subject, html=html):
            logger.info("No se envió el aviso de publicación programada a %s", user.email)
