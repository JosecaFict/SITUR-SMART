"""Motor de recomendacion de hospedajes, sin IA.

Las recomendaciones salen de la base, no del modelo de lenguaje: el asistente
solo las explica. Asi un hotel que no existe no puede recomendarse, el puntaje
es reproducible y este modulo funciona aunque el proveedor de IA este caido.

El puntaje es por reglas y cada regla deja un motivo legible, que es lo que el
asistente usa para explicar por que recomienda cada opcion.
"""

import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Q

from apps.catalog.services import public_lodgings

# Cuanto por encima del presupuesto se sigue mostrando una opcion, marcada como
# tal. Sin margen, un presupuesto de 300 esconderia un hotel de 310 y el
# viajero no se enteraria de que existe.
BUDGET_TOLERANCE = Decimal("1.20")
MAX_CANDIDATES = 60
MAX_RESULTS = 10


@dataclass
class Criteria:
    ciudad: str | None = None
    ciudad_id: int | None = None
    presupuesto: Decimal | None = None
    huespedes: int | None = None
    estrellas: int | None = None
    servicios: list[str] = field(default_factory=list)
    buscar: str | None = None
    limite: int = 5


def _plain(text: str) -> str:
    """Minusculas y sin tildes: "Potosí" y "potosi" tienen que coincidir."""
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower().strip()


def candidates(criteria: Criteria):
    """Filtros duros: lo que no cumple no se recomienda nunca."""
    lodgings = public_lodgings()
    if criteria.ciudad_id:
        lodgings = lodgings.filter(product__city_id=criteria.ciudad_id)
    if criteria.huespedes:
        lodgings = lodgings.filter(total_capacity__gte=criteria.huespedes)
    if criteria.estrellas:
        lodgings = lodgings.filter(star_rating__gte=criteria.estrellas)
    if criteria.presupuesto is not None:
        lodgings = lodgings.filter(from_price__lte=criteria.presupuesto * BUDGET_TOLERANCE)
    if criteria.buscar:
        lodgings = lodgings.filter(
            Q(product__name__icontains=criteria.buscar)
            | Q(product__description__icontains=criteria.buscar)
            | Q(address__icontains=criteria.buscar)
        )
    lodgings = lodgings.order_by("from_price", "id")[:MAX_CANDIDATES]

    # La ciudad que escribe la IA o el viajero llega con o sin tildes. SQLite y
    # Postgres sin unaccent no las ignoran, asi que se compara en Python sobre
    # un conjunto ya acotado.
    if criteria.ciudad and not criteria.ciudad_id:
        wanted = _plain(criteria.ciudad)
        return [
            lodging for lodging in lodgings
            if wanted in _plain(lodging.product.city.name)
            or wanted in _plain(lodging.product.locality or "")
        ]
    return list(lodgings)


def score(lodging, criteria: Criteria) -> tuple[int, list[str]]:
    """Puntaje de 0 a ~100 y los motivos que lo explican."""
    points = 0
    reasons: list[str] = []
    price = lodging.from_price
    symbol = lodging.product.currency.symbol

    if criteria.presupuesto is not None and price is not None:
        if price <= criteria.presupuesto:
            # Mas puntos cuanto mas holgado queda dentro del presupuesto.
            slack = (criteria.presupuesto - price) / criteria.presupuesto if criteria.presupuesto else 0
            points += 30 + int(Decimal(10) * Decimal(slack))
            reasons.append(f"Dentro de tu presupuesto (desde {symbol} {price})")
        else:
            points += 5
            reasons.append(f"Algo por encima de tu presupuesto (desde {symbol} {price})")

    if lodging.star_rating:
        points += lodging.star_rating * 6
        reasons.append(f"{lodging.star_rating} estrellas")

    if criteria.huespedes and lodging.total_capacity:
        points += 10
        reasons.append(f"Capacidad para {criteria.huespedes} huéspedes")

    services = [_plain(str(s)) for s in (lodging.services or [])]
    for wanted in criteria.servicios:
        plain = _plain(wanted)
        if plain and any(plain in service for service in services):
            points += 8
            reasons.append(f"Ofrece {wanted}")

    points += min(lodging.rooms_count or 0, 5) * 2
    if (lodging.rooms_count or 0) >= 3:
        reasons.append(f"{lodging.rooms_count} tipos de habitación")
    # Ficha completa: con foto y ubicacion en el mapa el viajero decide mejor.
    if lodging.product.image_url:
        points += 3
    if lodging.latitude is not None:
        points += 2
    return points, reasons


def as_card(lodging, *, points: int | None = None, reasons: list[str] | None = None) -> dict:
    """Forma compacta que comparten la API y las herramientas de la IA."""
    card = {
        "id": lodging.id,
        "nombre": lodging.product.name,
        "tipo": lodging.lodging_type.name,
        "ciudad": lodging.product.city.name,
        "localidad": lodging.product.locality,
        "empresa": lodging.tenant.trade_name,
        "estrellas": lodging.star_rating,
        "precio_desde": str(lodging.from_price) if lodging.from_price is not None else None,
        "moneda": lodging.product.currency.symbol,
        "servicios": list(lodging.services or [])[:8],
        "imagen_url": lodging.product.image_url,
        "url": f"/marketplace/hospedajes/{lodging.id}",
    }
    if points is not None:
        card["puntaje"] = points
        card["motivos"] = reasons or []
    return card


def recommend(criteria: Criteria) -> list[dict]:
    scored = [(lodging, *score(lodging, criteria)) for lodging in candidates(criteria)]
    # Empate: el mas economico primero, luego el id para que sea estable.
    scored.sort(key=lambda item: (-item[1], item[0].from_price or Decimal("Infinity"), item[0].id))
    limit = max(1, min(criteria.limite, MAX_RESULTS))
    return [as_card(lodging, points=points, reasons=reasons) for lodging, points, reasons in scored[:limit]]
