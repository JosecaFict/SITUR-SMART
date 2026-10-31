"""Guias de una empresa (CU20).

Un guia se asigna a las salidas de los tours. Las reglas que importan:

* el guia y la salida son de la misma empresa (tambien lo obliga la FK
  compuesta fk_disponibilidad_guia_tenant);
* un guia inactivo no se asigna a salidas nuevas;
* un guia no puede estar en dos salidas abiertas que se cruzan en horario.
"""

from datetime import datetime

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit.services import record_audit
from apps.rbac.services import require_permission, require_tenant_access

from .models import Availability, Guide

_GUIDE_FIELDS = {"nombres": "names", "telefono": "phone", "idiomas": "languages", "estado": "status"}


def _guide_values(data: dict) -> dict:
    return {_GUIDE_FIELDS[key]: value for key, value in data.items() if key in _GUIDE_FIELDS}


def list_guides(*, actor, tenant_id: int):
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "PRODUCTOS_LEER", tenant_id)
    return Guide.objects.filter(tenant_id=tenant_id)


def get_company_guide(*, actor, tenant_id: int, guide_id: int) -> Guide:
    guide = list_guides(actor=actor, tenant_id=tenant_id).filter(id=guide_id).first()
    if guide is None:
        raise NotFound("Guía no encontrado en esta empresa.")
    return guide


@transaction.atomic
def create_guide(*, actor, tenant_id: int, request=None, **data) -> Guide:
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "PRODUCTOS_GESTIONAR", tenant_id)
    guide = Guide.objects.create(tenant_id=tenant_id, **_guide_values(data))
    record_audit(
        actor=actor, tenant_id=tenant_id, action="CREAR", entity="guia",
        entity_id=str(guide.id), new_data={"nombres": guide.names}, request=request,
    )
    return guide


@transaction.atomic
def update_guide(*, actor, tenant_id: int, guide_id: int, request=None, **data) -> Guide:
    guide = get_company_guide(actor=actor, tenant_id=tenant_id, guide_id=guide_id)
    require_permission(actor, "PRODUCTOS_GESTIONAR", tenant_id)
    values = _guide_values(data)
    if values.get("status") == Guide.Status.INACTIVE and guide.is_active:
        _check_can_deactivate(guide)
    previous = {"nombres": guide.names, "estado": guide.status}
    for field, value in values.items():
        setattr(guide, field, value)
    if values:
        guide.save(update_fields=[*values.keys(), "updated_at"])
    record_audit(
        actor=actor, tenant_id=tenant_id, action="ACTUALIZAR", entity="guia",
        entity_id=str(guide.id), previous_data=previous,
        new_data={"nombres": guide.names, "estado": guide.status}, request=request,
    )
    return guide


def deactivate_guide(*, actor, tenant_id: int, guide_id: int, request=None) -> Guide:
    return update_guide(
        actor=actor, tenant_id=tenant_id, guide_id=guide_id,
        estado=Guide.Status.INACTIVE, request=request,
    )


def _check_can_deactivate(guide: Guide) -> None:
    """Un guia con salidas proximas no se desactiva: esas salidas quedarian sin nadie."""
    upcoming = Availability.objects.filter(guide=guide, closed=False, start__gt=timezone.now()).count()
    if upcoming:
        raise ValidationError(
            {
                "estado": [
                    f"El guía tiene {upcoming} salida(s) próxima(s). "
                    "Asigna otro guía a esas salidas antes de desactivarlo."
                ]
            }
        )


def guide_is_free(guide: Guide, start: datetime, end: datetime, *, exclude_departure_id: int | None = None) -> bool:
    """Si el guia no tiene otra salida abierta que se cruce con ``start``-``end``."""
    overlapping = Availability.objects.filter(guide=guide, closed=False, start__lt=end, end__gt=start)
    if exclude_departure_id is not None:
        overlapping = overlapping.exclude(id=exclude_departure_id)
    return not overlapping.exists()


def resolve_guide(tenant_id: int, guide_id: int) -> Guide:
    """El guia a asignar: de esta empresa y activo."""
    guide = Guide.objects.filter(tenant_id=tenant_id, id=guide_id).first()
    if guide is None:
        raise ValidationError({"guia_id": ["El guía no existe en esta empresa."]})
    if not guide.is_active:
        raise ValidationError({"guia_id": ["El guía está inactivo."]})
    return guide
