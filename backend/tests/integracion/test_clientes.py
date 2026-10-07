"""Administracion de las cuentas de los turistas, contra PostgreSQL real."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import customers
from apps.accounts.models import PasswordResetToken, User
from apps.bookings.models import Booking
from apps.notifications.models import PushDevice

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

SUPERADMIN = "superadmin@situr.com.bo"
DUENO = "jefeadmin@hotelcortez.com.bo"
URL = "/api/v1/admin/clientes/"
PASSWORD = "Admin123*"


@pytest.fixture
def correos(monkeypatch):
    enviados = []
    monkeypatch.setattr(customers, "send_email", lambda **kwargs: enviados.append(kwargs) or True)
    return enviados


def _turista() -> User:
    return User.objects.get(email=TURISTA)


def _login(email=TURISTA):
    return APIClient().post("/api/v1/auth/login/", {"email": email, "password": PASSWORD}, format="json")


def _admin():
    return cliente(SUPERADMIN)


def test_el_superadmin_ve_solo_turistas_con_su_resumen():
    data = _admin().get(URL).json()
    correos_listados = {row["email"] for row in data["results"]}

    assert TURISTA in correos_listados
    assert DUENO not in correos_listados
    assert SUPERADMIN not in correos_listados
    assert data["resumen"]["total"] == data["count"]
    assert {"nuevos_mes", "con_reservas", "bloqueados"} <= data["resumen"].keys()

    buscado = _admin().get(URL, {"buscar": "turista1"}).json()
    assert [row["email"] for row in buscado["results"]] == [TURISTA]


def test_nadie_sin_el_permiso_administra_clientes():
    turista_id = _turista().id
    for email in (DUENO, TURISTA):
        api = cliente(email)
        assert api.get(URL).status_code == 403
        assert api.post(f"{URL}{turista_id}/bloquear/", {"motivo": "porque si"}, format="json").status_code == 403
    assert APIClient().get(URL).status_code == 401


def test_la_ficha_muestra_su_actividad(stripe):
    creada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(habitacion_publicada()), format="json").json()
    _webhook("checkout.session.completed", _session_id(creada["id"]))

    ficha = _admin().get(f"{URL}{_turista().id}/").json()
    assert ficha["email"] == TURISTA
    assert ficha["actividad"]["pagadas"] == 1
    assert ficha["actividad"]["total_pagado"][0]["total"] == creada["importe"]["total"]
    assert ficha["reservas"][0]["codigo"] == creada["codigo"]


def test_bloquear_corta_el_acceso_y_cancela_solo_lo_pendiente(stripe, correos):
    turista = _turista()
    pagada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(habitacion_publicada()), format="json").json()
    _webhook("checkout.session.completed", _session_id(pagada["id"]))
    pendiente = cliente().post(
        "/api/v1/me/reservas/",
        {"producto_id": tour_publicado().id, "fecha_inicio": (timezone.localdate() + timedelta(days=4)).isoformat(), "cantidad": 1},
        format="json",
    ).json()
    cliente().post("/api/v1/me/dispositivos/", {"token": "celular"}, format="json")
    sesion = _login().json()
    con_token = APIClient()
    con_token.credentials(HTTP_AUTHORIZATION=f"Bearer {sesion['access']}")
    assert con_token.get("/api/v1/me/reservas/").status_code == 200

    respuesta = _admin().post(f"{URL}{turista.id}/bloquear/", {"motivo": "Reservas falsas reiteradas"}, format="json")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "BLOQUEADO"
    # Al instante, en la web y en el movil: el token ya emitido deja de valer
    # y la sesion no se puede renovar.
    assert con_token.get("/api/v1/me/reservas/").status_code == 401
    assert APIClient().post("/api/v1/auth/refresh/", {"refresh": sesion["refresh"]}, format="json").status_code == 401
    assert not PushDevice.objects.filter(user=turista).exists()
    assert Booking.objects.get(id=pagada["id"]).status == "CONFIRMADA"
    assert Booking.objects.get(id=pendiente["id"]).status == "CANCELADA"
    # Al intentar entrar se le dice por que, solo si la contrasena es correcta.
    assert "suspendida" in _login().json()["error"]["message"]
    mal = APIClient().post("/api/v1/auth/login/", {"email": TURISTA, "password": "otra"}, format="json")
    assert "suspendida" not in mal.json()["error"]["message"]
    assert "Reservas falsas reiteradas" in correos[0]["html"]
    historial = respuesta.json()["historial"][0]
    assert historial["accion"] == "BLOQUEAR_CLIENTE"
    assert historial["motivo"] == "Reservas falsas reiteradas"


def test_desbloquear_devuelve_el_acceso(correos):
    turista = _turista()
    _admin().post(f"{URL}{turista.id}/bloquear/", {"motivo": "Revisión de pagos"}, format="json")
    assert _admin().post(f"{URL}{turista.id}/bloquear/", {"motivo": "Otra vez"}, format="json").status_code == 400

    respuesta = _admin().post(f"{URL}{turista.id}/desbloquear/", {"motivo": "Se aclaró el caso"}, format="json")
    assert respuesta.json()["estado"] == "ACTIVO"
    assert _login().status_code == 200
    assert "activa de nuevo" in correos[-1]["subject"]


def test_cerrar_sesiones_sin_bloquear():
    sesion = _login().json()
    respuesta = _admin().post(f"{URL}{_turista().id}/cerrar-sesiones/", {"motivo": "Le robaron el celular"}, format="json")

    assert respuesta.json()["estado"] == "ACTIVO"
    assert respuesta.json()["sesiones_abiertas"] == 0
    assert APIClient().post("/api/v1/auth/refresh/", {"refresh": sesion["refresh"]}, format="json").status_code == 401
    assert _login().status_code == 200


def test_el_motivo_es_obligatorio_y_el_personal_no_es_cliente():
    turista_id = _turista().id
    assert _admin().post(f"{URL}{turista_id}/bloquear/", {"motivo": "  "}, format="json").status_code == 400
    assert _admin().post(f"{URL}{turista_id}/bloquear/", {"motivo": "no"}, format="json").status_code == 400
    dueno_id = User.objects.get(email=DUENO).id
    assert _admin().post(f"{URL}{dueno_id}/bloquear/", {"motivo": "Prueba de alcance"}, format="json").status_code == 404


def test_enviar_codigo_de_recuperacion(monkeypatch):
    monkeypatch.setattr("apps.accounts.services.send_password_reset_otp_email", lambda **kwargs: True)
    assert _admin().post(f"{URL}{_turista().id}/recuperar-contrasena/").status_code == 204
    assert PasswordResetToken.objects.filter(user=_turista()).exists()
