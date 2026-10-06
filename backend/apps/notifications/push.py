"""Envio de notificaciones push con Firebase Cloud Messaging (API HTTP v1).

La credencial es la clave de la cuenta de servicio del proyecto de Firebase,
cargada en Railway como ``FIREBASE_CREDENTIALS_BASE64`` (el JSON en base64) o
``FIREBASE_SERVICE_ACCOUNT_JSON`` (el JSON tal cual). Solo la lee este modulo y
nunca viaja a Angular ni a Flutter.

Sin credencial no falla nada: el aviso queda en la bandeja de la app y el push
simplemente no sale. Un error de Firebase tampoco corta el flujo que avisa
(un pago confirmado sigue confirmado).
"""

import base64
import binascii
import json
import logging
import threading
from functools import lru_cache

from django.conf import settings
from django.db import connection

from .models import Notification, PushDevice

logger = logging.getLogger(__name__)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_SEND_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
FCM_TIMEOUT_SECONDS = 10
# Codigos con los que Firebase dice que el token ya no sirve (app desinstalada,
# token rotado o de otro proyecto). Esos celulares se borran.
STALE_TOKEN_ERRORS = {"UNREGISTERED", "SENDER_ID_MISMATCH"}
# Canal de Android que crea la app; si no existe, Android usa uno generico.
ANDROID_CHANNEL_ID = "situr_avisos"


@lru_cache(maxsize=1)
def _service_account() -> dict | None:
    raw = getattr(settings, "FIREBASE_CREDENTIALS_BASE64", "").strip()
    if raw:
        try:
            raw = base64.b64decode(raw, validate=False).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            logger.warning("FIREBASE_CREDENTIALS_BASE64 no es base64 valido.")
            return None
    else:
        raw = getattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        return None
    try:
        info = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("La credencial de Firebase no es un JSON valido.")
        return None
    if not isinstance(info, dict) or not info.get("project_id") or not info.get("private_key"):
        logger.warning("La credencial de Firebase no es una clave de cuenta de servicio.")
        return None
    return info


def is_configured() -> bool:
    """Hay una clave de cuenta de servicio legible. No comprueba que siga vigente."""
    return _service_account() is not None


@lru_cache(maxsize=1)
def _session():
    # Import diferido: google-auth solo hace falta si hay credencial.
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_info(
        _service_account(), scopes=[FCM_SCOPE]
    )
    return AuthorizedSession(credentials)


def build_message(token: str, notification: Notification) -> dict:
    # FCM solo acepta textos en "data". La app usa reserva_id para abrir la reserva.
    data = {key: str(value) for key, value in (notification.data or {}).items() if value is not None}
    data.update({"notificacion_id": str(notification.id), "tipo": notification.kind})
    return {
        "message": {
            "token": token,
            "notification": {"title": notification.title, "body": notification.message},
            "data": data,
            "android": {
                "priority": "HIGH",
                "notification": {"channel_id": ANDROID_CHANNEL_ID},
            },
        }
    }


def send_one(message: dict) -> str | None:
    """Envia un mensaje. Devuelve None si salio, o el codigo de error de FCM."""
    url = FCM_SEND_URL.format(project_id=_service_account()["project_id"])
    try:
        response = _session().post(url, json=message, timeout=FCM_TIMEOUT_SECONDS)
    except Exception as exc:  # red, DNS o credencial rechazada al pedir el token OAuth
        logger.warning("No se pudo contactar a Firebase: %s", exc)
        return "UNAVAILABLE"
    if response.status_code == 200:
        return None
    code = _error_code(response)
    logger.info("Firebase rechazo un push (%s): %s", response.status_code, code)
    return code


def _error_code(response) -> str:
    try:
        error = response.json().get("error", {})
    except ValueError:
        return str(response.status_code)
    for detail in error.get("details", []):
        if detail.get("errorCode"):
            return detail["errorCode"]
    return error.get("status") or str(response.status_code)


def push_notification(notification: Notification) -> None:
    """Manda el aviso a todos los celulares del usuario.

    Los tokens se leen aca; el envio va en un hilo aparte (como el correo) para
    no demorar al webhook de Stripe ni a quien llamo a ``notify``.
    """
    if not is_configured():
        return
    tokens = list(PushDevice.objects.filter(user_id=notification.user_id).values_list("token", flat=True))
    if not tokens:
        return
    messages = [build_message(token, notification) for token in tokens]
    if getattr(settings, "PUSH_EN_SEGUNDO_PLANO", True):
        threading.Thread(target=_deliver_in_thread, args=(messages,), daemon=True).start()
    else:
        _deliver(messages)


def _deliver(messages: list[dict]) -> None:
    stale = [m["message"]["token"] for m in messages if send_one(m) in STALE_TOKEN_ERRORS]
    if stale:
        PushDevice.objects.filter(token__in=stale).delete()


def _deliver_in_thread(messages: list[dict]) -> None:
    try:
        _deliver(messages)
    except Exception:
        logger.exception("Fallo el envio de notificaciones push.")
    finally:
        # El hilo abrio su propia conexion si borro tokens; se cierra aqui.
        connection.close()
