"""Ajustes de las definiciones de herramientas y de sus resultados.

- Parametros opcionales que aceptan ``null``: algunos modelos (gpt-oss en Groq)
  mandan ``null`` en vez de omitir un filtro, y Groq valida contra el esquema y
  rechaza la llamada entera con un 400. Los manejadores ya tratan ``null`` como
  "sin filtro".
- Resultados para el modelo sin los campos que solo usan las tarjetas de la app
  (imagen, enlaces, puntaje): cada token cuenta contra la cuota por minuto.
"""

import copy

# Campos que van a las tarjetas pero el modelo no necesita para responder.
CARD_ONLY_FIELDS = frozenset({"imagen_url", "url", "puntaje", "whatsapp_url"})


def nullable_optionals(definition: dict) -> dict:
    """Copia de la definicion con cada parametro no requerido aceptando ``null``."""
    result = copy.deepcopy(definition)
    parameters = result["function"].get("parameters") or {}
    required = set(parameters.get("required") or [])
    for name, spec in (parameters.get("properties") or {}).items():
        if name in required:
            continue
        kind = spec.get("type")
        if isinstance(kind, str):
            spec["type"] = [kind, "null"]
        if "enum" in spec and None not in spec["enum"]:
            spec["enum"] = [*spec["enum"], None]
    return result


def for_model(value):
    """Copia del resultado sin los campos que solo usan las tarjetas."""
    if isinstance(value, dict):
        return {key: for_model(item) for key, item in value.items() if key not in CARD_ONLY_FIELDS}
    if isinstance(value, list):
        return [for_model(item) for item in value]
    return value
