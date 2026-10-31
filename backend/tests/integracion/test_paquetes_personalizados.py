"""CU39: paquetes privados que cotizan sin reservar ni abrir pagos."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.catalog.departures import day_bounds
from apps.catalog.models import Availability, TourismProduct
from apps.custom_packages.models import CustomPackage
from apps.payments.models import Payment

from .datos import (
    OTRO_TURISTA,
    cliente,
    habitacion_publicada,
    hotel_publicado,
    tour_publicado,
)

pytestmark = pytest.mark.django_db
BASE = "/api/v1/me/paquetes/"


def _day(offset=10):
    return timezone.localdate() + timedelta(days=offset)


def _create(api, *, people=2):
    day = _day()
    return api.post(BASE, {"nombre": "Ruta por Bolivia", "fecha_inicio": day.isoformat(),
                           "fecha_fin": (day + timedelta(days=2)).isoformat(), "personas": people}, format="json")


def _tour_slot(tour, day, *, capacity=5, closed=False):
    start, _ = day_bounds(day)
    return Availability.objects.create(product=tour, tenant=tour.tenant,
        start=start + timedelta(hours=9), end=start + timedelta(hours=12),
        total_capacity=capacity, closed=closed)


def test_crear_agregar_varios_quitar_guardar_y_consultar_sin_reserva():
    api = cliente()
    tour = tour_publicado()
    room = habitacion_publicada()
    day = _day()
    slot = _tour_slot(tour, day)
    before = (Booking.objects.count(), Payment.objects.count())
    created = _create(api)
    assert created.status_code == 201
    package_id = created.json()["id"]
    tour_config = {"producto_id": tour.id, "fecha_inicio": day.isoformat(),
                   "cantidad": 2, "salida_id": slot.id}
    quote = api.post(f"{BASE}{package_id}/cotizar/", tour_config, format="json")
    assert quote.status_code == 200
    assert quote.json()["total"] == str(tour.base_price * 2)
    first = api.post(f"{BASE}{package_id}/componentes/", tour_config, format="json")
    assert first.status_code == 201
    current_id = first.json()["componentes"][0]["id"]
    checked_edit = api.post(f"{BASE}{package_id}/cotizar/", tour_config | {"componente_id": current_id}, format="json")
    assert checked_edit.status_code == 200
    assert api.post(f"{BASE}{package_id}/componentes/", tour_config, format="json").status_code == 400
    room_config = {"producto_id": room.product_id, "fecha_inicio": day.isoformat(),
                   "fecha_fin": (day + timedelta(days=2)).isoformat(), "cantidad": 1, "huespedes": 1}
    second = api.post(f"{BASE}{package_id}/componentes/", room_config, format="json")
    assert second.status_code == 201, second.json()
    assert second.json()["cantidad_servicios"] == 2
    expected = tour.base_price * 2 + room.product.base_price * 2
    assert second.json()["total"] == str(expected)
    room_component = next(item for item in second.json()["componentes"] if item["producto_id"] == room.product_id)
    changed = api.patch(f"{BASE}{package_id}/componentes/{room_component['id']}/",
                        {"fecha_fin": (day + timedelta(days=1)).isoformat()}, format="json")
    assert changed.status_code == 200
    assert changed.json()["total"] == str(tour.base_price * 2 + room.product.base_price)
    saved = api.post(f"{BASE}{package_id}/validar/", {"guardar": True}, format="json")
    assert saved.status_code == 200
    assert saved.json()["estado"] == "GUARDADO"
    assert api.get(BASE).json()[0]["id"] == package_id
    assert api.get(f"{BASE}{package_id}/").json()["cantidad_servicios"] == 2
    removed = api.delete(f"{BASE}{package_id}/componentes/{room_component['id']}/")
    assert removed.status_code == 200
    assert removed.json()["estado"] == "BORRADOR"
    assert removed.json()["cantidad_servicios"] == 1
    assert (Booking.objects.count(), Payment.objects.count()) == before


def test_no_adivina_salidas_y_revalida_cupos_al_guardar():
    api = cliente()
    tour = tour_publicado()
    day = _day()
    slot = _tour_slot(tour, day, capacity=2)
    package_id = _create(api).json()["id"]
    config = {"producto_id": tour.id, "fecha_inicio": day.isoformat(), "cantidad": 2}
    assert api.post(f"{BASE}{package_id}/componentes/", config, format="json").status_code == 400
    config["salida_id"] = slot.id
    assert api.post(f"{BASE}{package_id}/componentes/", config, format="json").status_code == 201
    slot.closed = True
    slot.save(update_fields=["closed"])
    result = api.post(f"{BASE}{package_id}/validar/", {"guardar": True}, format="json")
    assert result.status_code == 400
    assert CustomPackage.objects.get(id=package_id).status == "BORRADOR"
    detail = api.get(f"{BASE}{package_id}/").json()
    assert detail["requiere_revalidacion"] is True
    assert detail["componentes"][0]["disponible"] is False


def test_sin_salidas_ni_disponibilidad_diaria_no_es_disponible():
    api = cliente()
    tour = tour_publicado()
    day = _day()
    package_id = _create(api).json()["id"]
    result = api.post(f"{BASE}{package_id}/cotizar/",
                      {"producto_id": tour.id, "fecha_inicio": day.isoformat(), "cantidad": 1}, format="json")
    assert result.status_code == 400
    assert "disponibilidad" in str(result.json()).lower()


def test_salidas_superpuestas_no_se_combinan():
    api = cliente()
    tour = tour_publicado()
    other = TourismProduct.objects.filter(status="PUBLICADO", tenant__status="ACTIVO",
        product_type__code="TOUR").exclude(id=tour.id).order_by("id").first()
    day = _day()
    first = _tour_slot(tour, day)
    second = _tour_slot(other, day)
    package_id = _create(api).json()["id"]
    config = {"fecha_inicio": day.isoformat(), "cantidad": 1}
    assert api.post(f"{BASE}{package_id}/componentes/",
        config | {"producto_id": tour.id, "salida_id": first.id}, format="json").status_code == 201
    conflict = api.post(f"{BASE}{package_id}/componentes/",
        config | {"producto_id": other.id, "salida_id": second.id}, format="json")
    assert conflict.status_code == 400
    assert "superpone" in str(conflict.json())


def test_cambio_de_precio_requiere_revalidacion_y_recalcula():
    api = cliente()
    tour = tour_publicado()
    day = _day()
    slot = _tour_slot(tour, day)
    package_id = _create(api).json()["id"]
    config = {"producto_id": tour.id, "fecha_inicio": day.isoformat(), "cantidad": 2, "salida_id": slot.id}
    assert api.post(f"{BASE}{package_id}/componentes/", config, format="json").status_code == 201
    assert api.post(f"{BASE}{package_id}/validar/", {"guardar": True}, format="json").status_code == 200
    tour.base_price += 10
    tour.save(update_fields=["base_price"])
    detail = api.get(f"{BASE}{package_id}/").json()
    assert detail["requiere_revalidacion"] is True
    assert detail["componentes"][0]["total_actual"] == str(tour.base_price * 2)
    refreshed = api.post(f"{BASE}{package_id}/validar/", {"guardar": False}, format="json")
    assert refreshed.status_code == 200
    assert refreshed.json()["total"] == str(tour.base_price * 2)
    assert refreshed.json()["estado"] == "BORRADOR"


def test_disponibilidad_diaria_heredada_y_fechas_invalidas():
    api = cliente()
    tour = tour_publicado()
    day = _day()
    start, end = day_bounds(day)
    Availability.objects.create(product=tour, tenant=tour.tenant, start=start, end=end,
                                total_capacity=4, closed=False)
    package_id = _create(api).json()["id"]
    daily = {"producto_id": tour.id, "fecha_inicio": day.isoformat(), "cantidad": 2}
    assert api.post(f"{BASE}{package_id}/componentes/", daily, format="json").status_code == 201
    assert api.post(f"{BASE}{package_id}/validar/", {"guardar": True}, format="json").status_code == 200
    past = api.patch(f"{BASE}{package_id}/", {"fecha_inicio": (day - timedelta(days=20)).isoformat()}, format="json")
    assert past.status_code == 400


def test_privacidad_y_catalogo_sin_hotel_como_componente():
    owner = cliente()
    other = cliente(OTRO_TURISTA)
    package_id = _create(owner).json()["id"]
    assert APIClient().get(BASE).status_code == 401
    assert other.get(f"{BASE}{package_id}/").status_code == 404
    assert other.patch(f"{BASE}{package_id}/", {"nombre": "Ajeno"}, format="json").status_code == 404
    assert other.post(f"{BASE}{package_id}/cotizar/", {"producto_id": tour_publicado().id,
        "fecha_inicio": _day().isoformat(), "cantidad": 1}, format="json").status_code == 404
    assert other.post(f"{BASE}{package_id}/validar/", {"guardar": True}, format="json").status_code == 404
    hotel = hotel_publicado()
    company_package = TourismProduct.objects.filter(product_type__code="PAQUETE", status="PUBLICADO").first()
    catalog = owner.get(f"{BASE}catalogo/", {"page_size": 50})
    assert catalog.status_code == 200
    assert hotel.product_id not in [item["id"] for item in catalog.json()["results"]]
    if company_package:
        assert company_package.id not in [item["id"] for item in catalog.json()["results"]]
        assert owner.post(f"{BASE}{package_id}/componentes/", {"producto_id": company_package.id,
            "fecha_inicio": _day().isoformat(), "cantidad": 1}, format="json").status_code == 400
