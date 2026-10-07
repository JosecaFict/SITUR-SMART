"""Publicacion y retiro programados de productos y hospedajes (PostgreSQL real)."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog import scheduling
from apps.catalog.models import LodgingEstablishment, Room, TourismProduct
from apps.rbac.models import UserRole

from .datos import cliente, hotel_publicado, tour_publicado

pytestmark = pytest.mark.django_db(transaction=False)


@pytest.fixture
def correos(monkeypatch):
    enviados = []
    monkeypatch.setattr(scheduling, "send_email", lambda **kwargs: enviados.append(kwargs) or True)
    return enviados


def _dueno(tenant_id: int) -> APIClient:
    owner = UserRole.objects.filter(tenant_id=tenant_id, role__code="TENANT_ADMIN").select_related("user").first().user
    api = APIClient()
    api.force_authenticate(owner)
    api.credentials(HTTP_X_TENANT_ID=str(tenant_id))
    return api


def _en(horas: float) -> str:
    return (timezone.now() + timedelta(hours=horas)).isoformat()


def _borrador() -> TourismProduct:
    tour = tour_publicado()
    TourismProduct.objects.filter(id=tour.id).update(status="BORRADOR")
    tour.refresh_from_db()
    return tour


def _programar(product, **fechas):
    return _dueno(product.tenant_id).put(f"/api/v1/productos/{product.id}/programacion/", fechas, format="json")


def test_un_tour_programado_se_publica_solo_a_su_hora(correos):
    tour = _borrador()
    respuesta = _programar(tour, publicar_en=_en(1))
    assert respuesta.status_code == 200
    assert respuesta.json()["publicar_en"]
    assert cliente().get(f"/api/v1/marketplace/productos/{tour.id}/").status_code == 404

    assert scheduling.process_due(now=timezone.now() + timedelta(minutes=30))["publicados"] == 0
    resultado = scheduling.process_due(now=timezone.now() + timedelta(hours=2))

    assert resultado["publicados"] == 1
    tour.refresh_from_db()
    assert tour.status == "PUBLICADO"
    assert tour.publish_at is None
    assert tour.auto_published_at is not None
    assert cliente().get(f"/api/v1/marketplace/productos/{tour.id}/").status_code == 200
    assert "ya está publicado" in correos[0]["subject"]


def test_el_retiro_programado_lo_saca_del_marketplace(correos):
    tour = tour_publicado()
    assert _programar(tour, retirar_en=_en(3)).status_code == 200

    assert scheduling.process_due(now=timezone.now() + timedelta(hours=4))["retirados"] == 1
    tour.refresh_from_db()
    assert tour.status == "INACTIVO"
    assert cliente().get(f"/api/v1/marketplace/productos/{tour.id}/").status_code == 404
    assert "se retiró" in correos[0]["subject"]


def test_un_hotel_se_programa_por_su_producto_y_revisa_sus_habitaciones(correos):
    hotel = hotel_publicado()
    product = hotel.product
    TourismProduct.objects.filter(id=product.id).update(status="BORRADOR")
    assert _programar(product, publicar_en=_en(1)).status_code == 200
    scheduling.process_due(now=timezone.now() + timedelta(hours=2))
    product.refresh_from_db()
    assert product.status == "PUBLICADO"


def test_un_hotel_sin_habitacion_con_precio_no_se_publica_y_se_avisa(correos):
    hotel = hotel_publicado()
    TourismProduct.objects.filter(id=hotel.product_id).update(status="BORRADOR")
    TourismProduct.objects.filter(room__establishment=hotel).update(status="BORRADOR")
    _programar(hotel.product, publicar_en=_en(1))

    resultado = scheduling.process_due(now=timezone.now() + timedelta(hours=2))

    assert resultado["fallidos"] == 1
    product = TourismProduct.objects.get(id=hotel.product_id)
    assert product.status == "BORRADOR"
    assert product.publish_at is None
    assert "No se pudo publicar" in correos[0]["subject"]
    assert "habitación" in correos[0]["html"]


@pytest.mark.parametrize(
    ("fechas", "campo"),
    [
        ({"publicar_en": "2000-01-01T10:00:00Z"}, "publicar_en"),
        ({"publicar_en": "+5", "retirar_en": "+2"}, "retirar_en"),
    ],
)
def test_validaciones_de_fechas(fechas, campo):
    tour = _borrador()
    datos = {key: (_en(int(value[1:])) if value.startswith("+") else value) for key, value in fechas.items()}
    respuesta = _programar(tour, **datos)
    assert respuesta.status_code == 400
    assert campo in respuesta.json()["error"]["details"]


def test_reglas_de_que_se_puede_programar():
    publicado = tour_publicado()
    assert _programar(publicado, publicar_en=_en(1)).status_code == 400

    habitacion = Room.objects.select_related("product").first().product
    assert _programar(habitacion, publicar_en=_en(1)).status_code == 400

    otra = UserRole.objects.filter(role__code="TENANT_ADMIN").exclude(tenant_id=publicado.tenant_id).first().tenant_id
    assert _dueno(otra).put(f"/api/v1/productos/{publicado.id}/programacion/", {"retirar_en": _en(2)}, format="json").status_code == 404


def test_quitar_la_programacion():
    tour = _borrador()
    _programar(tour, publicar_en=_en(1))
    respuesta = _dueno(tour.tenant_id).delete(f"/api/v1/productos/{tour.id}/programacion/")
    assert respuesta.json()["publicar_en"] is None


def test_el_cron_incluye_las_publicaciones(correos, monkeypatch):
    monkeypatch.setattr("apps.backups.management.commands.tareas_programadas.run_if_due", lambda: None)
    tour = _borrador()
    _programar(tour, publicar_en=_en(1))
    TourismProduct.objects.filter(id=tour.id).update(publish_at=timezone.now() - timedelta(minutes=1))

    salida = StringIO()
    call_command("tareas_programadas", stdout=salida)
    assert "1 publicadas" in salida.getvalue()


def test_el_hospedaje_muestra_su_programacion():
    hotel = hotel_publicado()
    _programar(hotel.product, retirar_en=_en(5))
    lodging = LodgingEstablishment.objects.get(id=hotel.id)
    data = _dueno(hotel.tenant_id).get(f"/api/v1/hospedajes/{lodging.id}/").json()
    assert data["retirar_en"]
