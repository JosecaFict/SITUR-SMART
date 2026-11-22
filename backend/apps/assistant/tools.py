"""Herramientas que el modelo puede pedir que ejecutemos (function calling).

El modelo nunca toca la base: describe que quiere buscar y este modulo hace la
consulta con los mismos filtros publicos del Marketplace. Solo ve la oferta
publicada de empresas activas, igual que un visitante anonimo. Las herramientas
de tours, promociones, intereses y paquetes estan en ``travel_tools.py``.

Cada herramienta valida y acota sus argumentos: lo que llega lo escribio un
modelo de lenguaje y puede venir con tipos equivocados o valores absurdos.
"""

import json
import logging
from decimal import Decimal, InvalidOperation

from apps.catalog.services import public_lodgings, public_rooms

from . import travel_tools
from .recommendations import Criteria, as_card, recommend
from .schema import for_model, nullable_optionals
from .travel_tools import Collected

logger = logging.getLogger(__name__)

def _tool(name: str, description: str, properties: dict | None = None, required=()) -> dict:
    parameters = {"type": "object", "properties": properties or {}}
    if required:
        parameters["required"] = list(required)
    return {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}


_ID = {"id": {"type": "integer"}}
_CIUDAD = {"type": "string", "description": "Ciudad o localidad"}

# Descripciones cortas a proposito: viajan en cada llamada y cuentan contra la
# cuota de tokens por minuto del proveedor. Las reglas de uso estan en el prompt.
DEFINITIONS = [
    nullable_optionals(definition)
    for definition in (
        _tool(
            "buscar_hospedajes",
            "Hospedajes publicados, ordenados por afinidad.",
            {
                "ciudad": _CIUDAD,
                "presupuesto": {"type": "number", "description": "Maximo por noche"},
                "huespedes": {"type": "integer"},
                "estrellas": {"type": "integer", "description": "Minimo, 1 a 5"},
                "servicios": {"type": "array", "items": {"type": "string"}},
                "buscar": {"type": "string", "description": "Nombre o zona"},
            },
        ),
        _tool("detalle_hospedaje", "Detalle de un hospedaje y sus habitaciones.", _ID, ["id"]),
        _tool("listar_ciudades", "Ciudades con oferta publicada y cuantos hospedajes y tours tiene cada una."),
        _tool(
            "buscar_tours",
            "Tours y experiencias publicados con salidas abiertas.",
            {
                "ciudad": _CIUDAD,
                "tipo": {"type": "string", "enum": ["TOUR", "EXPERIENCIA"]},
                "presupuesto": {"type": "number", "description": "Maximo por persona"},
                "dificultad": {"type": "string", "enum": ["BAJA", "MEDIA", "ALTA"]},
                "buscar": {"type": "string", "description": "Texto libre"},
            },
        ),
        _tool("detalle_tour", "Recorrido, que incluye y proximas salidas con lugares libres.", _ID, ["id"]),
        _tool("promociones_vigentes", "Promociones vigentes con descuento y precio final.", {"ciudad": _CIUDAD}),
        _tool("mis_intereses", "Ciudades y tipos que le interesan al viajero segun su actividad."),
        _tool(
            "estimar_paquete",
            "Costo estimado de hospedaje y/o tours para N personas y noches.",
            {
                "hospedaje_id": {"type": "integer"},
                "noches": {"type": "integer"},
                "personas": {"type": "integer"},
                "tour_ids": {"type": "array", "items": {"type": "integer"}},
            },
        ),
    )
]


def _int(value, *, low: int, high: int) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def _text(value, limit: int = 80) -> str | None:
    return str(value).strip()[:limit] or None if value is not None else None


def _buscar_hospedajes(args: dict, collected: Collected, **_) -> dict:
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
        ),
        contact=True,
    )
    for card in results:
        collected.hospedajes[card["id"]] = card
    if not results:
        return travel_tools.with_alternatives(
            {"resultados": [], "nota": "No hay hospedajes publicados que cumplan esos criterios."},
            "hospedajes",
        )
    return {"resultados": results}


def _detalle_hospedaje(args: dict, collected: Collected, **_) -> dict:
    lodging_id = _int(args.get("id"), low=1, high=2**62)
    lodging = public_lodgings().filter(id=lodging_id).first() if lodging_id else None
    if lodging is None:
        return {"error": "Ese hospedaje no existe o no esta publicado."}

    card = as_card(lodging, contact=True)
    collected.hospedajes[card["id"]] = card
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


HANDLERS = {
    "buscar_hospedajes": _buscar_hospedajes,
    "detalle_hospedaje": _detalle_hospedaje,
    "listar_ciudades": travel_tools.listar_ciudades,
    "buscar_tours": travel_tools.buscar_tours,
    "detalle_tour": travel_tools.detalle_tour,
    "promociones_vigentes": travel_tools.promociones_vigentes,
    "mis_intereses": travel_tools.mis_intereses,
    "estimar_paquete": travel_tools.estimar_paquete,
}


def run(name: str, raw_arguments: str | None, collected: Collected, user=None) -> str:
    """Ejecuta una herramienta y devuelve su resultado como JSON para el modelo.

    ``collected`` acumula los hospedajes, tours y promociones que aparecieron,
    para que la respuesta de la API los devuelva como tarjetas enlazables
    ademas del texto. ``user`` es el viajero, para ``mis_intereses``.
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
        result = handler(args, collected, user=user)
    except Exception:
        # Una herramienta que falla no tiene que tumbar la conversacion: el
        # modelo recibe el error y puede disculparse o reformular.
        logger.exception("Fallo la herramienta %s del asistente", name)
        result = {"error": "No se pudo consultar la informacion en este momento."}
    return json.dumps(for_model(result), ensure_ascii=False, default=str)
