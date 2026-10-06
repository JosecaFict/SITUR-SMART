"""Avisos y correo que dispara una reserva, contra PostgreSQL real."""

import pytest
from rest_framework.test import APIClient

from apps.bookings import events
from apps.notifications.models import Notification

from .datos import (
    OTRO_TURISTA,
    TURISTA,
    _pedido_habitacion,
    _session_id,
    _vencer,
    _webhook,
    cliente,
    habitacion_publicada,
)

pytestmark = pytest.mark.django_db(transaction=False)


@pytest.fixture
def correos(monkeypatch):
    enviados: list[dict] = []

    def capturar(**kwargs):
        enviados.append(kwargs)
        return True

    monkeypatch.setattr(events, "send_email", capturar)
    return enviados


def _confirmar(django_capture_on_commit_callbacks, room=None):
    room = room or habitacion_publicada()
    creada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(room), format="json").json()
    with django_capture_on_commit_callbacks(execute=True):
        _webhook("checkout.session.completed", _session_id(creada["id"]))
    return creada


def test_al_confirmar_llega_el_aviso_y_el_correo(stripe, correos, django_capture_on_commit_callbacks):
    creada = _confirmar(django_capture_on_commit_callbacks)

    [aviso] = Notification.objects.filter(user__email=TURISTA)
    assert aviso.kind == "RESERVA_CONFIRMADA"
    assert creada["codigo"] in aviso.message
    assert aviso.data == {"reserva_id": creada["id"], "codigo": creada["codigo"]}

    [correo] = correos
    assert correo["to_email"] == TURISTA
    assert creada["codigo"] in correo["subject"]
    assert creada["codigo"] in correo["html"]
    assert "Total pagado" in correo["html"]


def test_un_aviso_repetido_de_stripe_no_duplica_nada(stripe, correos, django_capture_on_commit_callbacks):
    creada = _confirmar(django_capture_on_commit_callbacks)
    with django_capture_on_commit_callbacks(execute=True):
        _webhook("checkout.session.completed", _session_id(creada["id"]))

    assert Notification.objects.count() == 1
    assert len(correos) == 1


def test_una_reserva_vencida_avisa_sin_correo(stripe, correos, django_capture_on_commit_callbacks):
    creada = cliente().post(
        "/api/v1/me/reservas/", _pedido_habitacion(habitacion_publicada()), format="json"
    ).json()
    _vencer(creada["id"])
    stripe.sessions[_session_id(creada["id"])]["status"] = "expired"

    with django_capture_on_commit_callbacks(execute=True):
        cliente().get(f"/api/v1/me/reservas/{creada['id']}/")

    [aviso] = Notification.objects.all()
    assert aviso.kind == "RESERVA_VENCIDA"
    assert correos == []


def test_cancelar_uno_mismo_no_genera_aviso(stripe, correos, django_capture_on_commit_callbacks):
    creada = cliente().post(
        "/api/v1/me/reservas/", _pedido_habitacion(habitacion_publicada()), format="json"
    ).json()
    with django_capture_on_commit_callbacks(execute=True):
        cliente().post(f"/api/v1/me/reservas/{creada['id']}/cancelar/")
    assert not Notification.objects.exists()


def test_la_bandeja_cuenta_y_marca_leidas(stripe, correos, django_capture_on_commit_callbacks):
    _confirmar(django_capture_on_commit_callbacks)
    api = cliente()

    assert api.get("/api/v1/me/notificaciones/no-leidas/").json() == {"no_leidas": 1}
    pagina = api.get("/api/v1/me/notificaciones/").json()
    assert pagina["count"] == 1
    aviso = pagina["results"][0]
    assert aviso["leida"] is False

    assert api.post(f"/api/v1/me/notificaciones/{aviso['id']}/leer/").json()["leida"] is True
    assert api.get("/api/v1/me/notificaciones/no-leidas/").json() == {"no_leidas": 0}


def test_marcar_todas_y_aislamiento_entre_usuarios(stripe, correos, django_capture_on_commit_callbacks):
    _confirmar(django_capture_on_commit_callbacks)
    aviso = Notification.objects.get()

    otro = cliente(OTRO_TURISTA)
    assert otro.get("/api/v1/me/notificaciones/no-leidas/").json() == {"no_leidas": 0}
    assert otro.post(f"/api/v1/me/notificaciones/{aviso.id}/leer/").status_code == 404

    assert cliente().post("/api/v1/me/notificaciones/leer-todas/").status_code == 204
    assert cliente().get("/api/v1/me/notificaciones/no-leidas/").json() == {"no_leidas": 0}
    assert APIClient().get("/api/v1/me/notificaciones/").status_code == 401


def test_sin_brevo_configurado_la_reserva_igual_se_confirma(stripe, settings, django_capture_on_commit_callbacks):
    settings.BREVO_API_KEY = ""
    creada = _confirmar(django_capture_on_commit_callbacks)
    assert cliente().get(f"/api/v1/me/reservas/{creada['id']}/").json()["estado"] == "CONFIRMADA"
    assert Notification.objects.filter(kind="RESERVA_CONFIRMADA").exists()
