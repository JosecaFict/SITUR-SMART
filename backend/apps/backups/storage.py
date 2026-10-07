"""Donde se guardan las copias automaticas: Cloudinary, como archivo privado.

Fuera de Railway a proposito: si se pierde la base, la copia sigue alli. El
archivo se sube con ``type="authenticated"``: no tiene URL publica y solo se
baja con un enlace firmado que vence en minutos, generado por el backend para
un SuperAdmin con sesion.
"""

import time

import cloudinary.uploader
import cloudinary.utils

from apps.media.services import CloudinaryService

FOLDER = "situr-smart/respaldos"
RESOURCE = {"resource_type": "raw", "type": "authenticated"}
LINK_SECONDS = 600


class StorageUnavailable(Exception):
    """Cloudinary no esta configurado o rechazo la operacion."""


def is_configured() -> bool:
    return CloudinaryService.is_configured()


def _init() -> None:
    if not is_configured():
        raise StorageUnavailable("Cloudinary no está configurado.")
    CloudinaryService._initialize()


def upload(file_obj, filename: str) -> str:
    """Sube la copia y devuelve su identificador en el almacen."""
    _init()
    try:
        result = cloudinary.uploader.upload(
            file_obj, public_id=f"{FOLDER}/{filename}", overwrite=False, **RESOURCE
        )
    except Exception as exc:  # red, cuota o archivo demasiado grande para el plan
        raise StorageUnavailable(str(exc)) from exc
    return result["public_id"]


def download_link(storage_id: str) -> str:
    """Enlace firmado para bajar la copia, valido unos minutos."""
    _init()
    return cloudinary.utils.private_download_url(
        storage_id, "", attachment=True, expires_at=int(time.time()) + LINK_SECONDS, **RESOURCE
    )


def delete(storage_id: str) -> None:
    _init()
    try:
        cloudinary.uploader.destroy(storage_id, invalidate=True, **RESOURCE)
    except Exception as exc:
        raise StorageUnavailable(str(exc)) from exc
