"""Herramientas que el modelo puede pedir que ejecutemos (function calling).

El modelo nunca toca la base: describe que quiere buscar y este modulo hace la
consulta con los mismos filtros publicos del Marketplace. Solo ve hospedajes
publicados de empresas activas, igual que un visitante anonimo.

Cada herramienta valida y acota sus argumentos: lo que llega lo escribio un
modelo de lenguaje y puede venir con tipos equivocados o valores absurdos.
"""

import json
import logging
from decimal import Decimal, InvalidOperation

from apps.catalog.services import public_lodgings, public_rooms

from .recommendations import Criteria, as_card, recommend

logger = logging.getLogger(__name__)

DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "buscar_hospedajes",
            "description": (
                "Busca y recomienda hospedajes publicados en SITUR-SMART, ordenados por "
                "afinidad con lo que pide el viajero. Usala siempre antes de mencionar "
                "cualquier hotel, precio o disponibilidad."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ciudad": {"type": "string", "description": "Ciudad o localidad, ej. 'Uyuni'."},
                    "presupuesto": {
                        "type": "number",
                        "description": "Precio maximo por noche en la moneda del hospedaje.",
                    },
                    "huespedes": {"type": "integer", "description": "Cantidad de personas."},
                    "estrellas": {"type": "integer", "description": "Categoria minima, 1 a 5."},
                    "servicios": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Servicios deseados, ej. ['wifi', 'desayuno'].",
                    },
                    "buscar": {"type": "string", "description": "Texto libre: nombre o zona."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detalle_hospedaje",
            "description": "Devuelve el detalle de un hospedaje y sus habitaciones con precio por noche.",
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "integer", "description": "id del hospedaje."}},
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_ciudades",
            "description": "Lista las ciudades donde hay hospedajes publicados.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _int(value, *, low: int, high: int) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def _text(value, limit: int = 80) -> str | None:
    return str(value).strip()[:limit] or None if value is not None else None


def _buscar_hospedajes(args: dict, cards: dict) -> dict:
    presupuesto = None
    if args.get("presupuesto") is not None:
        try:
            presupuesto = Decimal(str(args["presupuesto"]))
        except InvalidOperation:
            presupuesto = None
        if presupuesto is not None and presupuesto <= 0:
            presupuesto = None
    servicios = args.get("servicios") or []
    if not isinstance(servicios, list):
        servicios = [servicios]

    results = recommend(
        Criteria(
            ciudad=_text(args.get("ciudad")),
            presupuesto=presupuesto,
            huespedes=_int(args.get("huespedes"), low=1, high=100),
            estrellas=_int(args.get("estrellas"), low=1, high=5),
            servicios=[s for s in (_text(x, 40) for x in servicios[:6]) if s],
            buscar=_text(args.get("buscar")),
            limite=5,
        )
    )
    for card in results:
        cards[card["id"]] = card
    if not results:
        return {"resultados": [], "nota": "No hay hospedajes publicados que cumplan esos criterios."}
    return {"resultados": results}


def _detalle_hospedaje(args: dict, cards: dict) -> dict:
    lodging_id = _int(args.get("id"), low=1, high=2**62)
    lodging = public_lodgings().filter(id=lodging_id).first() if lodging_id else None
    if lodging is None:
        return {"error": "Ese hospedaje no existe o no esta publicado."}

    card = as_card(lodging)
    cards[card["id"]] = card
    rooms = public_rooms().filter(establishment=lodging).order_by("product__base_price", "id")[:10]
    return {
        **card,
        "descripcion": (lodging.product.description or "")[:600],
        "direccion": lodging.address,
        "check_in": lodging.check_in.strftime("%H:%M") if lodging.check_in else None,
        "check_out": lodging.check_out.strftime("%H:%M") if lodging.check_out else None,
        "habitaciones": [
            {
                "nombre": room.product.name,
                "precio_noche": str(room.product.base_price),
                "capacidad": room.product.max_capacity,
                "tipo_cama": room.bed_type,
                "incluye_desayuno": room.includes_breakfast,
            }
            for room in rooms
        ],
    }


def _listar_ciudades(args: dict, cards: dict) -> dict:
    names = (
        public_lodgings()
        .order_by()
        .values_list("product__city__name", flat=True)
        .distinct()
    )
    return {"ciudades": sorted(set(names))}


HANDLERS = {
    "buscar_hospedajes": _buscar_hospedajes,
    "detalle_hospedaje": _detalle_hospedaje,
    "listar_ciudades": _listar_ciudades,
}


def run(name: str, raw_arguments: str | None, cards: dict) -> str:
    """Ejecuta una herramienta y devuelve su resultado como JSON para el modelo.

    ``cards`` acumula los hospedajes que aparecieron, para que la respuesta de
    la API los devuelva como tarjetas enlazables ademas del texto.
    """
    handler = HANDLERS.get(name)
    if handler is None:
        return json.dumps({"error": f"Herramienta desconocida: {name}"})
    try:
        args = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        args = {}
    if not isinstance(args, dict):
        args = {}
    try:
        result = handler(args, cards)
    except Exception:
        # Una herramienta que falla no tiene que tumbar la conversacion: el
        # modelo recibe el error y puede disculparse o reformular.
        logger.exception("Fallo la herramienta %s del asistente", name)
        result = {"error": "No se pudo consultar la informacion en este momento."}
    return json.dumps(result, ensure_ascii=False, default=str)
