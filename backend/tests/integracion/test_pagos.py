import pytest
from rest_framework.test import APIClient

from apps.rbac.models import UserRole

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


def _paid_booking():
    room = habitacion_publicada()
    booking = cliente().post(
        "/api/v1/me/reservas/", _pedido_habitacion(room), format="json"
    ).json()
    _webhook("checkout.session.completed", _session_id(booking["id"]))
    return booking, room.tenant_id


def _owner(tenant_id: int) -> APIClient:
    user = UserRole.objects.filter(
        tenant_id=tenant_id, role__code="TENANT_ADMIN"
    ).select_related("user").first().user
    api = APIClient()
    api.force_authenticate(user)
    api.credentials(HTTP_X_TENANT_ID=str(tenant_id))
    return api


def test_tourist_only_sees_own_payments(stripe):
    booking, _ = _paid_booking()

    data = cliente().get("/api/v1/me/pagos/").json()
    payment = next(row for row in data["results"] if row["reserva_id"] == booking["id"])
    assert payment["status"] == "APROBADO"
    assert payment["cliente"]["email"] == TURISTA
    assert cliente().get(f"/api/v1/me/pagos/{payment['id']}/").status_code == 200
    assert cliente(OTRO_TURISTA).get(f"/api/v1/me/pagos/{payment['id']}/").status_code == 404


def test_company_sees_totals_and_not_other_tenants(stripe):
    booking, tenant_id = _paid_booking()
    data = _owner(tenant_id).get("/api/v1/empresa/pagos/").json()

    assert booking["id"] in [row["reserva_id"] for row in data["results"]]
    assert data["resumen"][0]["cobrado"] != "0.00"
    assert data["resumen"][0]["neto"] == data["resumen"][0]["cobrado"]

    other = UserRole.objects.filter(role__code="TENANT_ADMIN").exclude(tenant_id=tenant_id).first()
    assert booking["id"] not in [
        row["reserva_id"] for row in _owner(other.tenant_id).get("/api/v1/empresa/pagos/").json()["results"]
    ]


def test_tourist_cannot_read_company_payments(stripe):
    _, tenant_id = _paid_booking()
    api = cliente()
    api.credentials(HTTP_X_TENANT_ID=str(tenant_id))
    assert api.get("/api/v1/empresa/pagos/").status_code == 403
