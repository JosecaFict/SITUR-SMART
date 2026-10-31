"""Salidas horarias con el esquema PostgreSQL real y el pago simulado."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Lock

import pytest
from django.db import connections
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings import events, receipt
from apps.bookings.models import Booking
from apps.catalog.departures import day_bounds
from apps.catalog.models import Availability
from apps.payments.models import Payment
from apps.rbac.models import UserRole

from .datos import (
    OTRO_TURISTA,
    TURISTA,
    _hoy,
    _session_id,
    _webhook,
    cliente,
    tour_publicado,
)

pytestmark = pytest.mark.django_db


def _owner(tenant_id):
    user = UserRole.objects.filter(tenant_id=tenant_id, role__code="TENANT_ADMIN").select_related("user").first().user
    api = APIClient()
    api.force_authenticate(user)
    api.credentials(HTTP_X_TENANT_ID=str(tenant_id))
    return api


def _day(offset=5):
    return (_hoy() + timedelta(days=offset)).isoformat()


def _url(tour):
    return f"/api/v1/productos/{tour.id}/salidas/"


def _public_url(tour):
    return f"/api/v1/marketplace/productos/{tour.id}/salidas/"


def _create(tour, *, day=None, capacity=2, start="09:00", end="12:00"):
    return _owner(tour.tenant_id).post(_url(tour), {
        "fecha": day or _day(), "hora_inicio": start, "hora_fin": end, "cupo_total": capacity,
    }, format="json")


def test_permisos_tenant_y_consulta_publica(stripe):
    tour = tour_publicado()
    day = _day()
    assert APIClient().post(_url(tour), {}, format="json").status_code == 401
    valid = {"fecha": day, "hora_inicio": "09:00", "hora_fin": "12:00", "cupo_total": 2}
    assert cliente().post(_url(tour), valid, format="json", HTTP_X_TENANT_ID=str(tour.tenant_id)).status_code == 403
    assert cliente().get(_url(tour)).status_code == 400
    assert _owner(tour.tenant_id).get(_url(tour)).status_code == 200
    assert _owner(tour.tenant_id).post(_url(tour), {}, format="json").status_code == 400
    guide = UserRole.objects.filter(tenant_id=tour.tenant_id, role__code="GUIA").select_related("user").first()
    guide_api = APIClient()
    guide_api.force_authenticate(guide.user)
    guide_api.credentials(HTTP_X_TENANT_ID=str(tour.tenant_id))
    assert guide_api.get(_url(tour)).status_code == 200
    assert guide_api.post(_url(tour), valid, format="json").status_code == 403
    other = UserRole.objects.filter(role__code="TENANT_ADMIN").exclude(tenant_id=tour.tenant_id).first()
    assert _owner(other.tenant_id).get(_url(tour)).status_code == 404
    assert _owner(other.tenant_id).post(_url(tour), valid, format="json").status_code == 404
    created = _create(tour)
    assert created.status_code == 201, created.json()
    assert created.json()["inicio"].endswith("-04:00")
    public = APIClient().get(_public_url(tour), {"fecha": day})
    assert public.status_code == 200
    assert public.json()[0]["cupos_restantes"] == 2
    assert public.json()[0]["id"] == created.json()["id"]


def test_fechas_cupos_horarios_y_cierre(stripe):
    tour = tour_publicado()
    assert _create(tour, day="2000-01-01").status_code == 400
    assert _create(tour, capacity=tour.max_capacity + 1).status_code == 400
    assert _create(tour, start="12:00", end="09:00").status_code == 400
    created = _create(tour)
    assert created.status_code == 201, created.json()
    slot_id = created.json()["id"]
    assert _create(tour, start="11:00", end="13:00").status_code == 400
    assert _create(tour, start="13:00", end="15:00").status_code == 201
    detail = f"{_url(tour)}{slot_id}/"
    updated = _owner(tour.tenant_id).patch(detail, {"cupo_total": 1}, format="json")
    assert updated.status_code == 200, updated.json()
    assert updated.json()["cupo_total"] == 1
    assert _owner(tour.tenant_id).post(f"{detail}cerrar/").status_code == 200
    assert APIClient().get(_public_url(tour), {"fecha": _day()}).json()[0]["id"] != slot_id
    pedido = {"producto_id": tour.id, "fecha_inicio": _day(), "cantidad": 1, "salida_id": slot_id}
    assert cliente().post("/api/v1/me/reservas/cotizacion/", pedido, format="json").status_code == 400


def test_reserva_exacta_cupo_particular_y_contrato_solo_fecha(stripe):
    tour = tour_publicado()
    first = _create(tour, capacity=1).json()["id"]
    second = _create(tour, capacity=2, start="14:00", end="17:00").json()["id"]
    pedido = {"producto_id": tour.id, "fecha_inicio": _day(), "cantidad": 1, "salida_id": first}
    assert cliente().post("/api/v1/me/reservas/cotizacion/", {
        **pedido, "fecha_inicio": _day(6),
    }, format="json").status_code == 400
    quote = cliente().post("/api/v1/me/reservas/cotizacion/", pedido, format="json").json()
    assert quote["salida_id"] == first
    assert quote["inicio"] and quote["fin"]
    created = cliente().post("/api/v1/me/reservas/", pedido, format="json")
    assert created.status_code == 201, created.json()
    assert created.json()["salida"]["id"] == first
    assert Booking.objects.get(id=created.json()["id"]).details.first().slot_id == first
    assert Availability.objects.get(id=first).total_capacity == 1
    assert cliente(OTRO_TURISTA).post("/api/v1/me/reservas/", pedido, format="json").status_code == 409
    legacy_request = {"producto_id": tour.id, "fecha_inicio": _day(), "cantidad": 1}
    fallback = cliente(OTRO_TURISTA).post("/api/v1/me/reservas/", legacy_request, format="json")
    assert fallback.status_code == 201, fallback.json()
    assert fallback.json()["salida"]["id"] == second
    assert Availability.objects.get(id=second).total_capacity == 2
    assert APIClient().get(_public_url(tour), {"fecha": _day()}).json()[0]["cupos_restantes"] == 1
    assert _owner(tour.tenant_id).patch(f"{_url(tour)}{second}/", {"cupo_total": 0}, format="json").status_code == 400
    assert _owner(tour.tenant_id).patch(f"{_url(tour)}{second}/", {"hora_inicio": "15:00"}, format="json").status_code == 400


def test_reserva_diaria_historica_no_se_convierte_ni_se_sobrevende(stripe):
    tour = tour_publicado()
    day = _day(7)
    pedido = {"producto_id": tour.id, "fecha_inicio": day, "cantidad": 1}
    old = cliente().post("/api/v1/me/reservas/", pedido, format="json")
    assert old.status_code == 201, old.json()
    old_slot = Booking.objects.get(id=old.json()["id"]).details.first().slot
    assert timezone.localtime(old_slot.start).hour == 0
    denied = _create(tour, day=day)
    assert denied.status_code == 400
    assert Booking.objects.get(id=old.json()["id"]).details.first().slot_id == old_slot.id
    assert cliente().post(f"/api/v1/me/reservas/{old.json()['id']}/cancelar/").status_code == 200
    assert _create(tour, day=day).status_code == 400
    # El contrato por fecha conserva el cupo diario y el historial original.
    quote = cliente(OTRO_TURISTA).post("/api/v1/me/reservas/cotizacion/", pedido, format="json").json()
    assert quote["salida_id"] is None
    assert quote["disponible"] is True


def test_cupo_diario_sin_historial_puede_convertirse_a_salida_de_medianoche(stripe):
    tour = tour_publicado()
    start, end = day_bounds(_hoy() + timedelta(days=8))
    daily = Availability.objects.create(
        product=tour, tenant_id=tour.tenant_id, start=start, end=end,
        total_capacity=tour.max_capacity,
    )
    result = _create(tour, day=_day(8), start="00:00", end="02:00", capacity=1)
    assert result.status_code == 201, result.json()
    assert result.json()["id"] == daily.id
    assert Availability.objects.get(id=daily.id).total_capacity == 1


def test_stripe_y_cancelacion_existente_con_salida(stripe):
    tour = tour_publicado()
    slot_id = _create(tour, capacity=1).json()["id"]
    pedido = {"producto_id": tour.id, "fecha_inicio": _day(), "cantidad": 1, "salida_id": slot_id}
    first = cliente().post("/api/v1/me/reservas/", pedido, format="json").json()
    assert cliente().post(f"/api/v1/me/reservas/{first['id']}/cancelar/").status_code == 200
    assert APIClient().get(_public_url(tour), {"fecha": _day()}).json()[0]["cupos_restantes"] == 1
    second = cliente().post("/api/v1/me/reservas/", pedido, format="json").json()
    assert _webhook("checkout.session.completed", _session_id(second["id"])).status_code == 200
    assert cliente().get(f"/api/v1/me/reservas/{second['id']}/").json()["estado"] == "CONFIRMADA"
    paid = Booking.objects.get(id=second["id"])
    assert "09:00 a 12:00" in events._summary(paid)["when"]
    assert receipt.build_receipt_pdf(paid).startswith(b"%PDF")
    assert cliente().post(f"/api/v1/me/reservas/{second['id']}/cancelar/").status_code == 400
    assert APIClient().get(_public_url(tour), {"fecha": _day()}).json() == []


@pytest.mark.django_db(transaction=True)
def test_dos_reservas_simultaneas_no_exceden_el_cupo(stripe, monkeypatch):
    tour = tour_publicado()
    slot_id = _create(tour, capacity=1).json()["id"]
    gate = Barrier(2)
    stripe_lock = Lock()
    original_checkout = stripe.create_checkout_session

    def safe_checkout(**kwargs):
        with stripe_lock:
            return original_checkout(**kwargs)

    monkeypatch.setattr("apps.payments.gateway.create_checkout_session", safe_checkout)

    def reserve(email):
        connections.close_all()
        api = cliente(email)
        gate.wait(timeout=10)
        response = api.post("/api/v1/me/reservas/", {
            "producto_id": tour.id, "fecha_inicio": _day(), "cantidad": 1, "salida_id": slot_id,
        }, format="json")
        connections.close_all()
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, (TURISTA, OTRO_TURISTA)))
    assert sorted(outcomes) == [201, 409]
    assert sum(Payment.objects.filter(booking__details__slot_id=slot_id).values_list("amount", flat=True)) == tour.base_price
