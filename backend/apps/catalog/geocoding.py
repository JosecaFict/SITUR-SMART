"""Cliente del geocodificador de openrouteservice (Pelias alojado por HeiGIT).

Vive en el backend por una razon concreta: la clave. ``OPENROUTESERVICE_API_KEY``
no puede viajar a Angular ni a Flutter, asi que el navegador nunca habla con el
proveedor -- habla con nuestra API, que firma la llamada y devuelve una forma
propia.

Esa forma propia no es burocracia. Pelias responde GeoJSON con las coordenadas
en ``[lon, lat]``, invertidas respecto de como las nombra todo el resto del
sistema; traducirlas aqui, una sola vez, mata de raiz el error clasico de
intercambiarlas. Ademas evita filtrar cabeceras de cuota o detalles del
proveedor, y le da a Angular y a Flutter un unico contrato que no cambia si
maniana se cambia de geocodificador.

Se usa ``urllib`` y no ``requests``, igual que ``apps/accounts/brevo.py``: es la
unica llamada saliente del proyecto junto con esa y no justifica una dependencia.

Nada de lo que se registra incluye la clave, la URL completa ni el cuerpo de la
respuesta del proveedor. Solo el nombre del endpoint, el estado y los
milisegundos: un geocodificador puede devolver el texto consultado dentro de su
mensaje de error, y ese texto es entrada del usuario.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

from .models import COORDINATE_PRECISION

logger = logging.getLogger(__name__)

# Host y rutas son constantes del modulo: la entrada del usuario solo entra como
# valor de query urlencodeado, nunca concatenada al host ni a la ruta. Asi no hay
# forma de redirigir la llamada a otro servidor.
PELIAS_BASE_URL = "https://api.heigit.org/pelias/v1"
SEARCH_PATH = "/search"
REVERSE_PATH = "/reverse"


class GeocodingUnavailable(Exception):
    """El proveedor no esta configurado o no pudo responder.

    Siempre se traduce a un 503 con un mensaje que no culpa al usuario: el pin
    manual sigue disponible y guardar no depende de esto.
    """


def is_configured() -> bool:
    """Indica si hay clave cargada, sin revelar nada de ella.

    Lo consume ``/api/v1/health/`` como booleano. Comprueba presencia, no
    validez: una clave vencida igual aparece como ``True``.
    """
    return bool(getattr(settings, "OPENROUTESERVICE_API_KEY", "").strip())


def _request(path: str, params: dict[str, str]) -> dict:
    """Llama al proveedor y devuelve el JSON, o levanta GeocodingUnavailable."""
    api_key = getattr(settings, "OPENROUTESERVICE_API_KEY", "").strip()
    if not api_key:
        # Ni se intenta la llamada: sin clave la respuesta seria un 401 del
        # proveedor y habriamos gastado una peticion para averiguar lo que ya
        # sabemos.
        logger.warning("Geocodificacion solicitada sin OPENROUTESERVICE_API_KEY configurada.")
        raise GeocodingUnavailable

    url = f"{PELIAS_BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "accept": "application/json",
            # La clave va en cabecera, no en la query: una query termina en los
            # logs de acceso de cualquier intermediario.
            "Authorization": api_key,
            "User-Agent": "SITUR-SMART/1.0",
        },
        method="GET",
    )

    timeout = getattr(settings, "OPENROUTESERVICE_TIMEOUT_SECONDS", 6)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Solo el codigo. El cuerpo puede repetir el texto consultado.
        logger.error("El geocodificador respondio %d en %s", exc.code, path)
        raise GeocodingUnavailable from exc
    except urllib.error.URLError as exc:
        logger.error("No se pudo contactar al geocodificador en %s: %s", path, exc.reason)
        raise GeocodingUnavailable from exc
    except (TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        # UnicodeDecodeError va explicito aunque herede de ValueError: un cuerpo
        # con bytes que no son UTF-8 es tan inutilizable como un JSON roto y
        # tiene que salir como 503, nunca escaparse como 500. Solo se registra
        # el tipo de error: ni la URL completa ni el cuerpo, que podria repetir
        # el texto consultado.
        logger.error("Respuesta inutilizable del geocodificador en %s: %s", path, type(exc).__name__)
        raise GeocodingUnavailable from exc

    if not isinstance(payload, dict):
        logger.error("El geocodificador devolvio algo que no es un objeto en %s", path)
        raise GeocodingUnavailable
    return payload


def _coordinate(value) -> Decimal | None:
    """Redondea a la precision que guarda la columna, o descarta el valor.

    ``ROUND_HALF_UP`` explicito, la misma estrategia que ``CoordinateField`` al
    validar la entrada y que ``_normalize_coordinates`` en la capa de servicio.
    Dejarlo al contexto por omision de ``decimal`` traeria ``ROUND_HALF_EVEN``, y
    entonces el mismo punto podria guardarse con un ultimo decimal distinto
    segun por donde entrara: elegido en el buscador o colocado a mano.
    """
    try:
        return Decimal(str(value)).quantize(COORDINATE_PRECISION, rounding=ROUND_HALF_UP)
    except (ArithmeticError, TypeError, ValueError):
        return None


def _place(feature) -> dict | None:
    """Traduce un Feature de Pelias al contrato de SITUR-SMART.

    Devuelve ``None`` si el resultado no trae un punto usable. Pelias entrega
    ``coordinates: [lon, lat]``; aqui se separan con nombre para que nadie
    vuelva a confundir el orden.
    """
    if not isinstance(feature, dict):
        return None
    coordinates = (feature.get("geometry") or {}).get("coordinates") or []
    if len(coordinates) < 2:
        return None
    longitude = _coordinate(coordinates[0])
    latitude = _coordinate(coordinates[1])
    if latitude is None or longitude is None:
        return None
    # Un punto fuera de rango no se corrige, se descarta: el CHECK de la columna
    # lo rechazaria y es mejor no ofrecerlo que ofrecerlo y fallar al guardar.
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None

    properties = feature.get("properties") or {}
    return {
        "etiqueta": properties.get("label") or properties.get("name") or "",
        "nombre": properties.get("name") or "",
        "localidad": properties.get("locality"),
        "region": properties.get("region"),
        "pais": properties.get("country"),
        "latitud": latitude,
        "longitud": longitude,
        "confianza": properties.get("confidence"),
        "capa": properties.get("layer"),
    }


def _places(payload: dict, limit: int) -> list[dict]:
    features = payload.get("features")
    if not isinstance(features, list):
        return []
    places = [place for place in map(_place, features) if place is not None]
    return places[:limit]


def search_places(
    *, text: str, limit: int, center: tuple[Decimal, Decimal] | None = None
) -> list[dict]:
    """Busca direcciones por texto, restringido a Bolivia.

    ``boundary.country`` es un recorte duro y ``focus.point`` solo un sesgo de
    ranking. Es deliberado: la busqueda no debe salir del pais, pero un
    hospedaje rural legitimo puede estar a ochenta kilometros de la ciudad
    elegida y un recorte circular lo volveria invisible.
    """
    params = {
        "text": text,
        "boundary.country": getattr(settings, "GEOCODING_COUNTRY", "BOL"),
        "size": str(limit),
    }
    if center is not None:
        params["focus.point.lat"] = str(center[0])
        params["focus.point.lon"] = str(center[1])
    return _places(_request(SEARCH_PATH, params), limit)


def reverse_geocode(*, latitude: Decimal, longitude: Decimal) -> dict | None:
    """Da la direccion de un punto, o ``None`` si no hay nada cerca."""
    params = {"point.lat": str(latitude), "point.lon": str(longitude), "size": "1"}
    places = _places(_request(REVERSE_PATH, params), 1)
    return places[0] if places else None
