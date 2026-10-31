"""Salidas de un tour o experiencia (CU20).

Una salida es una fila de ``disponibilidad`` con fecha, hora, cupo y, si se
quiere, un guia. La crea la empresa, a diferencia del cupo diario automatico de
habitaciones y atracciones. Reservas (bookings/services.py) la usa igual que
cualquier otro cupo, y CU43 la cancela con reembolso desde Pagos.

Reglas:

* solo los tours con ficha (``detalle_tour``) tienen salidas;
* una salida es a futuro, termina despues de empezar y no repite la hora de
  otra salida del mismo tour (tambien lo obliga uq_disponibilidad_producto_inicio);
* el cupo va de 1 a la capacidad maxima del tour y nunca baja de lo reservado;
* una salida con reservas no cambia de horario ni se elimina: se cierra, o se
  cancela con reembolso desde Pagos (CU43).
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.audit.services import record_audit
from apps.rbac.services import require_permission, require_tenant_access
from apps.tenancy.subscriptions import require_active_plan, restricted_tenant_ids

from .guides import guide_is_free, resolve_guide
from .models import TOUR_PRODUCT_CODES, Availability, TourismProduct

# Hasta cuantos dias abarca una carga de salidas repetidas, y cuantas crea como
# maximo: mas que eso es casi siempre un error de fechas.
MAX_RECURRING_DAYS = 92
MAX_RECURRING_CREATED = 200
# Lo que muestra el Marketplace hacia adelante.
PUBLIC_DAYS_AHEAD = 120

WEEKDAY_NAMES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _zone() -> ZoneInfo:
    return ZoneInfo(settings.TIME_ZONE)


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=_zone())


def _when(value: datetime) -> str:
    return timezone.localtime(value, _zone()).strftime("%d/%m/%Y %H:%M")


def _booked(departures: list[Availability]) -> dict[int, int]:
    """Lugares tomados en cada salida: confirmados mas apartados vigentes."""
    from apps.bookings.services import _occupied

    return _occupied([departure.id for departure in departures]) if departures else {}


def _with_booked(departures: list[Availability]) -> list[Availability]:
    used = _booked(departures)
    for departure in departures:
        departure.booked = used.get(departure.id, 0)
    return departures


def _has_bookings(departure: Availability) -> bool:
    """Si alguna reserva, de cualquier estado, apunta a la salida."""
    from apps.bookings.models import BookingDetail, InventoryLock

    return (
        BookingDetail.objects.filter(slot=departure).exists()
        or InventoryLock.objects.filter(slot=departure).exists()
    )


def _company_tour(*, actor, tenant_id: int, tour_id: int, permission: str) -> TourismProduct:
    require_tenant_access(actor, tenant_id)
    require_permission(actor, permission, tenant_id)
    product = (
        TourismProduct.objects.select_related("tour", "product_type")
        .filter(tenant_id=tenant_id, id=tour_id, product_type__code__in=TOUR_PRODUCT_CODES)
        .first()
    )
    if product is None:
        raise NotFound("Tour no encontrado en esta empresa.")
    if not hasattr(product, "tour"):
        raise ValidationError(
            {"tour": ["Completa la ficha del tour (duración, punto de encuentro…) antes de crear salidas."]}
        )
    return product


def _company_departure(*, actor, tenant_id: int, departure_id: int, permission: str) -> Availability:
    require_tenant_access(actor, tenant_id)
    require_permission(actor, permission, tenant_id)
    departure = (
        Availability.objects.select_related("product__tour", "guide")
        .filter(
            id=departure_id,
            tenant_id=tenant_id,
            product__product_type__code__in=TOUR_PRODUCT_CODES,
            product__tour__isnull=False,
        )
        .first()
    )
    if departure is None:
        raise NotFound("Salida no encontrada en esta empresa.")
    return departure


def _check_schedule(product: TourismProduct, start: datetime, end: datetime, *, exclude_id: int | None = None) -> None:
    """Horario valido: a futuro, con fin despues del inicio y sin repetir hora."""
    if start <= timezone.now():
        raise ValidationError({"inicio": ["La salida tiene que ser a futuro."]})
    if end <= start:
        raise ValidationError({"fin": ["La salida debe terminar después de empezar."]})
    repeated = Availability.objects.filter(product=product, start=start)
    if exclude_id is not None:
        repeated = repeated.exclude(id=exclude_id)
    if repeated.exists():
        raise ValidationError({"inicio": [f"Ya hay una salida de este tour el {_when(start)}."]})


def _check_capacity_value(product: TourismProduct, capacity: int) -> None:
    if capacity < 1 or capacity > product.max_capacity:
        raise ValidationError(
            {"cupo": [f"El cupo va de 1 a {product.max_capacity} (la capacidad máxima del tour)."]}
        )


def _default_end(product: TourismProduct, start: datetime) -> datetime:
    minutes = product.tour.duration_minutes
    if not minutes:
        raise ValidationError(
            {"fin": ["Indica la hora de fin, o la duración del tour en su ficha para calcularla."]}
        )
    return start + timedelta(minutes=minutes)


def list_departures(
    *, actor, tenant_id: int, tour_id: int, date_from: date | None = None, date_to: date | None = None
) -> list[Availability]:
    product = _company_tour(actor=actor, tenant_id=tenant_id, tour_id=tour_id, permission="PRODUCTOS_LEER")
    date_from = date_from or timezone.localdate()
    queryset = Availability.objects.select_related("guide").filter(
        product=product, start__gte=_day_start(date_from)
    )
    if date_to is not None:
        queryset = queryset.filter(start__lt=_day_start(date_to + timedelta(days=1)))
    return _with_booked(list(queryset.order_by("start", "id")))


@transaction.atomic
def create_departure(
    *, actor, tenant_id: int, tour_id: int, start: datetime, end: datetime | None = None,
    capacity: int | None = None, guide_id: int | None = None, request=None,
) -> Availability:
    product = _company_tour(actor=actor, tenant_id=tenant_id, tour_id=tour_id, permission="DISPONIBILIDAD_GESTIONAR")
    require_active_plan(actor, tenant_id)
    end = end or _default_end(product, start)
    capacity = product.max_capacity if capacity is None else capacity
    _check_schedule(product, start, end)
    _check_capacity_value(product, capacity)
    guide = None
    if guide_id is not None:
        guide = resolve_guide(tenant_id, guide_id)
        if not guide_is_free(guide, start, end):
            raise ValidationError({"guia_id": [f"{guide.names} ya tiene otra salida en ese horario."]})

    departure = Availability.objects.create(
        product=product, tenant_id=tenant_id, start=start, end=end, total_capacity=capacity, guide=guide
    )
    departure.booked = 0
    record_audit(
        actor=actor, tenant_id=tenant_id, action="CREAR", entity="salida_tour",
        entity_id=str(departure.id),
        new_data={"producto_id": product.id, "inicio": start.isoformat(), "cupo": capacity, "guia_id": guide_id},
        request=request,
    )
    return departure


@transaction.atomic
def create_recurring(
    *, actor, tenant_id: int, tour_id: int, weekdays: list[int], start_time: time,
    date_from: date, date_to: date, end_time: time | None = None, capacity: int | None = None,
    guide_id: int | None = None, request=None,
) -> dict:
    """Crea una salida por cada dia elegido de la semana dentro del rango.

    Los dias ya pasados o que ya tienen salida a esa hora se omiten y se
    informan. Si el guia esta ocupado en alguno, no se crea ninguna: es mejor
    corregir el guia que terminar con salidas a medias.
    """
    product = _company_tour(actor=actor, tenant_id=tenant_id, tour_id=tour_id, permission="DISPONIBILIDAD_GESTIONAR")
    require_active_plan(actor, tenant_id)
    if date_to < date_from:
        raise ValidationError({"hasta": ["La fecha final debe ser igual o posterior a la inicial."]})
    if (date_to - date_from).days + 1 > MAX_RECURRING_DAYS:
        raise ValidationError({"hasta": [f"Se pueden programar hasta {MAX_RECURRING_DAYS} días de una vez."]})
    if not weekdays:
        raise ValidationError({"dias_semana": ["Elige al menos un día de la semana."]})
    capacity = product.max_capacity if capacity is None else capacity
    _check_capacity_value(product, capacity)
    guide = resolve_guide(tenant_id, guide_id) if guide_id is not None else None

    now = timezone.now()
    taken = set(Availability.objects.filter(product=product, start__gte=_day_start(date_from)).values_list("start", flat=True))
    to_create: list[Availability] = []
    skipped = 0
    busy: list[str] = []
    day = date_from
    while day <= date_to:
        if day.weekday() in weekdays:
            start = datetime.combine(day, start_time, tzinfo=_zone())
            end = datetime.combine(day, end_time, tzinfo=_zone()) if end_time else _default_end(product, start)
            if end <= start:
                raise ValidationError({"hora_fin": ["La hora de fin debe ser posterior a la de inicio."]})
            if start <= now or start in taken:
                skipped += 1
            else:
                if guide is not None and not guide_is_free(guide, start, end):
                    busy.append(_when(start))
                to_create.append(
                    Availability(product=product, tenant_id=tenant_id, start=start, end=end,
                                 total_capacity=capacity, guide=guide)
                )
        day += timedelta(days=1)

    if busy:
        shown = ", ".join(busy[:3]) + ("…" if len(busy) > 3 else "")
        raise ValidationError({"guia_id": [f"{guide.names} ya tiene otra salida el {shown}."]})
    if len(to_create) > MAX_RECURRING_CREATED:
        raise ValidationError({"hasta": [f"Serían {len(to_create)} salidas; el máximo por carga es {MAX_RECURRING_CREATED}."]})
    if not to_create:
        raise ValidationError({"dias_semana": ["No hay fechas nuevas que programar en ese rango."]})

    created = Availability.objects.bulk_create(to_create)
    for departure in created:
        departure.booked = 0
    record_audit(
        actor=actor, tenant_id=tenant_id, action="CREAR", entity="salida_tour",
        entity_id=str(product.id),
        new_data={
            "producto_id": product.id, "salidas": len(created), "omitidas": skipped,
            "dias_semana": [WEEKDAY_NAMES[day] for day in sorted(weekdays)],
            "desde": date_from.isoformat(), "hasta": date_to.isoformat(),
        },
        request=request,
    )
    return {"created": created, "skipped": skipped}


@transaction.atomic
def update_departure(*, actor, tenant_id: int, departure_id: int, request=None, **changes) -> Availability:
    """Cambia horario, cupo, guia o reabre una salida cerrada.

    ``changes`` usa las claves de la API: inicio, fin, cupo, guia_id, cerrada.
    """
    departure = _company_departure(
        actor=actor, tenant_id=tenant_id, departure_id=departure_id, permission="DISPONIBILIDAD_GESTIONAR"
    )
    require_active_plan(actor, tenant_id)
    # Se toma la fila con FOR UPDATE: una reserva no puede colarse entre el
    # conteo de lo reservado y el cambio de cupo.
    Availability.objects.select_for_update().filter(id=departure.id).first()
    product = departure.product
    booked = _booked([departure]).get(departure.id, 0)
    previous = {
        "inicio": departure.start.isoformat(), "fin": departure.end.isoformat(),
        "cupo": departure.total_capacity, "guia_id": departure.guide_id, "cerrada": departure.closed,
    }

    start = changes.get("inicio", departure.start)
    end = changes.get("fin", departure.end)
    if "inicio" in changes and "fin" not in changes:
        # Mover la salida conserva su duracion.
        end = start + (departure.end - departure.start)
    if start != departure.start or end != departure.end:
        if _has_bookings(departure):
            raise ValidationError(
                {"inicio": ["La salida ya tiene reservas: no se puede cambiar su horario. Ciérrala o cancélala desde Pagos."]}
            )
        _check_schedule(product, start, end, exclude_id=departure.id)

    if "cupo" in changes:
        capacity = changes["cupo"]
        _check_capacity_value(product, capacity)
        if capacity < booked:
            raise ValidationError({"cupo": [f"Ya hay {booked} lugares reservados: el cupo no puede ser menor."]})
        departure.total_capacity = capacity

    if "guia_id" in changes:
        guide_id = changes["guia_id"]
        departure.guide = resolve_guide(tenant_id, guide_id) if guide_id is not None else None
    if departure.guide is not None and ("guia_id" in changes or start != departure.start or end != departure.end):
        if not guide_is_free(departure.guide, start, end, exclude_departure_id=departure.id):
            raise ValidationError({"guia_id": [f"{departure.guide.names} ya tiene otra salida en ese horario."]})

    if changes.get("cerrada") is False and departure.closed:
        if start <= timezone.now():
            raise ValidationError({"cerrada": ["Una salida que ya pasó no se puede reabrir."]})
        departure.closed = False
    elif changes.get("cerrada") is True:
        departure.closed = True

    departure.start, departure.end = start, end
    departure.save(update_fields=["start", "end", "total_capacity", "guide", "closed"])
    departure.booked = booked
    record_audit(
        actor=actor, tenant_id=tenant_id, action="ACTUALIZAR", entity="salida_tour",
        entity_id=str(departure.id), previous_data=previous,
        new_data={
            "inicio": departure.start.isoformat(), "fin": departure.end.isoformat(),
            "cupo": departure.total_capacity, "guia_id": departure.guide_id, "cerrada": departure.closed,
        },
        request=request,
    )
    return departure


def close_departure(*, actor, tenant_id: int, departure_id: int, request=None) -> Availability:
    """Deja de vender la salida. Las reservas que ya tiene se mantienen."""
    return update_departure(
        actor=actor, tenant_id=tenant_id, departure_id=departure_id, cerrada=True, request=request
    )


@transaction.atomic
def delete_departure(*, actor, tenant_id: int, departure_id: int, request=None) -> None:
    departure = _company_departure(
        actor=actor, tenant_id=tenant_id, departure_id=departure_id, permission="DISPONIBILIDAD_GESTIONAR"
    )
    if _has_bookings(departure):
        raise ValidationError(
            {"salida": ["La salida tiene reservas: no se puede eliminar. Ciérrala, o cancélala con reembolso desde Pagos."]}
        )
    record_audit(
        actor=actor, tenant_id=tenant_id, action="ELIMINAR", entity="salida_tour",
        entity_id=str(departure.id),
        previous_data={"producto_id": departure.product_id, "inicio": departure.start.isoformat()},
        request=request,
    )
    departure.delete()


def open_future_departures(product: TourismProduct):
    """Salidas que todavia se pueden vender."""
    return Availability.objects.filter(product=product, closed=False, start__gt=timezone.now())


def list_public_departures(tour_id: int) -> list[Availability]:
    """Proximas salidas de un tour publicado, con sus lugares libres."""
    product = (
        TourismProduct.objects.filter(
            id=tour_id,
            status=TourismProduct.Status.PUBLISHED,
            tenant__status="ACTIVO",
            product_type__code__in=TOUR_PRODUCT_CODES,
            tour__isnull=False,
        )
        .exclude(tenant_id__in=restricted_tenant_ids())
        .first()
    )
    if product is None:
        raise NotFound("Tour no encontrado.")
    horizon = timezone.now() + timedelta(days=PUBLIC_DAYS_AHEAD)
    departures = list(
        open_future_departures(product).filter(start__lt=horizon).select_related("guide").order_by("start", "id")
    )
    return _with_booked(departures)
