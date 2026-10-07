"""La empresa ve sus reservas, valida la llegada y reporta clientes (PostgreSQL real)."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.bookings import company
from apps.bookings.models import Booking, CustomerReport
from apps.rbac.models import UserRole

from .datos import (
    TURISTA,
    _pedido_habitacion,
    _session_id,
    _webhook,
    cliente,
    habitacion_publicada,
)

pytestmark = pytest.mark.django_db(transaction=False)

URL = "/api/v1/empresa/reservas/"
SUPERADMIN = "superadmin@situr.com.bo"


@pytest.fixture
def correos(monkeypatch):
    enviados = []
    monkeypatch.setattr(company, "send_email", lambda **kwargs: enviados.append(kwargs) or True)
    return enviados


def _dueno(tenant_id: int) -> APIClient:
    owner = UserRole.objects.filter(tenant_id=tenant_id, role__code="TENANT_ADMIN").select_related("user").first().user
    api = APIClient()
    api.force_authenticate(owner)
    api.credentials(HTTP_X_TENANT_ID=str(tenant_id))
    return api


def _otra_empresa(tenant_id: int) -> APIClient:
    other = UserRole.objects.filter(role__code="TENANT_ADMIN").exclude(tenant_id=tenant_id).first()
    return _dueno(other.tenant_id)


def _reservar(*, pagar=True, dias=10):
    room = habitacion_publicada()
    creada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(room, dias=dias), format="json").json()
    if pagar:
        _webhook("checkout.session.completed", _session_id(creada["id"]))
    return creada, room.tenant_id


def test_la_empresa_ve_sus_reservas_con_el_contacto_del_cliente(stripe):
    creada, tenant_id = _reservar()

    data = _dueno(tenant_id).get(URL).json()
    [fila] = [row for row in data["results"] if row["id"] == creada["id"]]
    assert fila["cliente"]["email"] == TURISTA
    assert fila["estado"] == "CONFIRMADA"
    assert fila["comprobante_url"]
    assert data["resumen"]["proximas"] >= 1
    assert data["resumen"]["ingresos_mes"][0]["total"]

    buscada = _dueno(tenant_id).get(URL, {"buscar": creada["codigo"]}).json()
    assert [row["id"] for row in buscada["results"]] == [creada["id"]]


def test_otra_empresa_y_el_turista_no_la_ven(stripe):
    creada, tenant_id = _reservar()
    otra = _otra_empresa(tenant_id)

    assert creada["id"] not in [row["id"] for row in otra.get(URL).json()["results"]]
    assert otra.get(f"{URL}{creada['id']}/").status_code == 404
    assert otra.post(f"{URL}validar/", {"codigo": creada["codigo"]}, format="json").status_code == 404
    turista = cliente()
    turista.credentials(HTTP_X_TENANT_ID=str(tenant_id))
    assert turista.get(URL).status_code == 403


def test_validar_por_codigo_o_por_qr_y_marcar_la_llegada_una_vez(stripe):
    creada, tenant_id = _reservar(dias=0)
    api = _dueno(tenant_id)

    por_codigo = api.post(f"{URL}validar/", {"codigo": creada["codigo"].lower()}, format="json").json()
    assert por_codigo["puede_marcar_llegada"] is True
    assert por_codigo["reserva"]["cliente"]["email"] == TURISTA

    qr = cliente().get(f"/api/v1/me/reservas/{creada['id']}/").json()["qr"]
    por_qr = api.post(f"{URL}validar/", {"codigo": qr}, format="json").json()
    assert por_qr["reserva"]["id"] == creada["id"]

    llegada = api.post(f"{URL}{creada['id']}/llegada/").json()
    assert llegada["llegada"]["por"]
    assert Booking.objects.get(id=creada["id"]).checked_in_at is not None

    segunda = api.post(f"{URL}{creada['id']}/llegada/")
    assert segunda.status_code == 400
    assert "Ya se marcó la llegada" in segunda.json()["error"]["message"]
    assert api.post(f"{URL}validar/", {"codigo": creada["codigo"]}, format="json").json()["puede_marcar_llegada"] is False


def test_una_reserva_sin_pagar_no_se_valida(stripe):
    creada, tenant_id = _reservar(pagar=False)
    api = _dueno(tenant_id)

    resultado = api.post(f"{URL}validar/", {"codigo": creada["codigo"]}, format="json").json()
    assert resultado["puede_marcar_llegada"] is False
    assert "no está pagada" in resultado["motivo"]
    assert api.post(f"{URL}{creada['id']}/llegada/").status_code == 400


def test_una_reserva_futura_se_puede_validar_pero_avisa_la_fecha(stripe):
    creada, tenant_id = _reservar(dias=5)
    resultado = _dueno(tenant_id).post(f"{URL}validar/", {"codigo": creada["codigo"]}, format="json").json()
    dia = (timezone.localdate() + timedelta(days=5)).strftime("%d/%m/%Y")
    assert resultado["puede_marcar_llegada"] is True
    assert dia in resultado["motivo"]


def test_reportar_un_cliente_avisa_al_superadmin_sin_bloquearlo(stripe, correos):
    creada, tenant_id = _reservar()
    respuesta = _dueno(tenant_id).post(
        f"{URL}{creada['id']}/reportar/", {"motivo": "No se presentó y dejó una reseña falsa"}, format="json"
    )

    assert respuesta.status_code == 201
    turista = User.objects.get(email=TURISTA)
    assert turista.status == "ACTIVO"
    assert CustomerReport.objects.filter(customer=turista, tenant_id=tenant_id).exists()
    assert correos and correos[0]["to_email"] == SUPERADMIN

    ficha = cliente(SUPERADMIN).get(f"/api/v1/admin/clientes/{turista.id}/").json()
    assert ficha["reportes"][0]["reserva"] == creada["codigo"]
    assert "reseña falsa" in ficha["reportes"][0]["motivo"]
    assert _dueno(tenant_id).post(f"{URL}{creada['id']}/reportar/", {"motivo": "x"}, format="json").status_code == 400
