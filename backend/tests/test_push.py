"""Lectura de la credencial de Firebase y armado del mensaje (sin red ni base)."""

import base64
import json

import pytest

from apps.notifications import push
from apps.notifications.models import Notification

CLAVE = {
    "type": "service_account",
    "project_id": "situr-smart-pruebas",
    "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n",
    "client_email": "firebase-adminsdk@situr-smart-pruebas.iam.gserviceaccount.com",
}


@pytest.fixture(autouse=True)
def sin_cache(settings):
    settings.FIREBASE_CREDENTIALS_BASE64 = ""
    settings.FIREBASE_SERVICE_ACCOUNT_JSON = ""
    push._service_account.cache_clear()
    yield
    push._service_account.cache_clear()


def test_sin_credencial_no_esta_configurado():
    assert push.is_configured() is False


def test_lee_la_clave_en_base64(settings):
    settings.FIREBASE_CREDENTIALS_BASE64 = base64.b64encode(json.dumps(CLAVE).encode()).decode()
    assert push.is_configured() is True
    assert push._service_account()["project_id"] == "situr-smart-pruebas"


def test_lee_la_clave_en_json(settings):
    settings.FIREBASE_SERVICE_ACCOUNT_JSON = json.dumps(CLAVE)
    assert push.is_configured() is True


@pytest.mark.parametrize("valor", ["no-es-base64!!", base64.b64encode(b"{no json").decode()])
def test_una_credencial_rota_no_cuenta_como_configurada(settings, valor):
    settings.FIREBASE_CREDENTIALS_BASE64 = valor
    assert push.is_configured() is False


def test_un_json_que_no_es_cuenta_de_servicio_no_sirve(settings):
    # Error tipico: pegar el google-services.json de la app en lugar de la clave.
    settings.FIREBASE_SERVICE_ACCOUNT_JSON = json.dumps({"project_info": {"project_id": "x"}})
    assert push.is_configured() is False


def test_el_mensaje_lleva_textos_y_a_donde_navegar():
    aviso = Notification(
        id=7,
        kind="RESERVA_CONFIRMADA",
        title="¡Reserva confirmada!",
        message="Hotel Los Tajibos · 10 oct 2026.",
        data={"reserva_id": 12, "codigo": "R-ABC", "nada": None},
    )
    mensaje = push.build_message("token-1", aviso)["message"]

    assert mensaje["token"] == "token-1"
    assert mensaje["notification"] == {"title": "¡Reserva confirmada!", "body": "Hotel Los Tajibos · 10 oct 2026."}
    # FCM solo acepta textos en data.
    assert mensaje["data"] == {
        "reserva_id": "12",
        "codigo": "R-ABC",
        "notificacion_id": "7",
        "tipo": "RESERVA_CONFIRMADA",
    }
    assert mensaje["android"]["notification"]["channel_id"] == push.ANDROID_CHANNEL_ID
