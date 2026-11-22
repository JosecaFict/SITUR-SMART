"""Herramientas del asesor de viajes: tours, promociones, intereses y paquetes.

Igual que las de hospedaje (``tools.py``), solo leen la oferta publica del
Marketplace: lo que ve un visitante anonimo. El modelo nunca toca la base ni
hace cuentas; describe que quiere y este modulo responde con datos reales.

Las consultas a la base estan en funciones ``_find_*`` / ``_get_*`` pequenas y
el armado de las respuestas en funciones puras, para poder probarlas sin base.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from django.utils import timezone

from .recommendations import _plain, as_card

logger = logging.getLogger(__name__)

MAX_RESULTS = 5
MAX_DEPARTURES = 6
MAX_STOPS = 12
MAX_PACKAGE_TOURS = 5

DIFFICULTIES = {"BAJA", "MEDIA", "ALTA"}
TOUR_TYPES = {"TOUR", "EXPERIENCIA"}


@dataclass
class Collected:
    """Lo que aparecio en la conversacion, para devolverlo como tarjetas."""

    hospedajes: dict = field(default_factory=dict)
    tours: dict = field(default_factory=dict)
    promociones: dict = field(default_factory=dict)


# --- Utilidades ---------------------------------------------------------------


def _local(value) -> str | None:
    return timezone.localtime(value).strftime("%d/%m/%Y %H:%M") if value else None


def _duration(minutes: int | None) -> str | None:
    if not minutes:
        return None
    hours, rest = divmod(int(minutes), 60)
    if not hours:
        return f"{rest} min"
    return f"{hours} h" + (f" {rest} min" if rest else "")


def _matches_city(product, wanted: str | None) -> bool:
    if not wanted:
        return True
    plain = _plain(wanted)
    return plain in _plain(product.city.name) or plain in _plain(product.locality or "")


def _decimal(value) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except Exception:
        return None
    return number if number > 0 else None


# --- Tours y experiencias -----------------------------------------------------


def _public_tours():
    from apps.catalog.models import TourismProduct
    from apps.catalog.tours import _tours_queryset
    from apps.tenancy.subscriptions import restricted_tenant_ids

    return (
        _tours_queryset()
        .filter(status=TourismProduct.Status.PUBLISHED, tenant__status="ACTIVO", tour__isnull=False)
        .exclude(tenant_id__in=restricted_tenant_ids())
    )


def _find_tours(*, tipo, presupuesto, dificultad, buscar) -> list:
    return list(_tours_query(tipo=tipo, presupuesto=presupuesto, dificultad=dificultad, buscar=buscar))


def _tours_query(*, tipo, presupuesto, dificultad, buscar):
    """Tours con al menos una salida futura abierta: los que se pueden reservar."""
    from django.db.models import Q

    tours = _public_tours().filter(upcoming_departures__gt=0)
    if tipo:
        tours = tours.filter(product_type__code=tipo)
    if presupuesto is not None:
        tours = tours.filter(base_price__lte=presupuesto)
    if dificultad:
        tours = tours.filter(tour__difficulty=dificultad)
    if buscar:
        tours = tours.filter(Q(name__icontains=buscar) | Q(description__icontains=buscar))
    return tours.order_by("next_departure", "base_price", "id")[:60]


def _get_tour(tour_id: int):
    return _public_tours().filter(id=tour_id).first()


def _departures(tour_id: int) -> list:
    from apps.catalog.tour_departures import list_public_departures

    return list_public_departures(tour_id)[:MAX_DEPARTURES]


def tour_card(product) -> dict:
    detail = product.tour
    return {
        "id": product.id,
        "nombre": product.name,
        "tipo": product.product_type.name,
        "ciudad": product.city.name,
        "localidad": product.locality,
        "empresa": product.tenant.trade_name,
        "precio_por_persona": str(product.base_price),
        "moneda": product.currency.symbol,
        "duracion": _duration(detail.duration_minutes),
        "dificultad": detail.get_difficulty_display() if detail.difficulty else None,
        "edad_minima": detail.minimum_age,
        "idioma": detail.language,
        "proxima_salida": _local(getattr(product, "next_departure", None)),
        "salidas_disponibles": getattr(product, "upcoming_departures", None),
        "imagen_url": product.image_url,
        "url": f"/marketplace/productos/{product.id}",
    }


def buscar_tours(args: dict, collected: Collected, *, user=None, limit=MAX_RESULTS, **_) -> dict:
    tipo = str(args.get("tipo") or "").upper().strip() or None
    dificultad = str(args.get("dificultad") or "").upper().strip() or None
    found = _find_tours(
        tipo=tipo if tipo in TOUR_TYPES else None,
        presupuesto=_decimal(args.get("presupuesto")),
        dificultad=dificultad if dificultad in DIFFICULTIES else None,
        buscar=(str(args.get("buscar") or "").strip()[:80] or None),
    )
    ciudad = str(args.get("ciudad") or "").strip()[:80] or None
    found = [tour for tour in found if _matches_city(tour, ciudad)][:limit]
    if not found:
        return with_alternatives(
            {
                "resultados": [],
                "nota": "No hay tours ni experiencias con salidas abiertas que cumplan esos criterios.",
            },
            "tours",
        )
    cards = [tour_card(tour) for tour in found]
    for card in cards:
        collected.tours[card["id"]] = card
    return {"resultados": cards}


def detalle_tour(args: dict, collected: Collected, **_) -> dict:
    tour_id = _positive_int(args.get("id"))
    product = _get_tour(tour_id) if tour_id else None
    if product is None:
        return {"error": "Ese tour o experiencia no existe o no esta publicado."}
    card = tour_card(product)
    collected.tours[card["id"]] = card
    detail = product.tour
    departures = _departures(product.id)
    return {
        **card,
        "descripcion": (product.description or "")[:600],
        "punto_encuentro": detail.meeting_point,
        "incluye": list(detail.includes or [])[:10],
        "no_incluye": list(detail.excludes or [])[:10],
        "requisitos": (detail.requirements or "")[:300] or None,
        "recorrido": [
            {"parada": stop.name, "duracion": _duration(stop.duration_minutes)}
            for stop in list(product.stops.all())[:MAX_STOPS]
        ],
        "proximas_salidas": [
            {
                "inicio": _local(departure.start),
                "fin": _local(departure.end),
                "lugares_libres": max(departure.total_capacity - getattr(departure, "booked", 0), 0),
            }
            for departure in departures
        ],
    }


# --- Promociones --------------------------------------------------------------


def _find_promotions() -> list[tuple]:
    """Promociones vigentes y validas, con sus datos calculados."""
    from apps.promotions import services

    result = []
    for promotion in services.public_promotions().order_by("ends_at", "id")[:30]:
        data = services.promotion_data(promotion)
        if data.get("publicado"):
            result.append((promotion, data))
    return result


def _promotion_cities(promotion, data) -> list[str]:
    products = [promotion.product] if promotion.product_id else []
    products += [component.product for component in promotion.components.all()]
    return sorted({product.city.name for product in products if product is not None})


def promotion_card(promotion, data, cities: list[str]) -> dict:
    combined = promotion.mode == "COMBINADO"
    return {
        "id": promotion.id,
        "nombre": promotion.name,
        "empresa": promotion.tenant.trade_name,
        "modalidad": "Servicios combinados" if combined else "Descuento en un producto",
        "descuento_porcentaje": str(promotion.percentage),
        "precio_original": data.get("precio_original"),
        "precio_final": data.get("precio_final"),
        "moneda": data.get("moneda_simbolo"),
        "incluye": [item.get("nombre") for item in data.get("componentes") or [] if item.get("nombre")][:6],
        "ciudades": cities,
        "vence": _local(promotion.ends_at),
        "se_puede_reservar": bool(data.get("admite_reservas")),
        "imagen_url": data.get("imagen_url"),
        "url": f"/marketplace/promociones/{promotion.id}",
    }


def promociones_vigentes(args: dict, collected: Collected, **_) -> dict:
    ciudad = str(args.get("ciudad") or "").strip()[:80] or None
    wanted = _plain(ciudad) if ciudad else None
    cards = []
    for promotion, data in _find_promotions():
        cities = _promotion_cities(promotion, data)
        if wanted and not any(wanted in _plain(city) for city in cities):
            continue
        cards.append(promotion_card(promotion, data, cities))
        if len(cards) >= MAX_RESULTS:
            break
    if not cards:
        return {"resultados": [], "nota": "No hay promociones vigentes con esos criterios en este momento."}
    for card in cards:
        collected.promociones[card["id"]] = card
    return {"resultados": cards}


# --- Intereses del viajero ----------------------------------------------------


def mis_intereses(args: dict, collected: Collected, *, user=None, **_) -> dict:
    if user is None or not getattr(user, "is_authenticated", False):
        return {"error": "No hay un viajero con sesion iniciada."}
    from apps.notifications.interests import customer_interests

    profile = customer_interests(user)
    if not profile["ciudades"] and not profile["tipos"]:
        return {
            **profile,
            "nota": "Todavia no tiene favoritos, reservas ni resenas: pregunta por sus gustos.",
        }
    return profile


# --- Paquete estimado ---------------------------------------------------------


def _get_lodging(lodging_id: int):
    from apps.catalog.services import public_lodgings

    return public_lodgings().filter(id=lodging_id).first()


def _rooms(lodging) -> list:
    from apps.catalog.services import public_rooms

    return list(public_rooms().filter(establishment=lodging).order_by("product__base_price", "id")[:10])


def _room_plan(rooms: list, people: int):
    """La opcion mas barata para alojar a todos: (habitacion, cantidad, total por noche)."""
    best = None
    for room in rooms:
        capacity = room.product.max_capacity or 0
        if capacity <= 0:
            continue
        count = math.ceil(people / capacity)
        if count > (room.quantity or 1):
            continue
        nightly = room.product.base_price * count
        if best is None or nightly < best[2]:
            best = (room, count, nightly)
    return best


def estimar_paquete(args: dict, collected: Collected, **_) -> dict:
    people = _positive_int(args.get("personas"), high=20) or 1
    nights = _positive_int(args.get("noches"), high=30)
    lodging_id = _positive_int(args.get("hospedaje_id"))
    raw_tours = args.get("tour_ids") or []
    if not isinstance(raw_tours, list):
        raw_tours = [raw_tours]
    tour_ids = list(dict.fromkeys(i for i in (_positive_int(x) for x in raw_tours) if i))[:MAX_PACKAGE_TOURS]

    if not lodging_id and not tour_ids:
        return {"error": "Indica un hospedaje_id, uno o mas tour_ids, o ambos."}

    lines: list[dict] = []
    totals: dict[str, Decimal] = defaultdict(Decimal)
    warnings: list[str] = []

    if lodging_id:
        lodging = _get_lodging(lodging_id)
        if lodging is None:
            warnings.append(f"El hospedaje {lodging_id} no existe o no esta publicado.")
        elif not nights:
            warnings.append("Falta la cantidad de noches para estimar el hospedaje.")
        else:
            card = as_card(lodging)
            collected.hospedajes[card["id"]] = card
            plan = _room_plan(_rooms(lodging), people)
            if plan is None:
                warnings.append(f"{lodging.product.name} no tiene habitaciones para {people} personas.")
            else:
                room, count, nightly = plan
                subtotal = nightly * nights
                symbol = lodging.product.currency.symbol
                totals[symbol] += subtotal
                lines.append(
                    {
                        "concepto": f"{lodging.product.name}: {count} x {room.product.name}",
                        "detalle": f"{symbol} {nightly} por noche x {nights} noches",
                        "subtotal": f"{symbol} {subtotal}",
                    }
                )

    for tour_id in tour_ids:
        product = _get_tour(tour_id)
        if product is None:
            warnings.append(f"El tour {tour_id} no existe o no esta publicado.")
            continue
        card = tour_card(product)
        collected.tours[card["id"]] = card
        symbol = product.currency.symbol
        subtotal = product.base_price * people
        totals[symbol] += subtotal
        lines.append(
            {
                "concepto": product.name,
                "detalle": f"{symbol} {product.base_price} por persona x {people} personas",
                "subtotal": f"{symbol} {subtotal}",
            }
        )

    result = {
        "personas": people,
        "noches": nights,
        "detalle": lines,
        # Una suma por moneda: no se mezclan bolivianos con dolares.
        "total_estimado": [f"{symbol} {amount}" for symbol, amount in totals.items()],
        "nota": (
            "Estimado con precios base actuales. Promociones, disponibilidad de fechas y cupos "
            "se confirman al reservar cada servicio en el Marketplace."
        ),
    }
    if warnings:
        result["advertencias"] = warnings
    return result


# --- Ciudades -----------------------------------------------------------------


def _city_counts() -> tuple[dict, dict]:
    """Cuantos hospedajes y tours reservables hay por ciudad (una fila por producto)."""
    from collections import Counter

    from apps.catalog.services import public_lodgings

    lodgings = Counter(public_lodgings().order_by().values_list("product__city__name", flat=True))
    tours = Counter(
        _public_tours().filter(upcoming_departures__gt=0).order_by().values_list("city__name", flat=True)
    )
    return dict(lodgings), dict(tours)


def with_alternatives(result: dict, kind: str) -> dict:
    """Agrega a una busqueda vacia las ciudades que si tienen esa oferta.

    Asi el modelo propone alternativas reales sin otra ronda (y sin inventar
    ciudades). ``kind`` es "tours" u "hospedajes". Si la consulta falla, la
    respuesta sale igual, sin la lista.
    """
    try:
        lodgings, tours = _city_counts()
    except Exception:
        logger.warning("No se pudieron listar las ciudades con oferta para sugerir alternativas.")
        return result
    counts = tours if kind == "tours" else lodgings
    key = "ciudades_con_tours" if kind == "tours" else "ciudades_con_hospedajes"
    result[key] = sorted(counts, key=_plain)
    result["nota"] += f" Si propones otra ciudad, usa solo las de {key}."
    return result


def listar_ciudades(args: dict, collected: Collected, **_) -> dict:
    lodgings, tours = _city_counts()
    names = sorted(set(lodgings) | set(tours), key=_plain)
    return {
        "ciudades": [
            {"ciudad": name, "hospedajes": lodgings.get(name, 0), "tours_y_experiencias": tours.get(name, 0)}
            for name in names
        ],
        "nota": "Solo estas ciudades tienen oferta publicada en SITUR-SMART.",
    }


def _positive_int(value, *, high: int = 2**62) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= high else None
