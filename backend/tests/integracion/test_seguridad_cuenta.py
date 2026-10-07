"""Seguridad y autogestion de la cuenta del turista, contra PostgreSQL real."""

import re
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import security
from apps.accounts.models import User
from apps.bookings.models import Booking

from .datos import (
    TURISTA,
    _pedido_habitacion,
    _session_id,
    _webhook,
    cliente,
    habitacion_publicada,
    tour_publicado,
)

pytestmark = pytest.mark.django_db(transaction=False)

PASSWORD = "Admin123*"


@pytest.fixture
def correos(monkeypatch):
    enviados = []
    monkeypatch.setattr(security, "send_email", lambda **kwargs: enviados.append(kwargs) or True)
    return enviados


def _login(email=TURISTA, password=PASSWORD):
    return APIClient().post("/api/v1/auth/login/", {"email": email, "password": password}, format="json")


def _con_token(access: str) -> APIClient:
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return api


def _registrar(django_capture_on_commit_callbacks, email="nueva@viajera.bo"):
    with django_capture_on_commit_callbacks(execute=True):
        data = APIClient().post(
            "/api/v1/auth/register/",
            {"nombres": "Nueva", "apellidos": "Viajera", "email": email, "password": "ClaveSegura1"},
            format="json",
        ).json()
    return data


def _codigo(correo) -> str:
    return re.search(r">(\d{6})<", correo["html"]).group(1)


def test_sin_correo_verificado_no_reserva_y_con_el_codigo_si(stripe, correos, django_capture_on_commit_callbacks):
    registro = _registrar(django_capture_on_commit_callbacks)
    api = _con_token(registro["access"])
    assert api.get("/api/v1/auth/me/").json()["correo_verificado"] is False

    pedido = _pedido_habitacion(habitacion_publicada())
    bloqueada = api.post("/api/v1/me/reservas/", pedido, format="json")
    assert bloqueada.status_code == 403
    assert "Verifica tu correo" in bloqueada.json()["error"]["message"]

    [correo] = correos  # el codigo sale solo al registrarse
    assert api.post("/api/v1/auth/correo/verificar/", {"codigo": "000000"}, format="json").status_code == 400
    assert api.post("/api/v1/auth/correo/verificar/", {"codigo": _codigo(correo)}, format="json").json()["correo_verificado"] is True
    assert api.post("/api/v1/me/reservas/", pedido, format="json").status_code == 201


def test_no_se_puede_pedir_codigos_seguidos(correos, django_capture_on_commit_callbacks):
    registro = _registrar(django_capture_on_commit_callbacks)
    respuesta = _con_token(registro["access"]).post("/api/v1/auth/correo/enviar-codigo/")
    assert respuesta.status_code == 400


def test_cinco_contrasenas_mal_traban_la_cuenta():
    for _ in range(security.MAX_FAILED_LOGINS):
        assert _login(password="incorrecta").status_code == 401
    trabada = _login()
    assert trabada.status_code == 401
    assert "Demasiados intentos" in trabada.json()["error"]["message"]

    User.objects.filter(email=TURISTA).update(locked_until=timezone.now() - timedelta(minutes=1))
    assert _login().status_code == 200
    assert User.objects.get(email=TURISTA).failed_logins == 0


def test_cambiar_la_contrasena_cierra_las_demas_sesiones(correos):
    otra = _login().json()
    actual = _login().json()
    api = _con_token(actual["access"])

    assert api.post("/api/v1/auth/me/contrasena/", {"actual": "mal", "nueva": "OtraClave99"}, format="json").status_code == 400
    nuevos = api.post("/api/v1/auth/me/contrasena/", {"actual": PASSWORD, "nueva": "OtraClave99"}, format="json").json()

    assert nuevos["access"] and nuevos["refresh"]
    assert APIClient().post("/api/v1/auth/refresh/", {"refresh": otra["refresh"]}, format="json").status_code == 401
    assert _login(password="OtraClave99").status_code == 200
    assert "Tu contraseña cambió" in correos[-1]["subject"]


def test_ver_y_cerrar_sesiones():
    vieja = _login().json()
    actual = _login().json()
    api = _con_token(actual["access"])

    sesiones = api.get("/api/v1/auth/me/sesiones/", HTTP_X_REFRESH_TOKEN=actual["refresh"]).json()
    assert len([s for s in sesiones if s["actual"]]) == 1
    assert len(sesiones) >= 2

    assert api.post("/api/v1/auth/me/sesiones/cerrar-otras/", {"refresh": actual["refresh"]}, format="json").json()["cerradas"] >= 1
    assert APIClient().post("/api/v1/auth/refresh/", {"refresh": vieja["refresh"]}, format="json").status_code == 401
    assert APIClient().post("/api/v1/auth/refresh/", {"refresh": actual["refresh"]}, format="json").status_code == 200


def test_eliminar_la_cuenta_la_anonimiza_y_respeta_lo_pagado(stripe):
    pagada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(habitacion_publicada()), format="json").json()
    _webhook("checkout.session.completed", _session_id(pagada["id"]))
    pendiente = cliente().post(
        "/api/v1/me/reservas/",
        {"producto_id": tour_publicado().id, "fecha_inicio": (timezone.localdate() + timedelta(days=3)).isoformat(), "cantidad": 1},
        format="json",
    ).json()
    turista_id = User.objects.get(email=TURISTA).id
    api = _con_token(_login().json()["access"])

    assert api.post("/api/v1/auth/me/eliminar/", {"password": "mal"}, format="json").status_code == 400
    assert api.post("/api/v1/auth/me/eliminar/", {"password": PASSWORD}, format="json").status_code == 204

    cuenta = User.objects.get(id=turista_id)
    assert cuenta.email.startswith("eliminado-")
    assert cuenta.status == "INACTIVO"
    assert _login().status_code == 401
    assert Booking.objects.get(id=pagada["id"]).status == "CONFIRMADA"
    assert Booking.objects.get(id=pendiente["id"]).status == "CANCELADA"


def test_el_personal_no_se_da_de_baja_desde_aqui():
    api = _con_token(_login("jefeadmin@hotelcortez.com.bo").json()["access"])
    assert api.post("/api/v1/auth/me/eliminar/", {"password": PASSWORD}, format="json").status_code == 400


def test_no_mas_de_tres_reservas_esperando_pago(stripe):
    for dias in (3, 4, 5):
        pedido = {"producto_id": tour_publicado().id, "fecha_inicio": (timezone.localdate() + timedelta(days=dias)).isoformat(), "cantidad": 1}
        assert cliente().post("/api/v1/me/reservas/", pedido, format="json").status_code == 201
    cuarta = {"producto_id": tour_publicado().id, "fecha_inicio": (timezone.localdate() + timedelta(days=6)).isoformat(), "cantidad": 1}
    respuesta = cliente().post("/api/v1/me/reservas/", cuarta, format="json")
    assert respuesta.status_code == 400
    assert "esperando pago" in respuesta.json()["error"]["message"]
