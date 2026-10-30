import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.bookings.models import Booking, InventoryLock
from apps.payments.models import Payment, Refund
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
    stripe_session = _session_id(booking["id"])
    _webhook("checkout.session.completed", stripe_session)
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


def test_owner_registers_manual_payment_without_trusting_amount(stripe):
    room = habitacion_publicada()
    booking = cliente().post(
        "/api/v1/me/reservas/", _pedido_habitacion(room), format="json"
    ).json()
    stripe_session = _session_id(booking["id"])
    api = _owner(room.tenant_id)
    url = "/api/v1/empresa/pagos/manuales/"
    body = {"reserva_id": booking["id"], "metodo": "TRANSFERENCIA", "referencia": "TRX-900"}

    first = api.post(url, body, format="json", HTTP_IDEMPOTENCY_KEY="manual-900")
    repeated = api.post(url, body, format="json", HTTP_IDEMPOTENCY_KEY="manual-900")

    assert first.status_code == repeated.status_code == 201
    assert first.json()["id"] == repeated.json()["id"]
    assert first.json()["amount"] == booking["importe"]["total"]
    assert first.json()["provider"] == "MANUAL"
    assert Booking.objects.get(id=booking["id"]).status == "CONFIRMADA"
    assert InventoryLock.objects.get(booking_id=booking["id"]).status == "CONSUMIDO"
    assert Payment.objects.filter(booking_id=booking["id"], status="APROBADO").count() == 1

    # Si Stripe confirma tarde la sesión que quedó anulada, no crea un segundo
    # ingreso aprobado ni cambia el pago manual.
    _webhook("checkout.session.completed", stripe_session)
    assert Payment.objects.filter(booking_id=booking["id"], status="APROBADO").count() == 1


def test_manual_qr_requires_reference_and_tourist_is_forbidden(stripe):
    room = habitacion_publicada()
    booking = cliente().post(
        "/api/v1/me/reservas/", _pedido_habitacion(room), format="json"
    ).json()
    url = "/api/v1/empresa/pagos/manuales/"
    body = {"reserva_id": booking["id"], "metodo": "QR", "referencia": ""}
    assert _owner(room.tenant_id).post(
        url, body, format="json", HTTP_IDEMPOTENCY_KEY="sin-ref"
    ).status_code == 400
    api = cliente()
    api.credentials(HTTP_X_TENANT_ID=str(room.tenant_id))
    assert api.post(url, body, format="json", HTTP_IDEMPOTENCY_KEY="turista").status_code == 403


def test_company_cancels_with_full_stripe_refund(stripe):
    booking, tenant_id = _paid_booking()
    response = _owner(tenant_id).post(
        f"/api/v1/empresa/reservas/{booking['id']}/cancelacion/",
        {"motivo": "La empresa canceló la salida programada."}, format="json",
        HTTP_IDEMPOTENCY_KEY="empresa-cancela-1",
    )
    assert response.status_code == 200
    assert response.json()["estado"] == "COMPLETADO"
    assert response.json()["monto"] == booking["importe"]["total"]
    assert Booking.objects.get(id=booking["id"]).status == "CANCELADA"
    assert InventoryLock.objects.get(booking_id=booking["id"]).status == "LIBERADO"


def test_manual_refund_requires_external_confirmation(stripe):
    room = habitacion_publicada()
    booking = cliente().post(
        "/api/v1/me/reservas/", _pedido_habitacion(room), format="json"
    ).json()
    owner = _owner(room.tenant_id)
    owner.post(
        "/api/v1/empresa/pagos/manuales/",
        {"reserva_id": booking["id"], "metodo": "EFECTIVO", "referencia": "CAJA-10"},
        format="json", HTTP_IDEMPOTENCY_KEY="cash-10",
    )
    url = f"/api/v1/empresa/reservas/{booking['id']}/cancelacion/"
    assert owner.post(
        url, {"motivo": "La empresa no podrá prestar el servicio."}, format="json",
        HTTP_IDEMPOTENCY_KEY="manual-refund-10",
    ).status_code == 400
    result = owner.post(
        url, {
            "motivo": "La empresa no podrá prestar el servicio.",
            "reembolso_manual_confirmado": True,
            "referencia_reembolso": "DEV-CAJA-10",
        }, format="json", HTTP_IDEMPOTENCY_KEY="manual-refund-10",
    )
    assert result.status_code == 200
    assert Refund.objects.get(id=result.json()["reembolso_id"]).provider == "MANUAL"
    assert Booking.objects.get(id=booking["id"]).status == "CANCELADA"


def test_superadmin_has_consolidated_payments(stripe):
    booking, _ = _paid_booking()
    api = APIClient()
    api.force_authenticate(User.objects.get(email="superadmin@situr.com.bo"))
    response = api.get("/api/v1/admin/pagos/")
    assert response.status_code == 200
    assert booking["id"] in [row["reserva_id"] for row in response.json()["results"]]
