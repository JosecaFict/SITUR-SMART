"""Itinerarios: el plan de un viaje dia por dia.

Las actividades las carga el turista; las reservas pagadas no se guardan aca,
se mezclan al leer (``build_days``) para que una cancelacion o un cambio se
vean solos.
"""

from dataclasses import dataclass, field
from datetime import date, time, timedelta

from django.db.models import Count
from rest_framework.exceptions import NotFound, ValidationError

from apps.bookings.models import Booking
from apps.bookings.serializers import BookingSerializer
from apps.bookings.services import paid_bookings_touching
from apps.catalog.models import TourismProduct
from apps.favorites.services import public_products
from apps.tenancy.models import City

from .models import Itinerary, ItineraryActivity

MAX_DAYS = 60


# --- Itinerarios ----------------------------------------------------------------


def list_itineraries(*, user):
    return (
        Itinerary.objects.filter(user=user)
        .select_related("city")
        .annotate(activity_count=Count("activities"))
    )


def get_itinerary(*, user, itinerary_id: int) -> Itinerary:
    itinerary = Itinerary.objects.select_related("city").filter(user=user, id=itinerary_id).first()
    if itinerary is None:
        raise NotFound("Itinerario no encontrado.")
    return itinerary


def _check_range(start: date, end: date) -> None:
    if end < start:
        raise ValidationError({"fin": "La fecha de regreso no puede ser anterior a la de salida."})
    if (end - start).days >= MAX_DAYS:
        raise ValidationError({"fin": f"Un itinerario puede durar hasta {MAX_DAYS} días."})


def _city(city_id: int | None) -> City | None:
    if city_id is None:
        return None
    city = City.objects.filter(id=city_id, active=True).first()
    if city is None:
        raise ValidationError({"ciudad_id": "Ciudad no encontrada."})
    return city


def create_itinerary(*, user, name: str, start: date, end: date, city_id=None, notes=None) -> Itinerary:
    _check_range(start, end)
    return Itinerary.objects.create(
        user=user, name=name, start_date=start, end_date=end, city=_city(city_id), notes=notes or None
    )


def update_itinerary(*, user, itinerary_id: int, changes: dict) -> Itinerary:
    itinerary = get_itinerary(user=user, itinerary_id=itinerary_id)
    start = changes.get("start", itinerary.start_date)
    end = changes.get("end", itinerary.end_date)
    _check_range(start, end)
    outside = itinerary.activities.exclude(date__range=(start, end)).count()
    if outside:
        raise ValidationError(
            {
                "inicio": (
                    f"{outside} {'actividad queda' if outside == 1 else 'actividades quedan'} "
                    "fuera de las nuevas fechas. Muévelas o bórralas primero."
                )
            }
        )
    itinerary.start_date, itinerary.end_date = start, end
    if "name" in changes:
        itinerary.name = changes["name"]
    if "city_id" in changes:
        itinerary.city = _city(changes["city_id"])
    if "notes" in changes:
        itinerary.notes = changes["notes"] or None
    itinerary.save()
    return itinerary


def delete_itinerary(*, user, itinerary_id: int) -> None:
    get_itinerary(user=user, itinerary_id=itinerary_id).delete()


# --- Actividades ------------------------------------------------------------------


def _check_day(itinerary: Itinerary, day: date) -> None:
    if not itinerary.start_date <= day <= itinerary.end_date:
        raise ValidationError({"fecha": "La fecha tiene que estar dentro del viaje."})


def _product(product_id: int) -> TourismProduct:
    product = public_products().filter(id=product_id).first()
    if product is None:
        raise ValidationError({"producto_id": "Producto no encontrado."})
    return product


def add_activity(
    *, user, itinerary_id: int, day: date, at: time | None = None,
    product_id: int | None = None, title: str | None = None, note: str | None = None,
) -> ItineraryActivity:
    itinerary = get_itinerary(user=user, itinerary_id=itinerary_id)
    _check_day(itinerary, day)
    product = _product(product_id) if product_id is not None else None
    title = (title or "").strip() or (product.name if product else "")
    if not title:
        raise ValidationError({"titulo": "Escribe qué vas a hacer o elige un producto."})
    activity = ItineraryActivity.objects.create(
        itinerary=itinerary, date=day, time=at, product=product, title=title[:150], note=note or None
    )
    activity.visible_product = product
    return activity


def _activity(*, user, itinerary_id: int, activity_id: int) -> ItineraryActivity:
    activity = (
        ItineraryActivity.objects.select_related("itinerary")
        .filter(id=activity_id, itinerary_id=itinerary_id, itinerary__user=user)
        .first()
    )
    if activity is None:
        raise NotFound("Actividad no encontrada.")
    return activity


def update_activity(*, user, itinerary_id: int, activity_id: int, changes: dict) -> ItineraryActivity:
    """Cambia dia, hora, titulo o nota. El producto no cambia: se borra y se agrega otro."""
    activity = _activity(user=user, itinerary_id=itinerary_id, activity_id=activity_id)
    if "day" in changes:
        _check_day(activity.itinerary, changes["day"])
        activity.date = changes["day"]
    if "at" in changes:
        activity.time = changes["at"]
    if "title" in changes:
        title = (changes["title"] or "").strip()
        if not title:
            raise ValidationError({"titulo": "El título no puede quedar vacío."})
        activity.title = title[:150]
    if "note" in changes:
        activity.note = changes["note"] or None
    activity.save()
    activity.visible_product = public_products().filter(id=activity.product_id).first() if activity.product_id else None
    return activity


def delete_activity(*, user, itinerary_id: int, activity_id: int) -> None:
    _activity(user=user, itinerary_id=itinerary_id, activity_id=activity_id).delete()


# --- Vista por dias ---------------------------------------------------------------


@dataclass
class BookingEntry:
    """Una reserva pagada ubicada en un dia del viaje."""

    booking: Booking
    moment: str | None  # LLEGADA / SALIDA en un hospedaje; None en lo demas.
    summary: dict


@dataclass
class Day:
    date: date
    bookings: list[BookingEntry] = field(default_factory=list)
    activities: list[ItineraryActivity] = field(default_factory=list)


def _booking_entries(booking: Booking, start: date, end: date) -> list[tuple[date, str | None]]:
    """En que dias del rango aparece una reserva.

    Un hospedaje aparece el dia de llegada y el de salida (las noches del medio
    no son algo que hacer); un tour o un restaurante, el dia reservado.
    """
    fechas = BookingSerializer().get_fechas(booking)
    if fechas is None:
        return []
    first = date.fromisoformat(fechas["inicio"])
    if fechas["noches"]:
        last = date.fromisoformat(fechas["fin"])
        moments = [(first, "LLEGADA"), (last, "SALIDA")]
    else:
        moments = [(first, None)]
    return [(day, moment) for day, moment in moments if start <= day <= end]


def build_days(itinerary: Itinerary) -> list[Day]:
    start, end = itinerary.start_date, itinerary.end_date
    days = {start + timedelta(days=offset): Day(start + timedelta(days=offset)) for offset in range((end - start).days + 1)}

    activities = list(itinerary.activities.all())
    visible = {
        product.id: product
        for product in public_products().filter(id__in={a.product_id for a in activities if a.product_id})
    }
    for activity in activities:
        # Un producto que dejo de publicarse no se muestra; queda el titulo.
        activity.visible_product = visible.get(activity.product_id)
        days[activity.date].activities.append(activity)

    serializer = BookingSerializer()
    for booking in paid_bookings_touching(user=itinerary.user, start=start, end=end):
        summary = {
            "producto": serializer.get_producto(booking),
            "fechas": serializer.get_fechas(booking),
        }
        for day, moment in _booking_entries(booking, start, end):
            days[day].bookings.append(BookingEntry(booking=booking, moment=moment, summary=summary))

    for day in days.values():
        # Las salidas primero: de manana se deja el hotel y despues se llega al otro.
        day.bookings.sort(key=lambda entry: (entry.moment != "SALIDA", entry.booking.id))
        day.activities.sort(key=lambda a: (a.time is not None, a.time or time.min, a.id))
    return list(days.values())
