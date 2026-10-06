import pytest

from apps.catalog.models import TourismProduct

from .datos import (
    OTRO_TURISTA,
    cliente,
    habitacion_publicada,
    hotel_publicado,
    tour_publicado,
)

pytestmark = pytest.mark.django_db


def test_marcar_listar_y_quitar_un_favorito():
    api = cliente()
    tour = tour_publicado()

    creado = api.put(f"/api/v1/me/favoritos/{tour.id}/")
    assert creado.status_code == 201
    assert creado.json() == {"producto_id": tour.id, "favorito": True}

    # Marcar dos veces no duplica ni falla.
    assert api.put(f"/api/v1/me/favoritos/{tour.id}/").status_code == 200

    lista = api.get("/api/v1/me/favoritos/").json()
    assert [item["id"] for item in lista] == [tour.id]

    assert api.delete(f"/api/v1/me/favoritos/{tour.id}/").status_code == 204
    assert api.delete(f"/api/v1/me/favoritos/{tour.id}/").status_code == 204
    assert api.get("/api/v1/me/favoritos/").json() == []


def test_un_hotel_se_marca_por_su_producto_y_trae_precio_desde():
    api = cliente()
    hotel = hotel_publicado()

    assert api.put(f"/api/v1/me/favoritos/{hotel.product_id}/").status_code == 201
    [item] = api.get("/api/v1/me/favoritos/").json()
    assert item["hospedaje_id"] == hotel.id
    assert item["precio_desde"] is not None


def test_los_favoritos_son_de_cada_usuario():
    tour = tour_publicado()
    cliente().put(f"/api/v1/me/favoritos/{tour.id}/")
    assert cliente(OTRO_TURISTA).get("/api/v1/me/favoritos/").json() == []


def test_no_se_marca_lo_que_el_marketplace_no_muestra():
    api = cliente()
    borrador = TourismProduct.objects.exclude(status="PUBLICADO").order_by("id").first()
    habitacion = habitacion_publicada()

    if borrador is not None:
        assert api.put(f"/api/v1/me/favoritos/{borrador.id}/").status_code == 404
    # Una habitacion no se oferta suelta: se llega a ella por su hotel.
    assert api.put(f"/api/v1/me/favoritos/{habitacion.product_id}/").status_code == 404
    assert api.put("/api/v1/me/favoritos/999999999/").status_code == 404


def test_un_producto_despublicado_se_oculta_sin_perder_la_marca():
    api = cliente()
    tour = tour_publicado()
    api.put(f"/api/v1/me/favoritos/{tour.id}/")

    TourismProduct.objects.filter(id=tour.id).update(status="INACTIVO")
    assert api.get("/api/v1/me/favoritos/").json() == []

    TourismProduct.objects.filter(id=tour.id).update(status="PUBLICADO")
    assert [item["id"] for item in api.get("/api/v1/me/favoritos/").json()] == [tour.id]


def test_sin_sesion_no_hay_favoritos():
    from rest_framework.test import APIClient

    assert APIClient().get("/api/v1/me/favoritos/").status_code == 401
