"""Celulares registrados y push de Firebase, contra PostgreSQL real.

Firebase se reemplaza por una funcion que anota lo enviado: aqui se prueba a
quien le llega y que se hace con los tokens vencidos, no la red.
"""

from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from apps.bookings import events
from apps.notifications import push
from apps.notifications.models import PushDevice

from .datos import (
    OTRO_TURISTA,
    TURISTA,
    _pedido_habitacion,
    _session_id,
    _webhook,
    cliente,
    habitacion_publicada,
)

pytestmark = pytest.mark.django_db(transaction=False)


@pytest.fixture
def firebase(monkeypatch):
    """Firebase falso. ``rechazos`` mapea token -> codigo de error de FCM."""

    falso = SimpleNamespace(enviados=[], rechazos={})

    def enviar(message):
        falso.enviados.append(message["message"])
        return falso.rechazos.get(message["message"]["token"])

    monkeypatch.setattr(push, "is_configured", lambda: True)
    monkeypatch.setattr(push, "send_one", enviar)
    monkeypatch.setattr(events, "send_email", lambda **kwargs: True)
    return falso


def _registrar(token, email=TURISTA):
    return cliente(email).post("/api/v1/me/dispositivos/", {"token": token}, format="json")


def _confirmar(django_capture_on_commit_callbacks, email=TURISTA):
    creada = cliente(email).post(
        "/api/v1/me/reservas/", _pedido_habitacion(habitacion_publicada()), format="json"
    ).json()
    with django_capture_on_commit_callbacks(execute=True):
        _webhook("checkout.session.completed", _session_id(creada["id"]))
    return creada


def test_registrar_el_celular_es_idempotente():
    assert _registrar("token-a").status_code == 204
    assert _registrar("token-a").status_code == 204

    [device] = PushDevice.objects.all()
    assert device.user.email == TURISTA
    assert device.platform == "ANDROID"


def test_si_entra_otra_cuenta_en_el_celular_el_token_pasa_a_ella():
    _registrar("token-a")
    _registrar("token-a", OTRO_TURISTA)

    [device] = PushDevice.objects.all()
    assert device.user.email == OTRO_TURISTA


def test_quitar_solo_borra_el_celular_propio():
    _registrar("token-a")
    assert cliente(OTRO_TURISTA).post(
        "/api/v1/me/dispositivos/quitar/", {"token": "token-a"}, format="json"
    ).status_code == 204
    assert PushDevice.objects.count() == 1

    cliente().post("/api/v1/me/dispositivos/quitar/", {"token": "token-a"}, format="json")
    assert not PushDevice.objects.exists()


def test_validaciones_y_sesion():
    assert APIClient().post("/api/v1/me/dispositivos/", {"token": "x"}, format="json").status_code == 401
    assert cliente().post("/api/v1/me/dispositivos/", {}, format="json").status_code == 400
    assert cliente().post(
        "/api/v1/me/dispositivos/", {"token": "x", "plataforma": "WINDOWS"}, format="json"
    ).status_code == 400


def test_al_confirmar_la_reserva_llega_el_push_a_cada_celular(
    stripe, firebase, django_capture_on_commit_callbacks
):
    _registrar("celular")
    _registrar("tablet")
    _registrar("de-otro", OTRO_TURISTA)

    creada = _confirmar(django_capture_on_commit_callbacks)

    assert sorted(m["token"] for m in firebase.enviados) == ["celular", "tablet"]
    mensaje = firebase.enviados[0]
    assert mensaje["notification"]["title"] == "¡Reserva confirmada!"
    assert creada["codigo"] in mensaje["notification"]["body"]
    assert mensaje["data"]["reserva_id"] == str(creada["id"])
    assert mensaje["data"]["tipo"] == "RESERVA_CONFIRMADA"


def test_un_token_que_firebase_da_por_muerto_se_borra(
    stripe, firebase, django_capture_on_commit_callbacks
):
    _registrar("vivo")
    _registrar("desinstalado")
    _registrar("caido")
    firebase.rechazos = {"desinstalado": "UNREGISTERED", "caido": "UNAVAILABLE"}

    _confirmar(django_capture_on_commit_callbacks)

    # Un error pasajero (UNAVAILABLE) no borra el celular; uno definitivo si.
    assert sorted(PushDevice.objects.values_list("token", flat=True)) == ["caido", "vivo"]


def test_sin_firebase_configurado_el_aviso_igual_queda_en_la_bandeja(
    stripe, firebase, monkeypatch, django_capture_on_commit_callbacks
):
    monkeypatch.setattr(push, "is_configured", lambda: False)
    _registrar("celular")

    _confirmar(django_capture_on_commit_callbacks)

    assert firebase.enviados == []
    assert cliente().get("/api/v1/me/notificaciones/no-leidas/").json() == {"no_leidas": 1}
