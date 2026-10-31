"""Salidas de tours y experiencias sobre la disponibilidad existente.

La fila historica de un dia completo (medianoche a medianoche) se conserva
para las reservas antiguas. Las salidas nuevas terminan el mismo dia y duran
menos de 24 horas, por lo que se distinguen sin cambiar el esquema.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.bookings.models import BookingDetail, InventoryLock
from apps.rbac.services import require_permission, require_tenant_access
from apps.tenancy.subscriptions import require_active_plan, restricted_tenant_ids

from .models import Availability, TourismProduct

DEPARTURE_CODES = frozenset({"TOUR", "EXPERIENCIA"})


def _occupied(slot_ids):
    # Import diferido: bookings.services tambien consulta estas salidas.
    from apps.bookings.services import _occupied as booking_occupied

    return booking_occupied(slot_ids)


def _zone():
    return ZoneInfo(settings.TIME_ZONE)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(day, time.min, tzinfo=_zone()),
        datetime.combine(day + timedelta(days=1), time.min, tzinfo=_zone()),
    )


def is_legacy_daily(slot: Availability) -> bool:
    start = timezone.localtime(slot.start, _zone())
    end = timezone.localtime(slot.end, _zone())
    return start.time() == time.min and end == start + timedelta(days=1)


def slots_for_day(product_id: int, day: date):
    start, end = day_bounds(day)
    return Availability.objects.filter(product_id=product_id, start__gte=start, start__lt=end).order_by("start", "id")


def scheduled_slots(product_id: int, day: date) -> list[Availability]:
    return [slot for slot in slots_for_day(product_id, day) if not is_legacy_daily(slot)]


def _product(product_id: int, *, lock: bool = False) -> TourismProduct:
    query = TourismProduct.objects.select_related("product_type")
    if lock:
        query = query.select_for_update()
    product = query.filter(id=product_id).first()
    if product is None or product.product_type.code not in DEPARTURE_CODES:
        raise NotFound("Tour o experiencia no encontrado.")
    return product


def _company_product(*, actor, tenant_id: int, product_id: int, permission: str, lock=False):
    require_tenant_access(actor, tenant_id)
    require_permission(actor, permission, tenant_id)
    product = _product(product_id, lock=lock)
    if product.tenant_id != tenant_id:
        raise NotFound("Tour o experiencia no encontrado en esta empresa.")
    return product


def _public_product(product_id: int):
    product = _product(product_id)
    if (
        product.status != TourismProduct.Status.PUBLISHED
        or product.tenant.status != "ACTIVO"
        or product.tenant_id in restricted_tenant_ids()
    ):
        raise NotFound("Tour o experiencia no disponible.")
    return product


def _legacy_has_history(product_id: int, day: date) -> bool:
    legacy = [slot for slot in slots_for_day(product_id, day) if is_legacy_daily(slot)]
    ids = [slot.id for slot in legacy]
    # Incluso una reserva cancelada puede recibir un pago tardio de Stripe.
    # Su detalle sigue apuntando al dia completo y no debe convivir con salidas.
    return bool(ids) and (
        BookingDetail.objects.filter(slot_id__in=ids).exists()
        or InventoryLock.objects.filter(slot_id__in=ids).exists()
    )


def _validate_period(day: date, start_time: time, end_time: time) -> tuple[datetime, datetime]:
    if end_time <= start_time:
        raise ValidationError({"hora_fin": "Debe ser posterior a la hora de inicio en el mismo dia."})
    start = datetime.combine(day, start_time, tzinfo=_zone())
    end = datetime.combine(day, end_time, tzinfo=_zone())
    if start <= timezone.now():
        raise ValidationError({"fecha": "La salida debe comenzar en el futuro."})
    return start, end


def _check_overlap(product_id: int, day: date, start: datetime, end: datetime, exclude_id=None):
    for other in scheduled_slots(product_id, day):
        if other.id != exclude_id and start < other.end and other.start < end:
            raise ValidationError({"hora_inicio": "El horario se superpone con otra salida."})


def _validate_capacity(slot: Availability, capacity: int):
    used = _occupied([slot.id]).get(slot.id, 0)
    if capacity < used:
        raise ValidationError({"cupo_total": f"Hay {used} cupos reservados o apartados."})


def serialize(slot: Availability) -> dict:
    local_start = timezone.localtime(slot.start, _zone())
    local_end = timezone.localtime(slot.end, _zone())
    remaining = max(slot.total_capacity - _occupied([slot.id]).get(slot.id, 0), 0)
    return {
        "id": slot.id,
        "producto_id": slot.product_id,
        "fecha": local_start.date().isoformat(),
        "hora_inicio": local_start.time().isoformat(timespec="minutes"),
        "hora_fin": local_end.time().isoformat(timespec="minutes"),
        "inicio": local_start.isoformat(),
        "fin": local_end.isoformat(),
        "cupo_total": slot.total_capacity,
        "cupos_restantes": 0 if slot.closed else remaining,
        "cerrado": slot.closed,
    }


def list_company(*, actor, tenant_id: int, product_id: int, day: date | None = None):
    _company_product(actor=actor, tenant_id=tenant_id, product_id=product_id, permission="PRODUCTOS_LEER")
    if day is not None:
        return scheduled_slots(product_id, day)
    today, _ = day_bounds(timezone.localdate())
    return [slot for slot in Availability.objects.filter(product_id=product_id, start__gte=today).order_by("start", "id") if not is_legacy_daily(slot)]


def list_public(*, product_id: int, day: date | None = None):
    _public_product(product_id)
    first_day = day or timezone.localdate()
    last_day = first_day + timedelta(days=1 if day else 31)
    first, _ = day_bounds(first_day)
    last, _ = day_bounds(last_day)
    now = timezone.now()
    slots = [
        slot for slot in Availability.objects.filter(
            product_id=product_id, start__gte=first, start__lt=last, closed=False,
        ).order_by("start", "id")
        if slot.start > now and not is_legacy_daily(slot)
    ]
    used = _occupied([slot.id for slot in slots])
    return [slot for slot in slots if slot.total_capacity > used.get(slot.id, 0)]


@transaction.atomic
def create(*, actor, tenant_id: int, product_id: int, day: date, start_time: time, end_time: time, capacity: int, closed=False):
    product = _company_product(actor=actor, tenant_id=tenant_id, product_id=product_id, permission="DISPONIBILIDAD_GESTIONAR", lock=True)
    require_active_plan(actor, tenant_id)
    start, end = _validate_period(day, start_time, end_time)
    if capacity > product.max_capacity:
        raise ValidationError({"cupo_total": "Supera la capacidad maxima del producto."})
    if _legacy_has_history(product_id, day):
        raise ValidationError({"fecha": "Hay historial de reservas diarias; no se pueden crear salidas en esta fecha."})
    _check_overlap(product_id, day, start, end)
    if start_time == time.min:
        legacy = next((slot for slot in slots_for_day(product_id, day) if is_legacy_daily(slot)), None)
        if legacy is not None:
            if BookingDetail.objects.filter(slot=legacy).exists() or InventoryLock.objects.filter(slot=legacy).exists():
                raise ValidationError({"hora_inicio": "Existe disponibilidad diaria historica a medianoche en esa fecha."})
            legacy.start, legacy.end, legacy.total_capacity, legacy.closed = start, end, capacity, closed
            legacy.save(update_fields=["start", "end", "total_capacity", "closed"])
            return legacy
    return Availability.objects.create(product=product, tenant_id=tenant_id, start=start, end=end, total_capacity=capacity, closed=closed)


@transaction.atomic
def update(*, actor, tenant_id: int, product_id: int, slot_id: int, day=None, start_time=None, end_time=None, capacity=None, closed=None):
    product = _company_product(actor=actor, tenant_id=tenant_id, product_id=product_id, permission="DISPONIBILIDAD_GESTIONAR", lock=True)
    require_active_plan(actor, tenant_id)
    slot = Availability.objects.select_for_update().filter(id=slot_id, product=product, tenant_id=tenant_id).first()
    if slot is None or is_legacy_daily(slot):
        raise NotFound("Salida no encontrada.")
    local_start = timezone.localtime(slot.start, _zone())
    local_end = timezone.localtime(slot.end, _zone())
    new_day = day or local_start.date()
    new_start, new_end = _validate_period(new_day, start_time or local_start.time(), end_time or local_end.time())
    if (new_start != slot.start or new_end != slot.end) and BookingDetail.objects.filter(slot=slot).exists():
        raise ValidationError({"hora_inicio": "No se puede cambiar el horario de una salida con historial de reservas."})
    if new_day != local_start.date() and _legacy_has_history(product_id, new_day):
        raise ValidationError({"fecha": "Hay historial de reservas diarias en esa fecha."})
    _check_overlap(product_id, new_day, new_start, new_end, exclude_id=slot.id)
    if new_start != slot.start and timezone.localtime(new_start, _zone()).time() == time.min:
        if any(other.id != slot.id and is_legacy_daily(other) for other in slots_for_day(product_id, new_day)):
            raise ValidationError({"hora_inicio": "Ya existe una disponibilidad a medianoche en esa fecha."})
    new_capacity = capacity if capacity is not None else slot.total_capacity
    if new_capacity > product.max_capacity:
        raise ValidationError({"cupo_total": "Supera la capacidad maxima del producto."})
    _validate_capacity(slot, new_capacity)
    slot.start, slot.end, slot.total_capacity = new_start, new_end, new_capacity
    if closed is not None:
        slot.closed = closed
    slot.save(update_fields=["start", "end", "total_capacity", "closed"])
    return slot
