"""Comprobante PDF y vuelta a la app tras pagar, contra PostgreSQL real."""

import base64
from urllib.parse import urlparse

import pytest
from rest_framework.test import APIClient

from apps.bookings import events

from .datos import TURISTA, _pedido_habitacion, _session_id, _webhook, cliente, habitacion_publicada

pytestmark = pytest.mark.django_db(transaction=False)


@pytest.fixture
def correos(monkeypatch):
    enviados = []
    monkeypatch.setattr(events, "send_email", lambda **kwargs: enviados.append(kwargs) or True)
    return enviados


def _pagada(django_capture_on_commit_callbacks):
    creada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(habitacion_publicada()), format="json").json()
    with django_capture_on_commit_callbacks(execute=True):
        _webhook("checkout.session.completed", _session_id(creada["id"]))
    return creada


def test_el_correo_de_confirmacion_lleva_el_pdf_y_el_boton(stripe, correos, django_capture_on_commit_callbacks):
    creada = _pagada(django_capture_on_commit_callbacks)

    [correo] = correos
    assert correo["to_email"] == TURISTA
    [adjunto] = correo["attachments"]
    assert adjunto["name"] == f"comprobante-{creada['codigo']}.pdf"
    assert base64.b64decode(adjunto["content"]).startswith(b"%PDF")
    assert "Descargar comprobante" in correo["html"]
    assert "/api/v1/comprobantes/" in correo["html"]


def test_la_app_pide_el_enlace_y_el_navegador_baja_el_pdf(stripe, correos, django_capture_on_commit_callbacks):
    creada = _pagada(django_capture_on_commit_callbacks)

    enlace = cliente().get(f"/api/v1/me/reservas/{creada['id']}/comprobante/").json()["url"]
    pdf = APIClient().get(urlparse(enlace).path)  # sin sesion: el enlace va firmado
    assert pdf.status_code == 200
    assert pdf["Content-Type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert creada["codigo"] in pdf["Content-Disposition"]


def test_sin_pagar_no_hay_comprobante_y_un_enlace_falso_no_sirve(stripe):
    creada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(habitacion_publicada()), format="json").json()
    assert cliente().get(f"/api/v1/me/reservas/{creada['id']}/comprobante/").status_code == 400
    assert cliente("turista2@situr.com.bo").get(f"/api/v1/me/reservas/{creada['id']}/comprobante/").status_code == 404
    assert APIClient().get("/api/v1/comprobantes/inventado:token/").status_code == 404


def test_al_volver_de_stripe_la_pagina_reabre_la_app_en_la_reserva(stripe):
    creada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(habitacion_publicada()), format="json").json()
    [sesion] = stripe.created
    assert f"id={creada['id']}" in sesion["success_url"]

    pagina = APIClient().get(urlparse(sesion["success_url"]).path + "?" + urlparse(sesion["success_url"]).query)
    html = pagina.content.decode()
    assert f"situr-smart://app/reserva/{creada['id']}?pago=exito" in html
    assert "Volver a SITUR-SMART" in html

    cancelada = APIClient().get(urlparse(sesion["cancel_url"]).path + "?" + urlparse(sesion["cancel_url"]).query)
    assert f"situr-smart://app/reserva/{creada['id']}?pago=cancelado" in cancelada.content.decode()


def test_desde_la_web_stripe_vuelve_a_mis_viajes(stripe, settings):
    settings.WEB_APP_URL = "https://web.test"
    creada = cliente().post(
        "/api/v1/me/reservas/?origen=web", _pedido_habitacion(habitacion_publicada()), format="json"
    ).json()
    [sesion] = stripe.created
    assert sesion["success_url"] == f"https://web.test/mis-viajes/{creada['id']}?pago=exito"
    assert sesion["cancel_url"] == f"https://web.test/mis-viajes/{creada['id']}?pago=cancelado"
