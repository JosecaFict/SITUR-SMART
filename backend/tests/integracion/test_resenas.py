"""CU35 sobre PostgreSQL aislado, con el esquema SQL y las migraciones Django."""

import pytest
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import ProductReview, TourismProduct
from apps.catalog.seed.bolivia import PASSWORD

from .datos import (
    OTRO_TURISTA,
    TURISTA,
    cliente,
    habitacion_publicada,
    hotel_publicado,
    tour_publicado,
)

pytestmark = pytest.mark.django_db


def _url(product_id):
    return f"/api/v1/marketplace/productos/{product_id}/resenas/"


def _create(api, product_id, rating=5, comment="Excelente experiencia"):
    return api.post(_url(product_id), {"calificacion": rating, "comentario": comment}, format="json")


def _summary(api, product_id):
    response = api.get(f"/api/v1/marketplace/productos/{product_id}/")
    assert response.status_code == 200
    return response.json()


def test_crear_y_consultar_publicamente_con_autor_limitado():
    tour = tour_publicado()
    api = cliente()
    created = _create(api, tour.id)
    assert created.status_code == 201
    review = created.json()
    assert review["producto_id"] == tour.id
    assert review["calificacion"] == 5
    assert review["comentario"] == "Excelente experiencia"
    assert review["autor"]
    assert review["es_propia"] is True
    assert review["creado_en"] and review["actualizado_en"]
    assert "email" not in review and "password" not in review

    public = APIClient().get(_url(tour.id), {"page_size": 1})
    assert public.status_code == 200
    assert public.json()["count"] == 1
    assert public.json()["results"][0]["es_propia"] is False
    assert public.json()["results"][0]["id"] == review["id"]


def test_consulta_resena_propia_por_producto_sin_exponer_la_ajena():
    tour = tour_publicado()
    owner = cliente()
    other = cliente(OTRO_TURISTA)
    url = f"/api/v1/me/productos/{tour.id}/resena/"
    assert APIClient().get(url).status_code == 401
    assert owner.get(url).status_code == 200
    assert owner.get(url).json() == {"resena": None}
    created = _create(owner, tour.id).json()
    assert owner.get(url).json()["resena"]["id"] == created["id"]
    assert owner.get(url).json()["resena"]["es_propia"] is True
    assert other.get(url).json() == {"resena": None}


@pytest.mark.parametrize("rating,comment", [
    (0, "Bueno"), (6, "Bueno"), (1.5, "Bueno"),
    (5, ""), (5, "   "), (5, "\t\n"),
])
def test_calificacion_y_comentario_invalidos(rating, comment):
    response = _create(cliente(), tour_publicado().id, rating, comment)
    assert response.status_code == 400


def test_visitante_no_publica_y_no_puede_suplantar_autor():
    tour = tour_publicado()
    assert _create(APIClient(), tour.id).status_code == 401
    api = cliente()
    response = api.post(
        _url(tour.id),
        {"calificacion": 4, "comentario": "Muy bueno", "usuario_id": 999999},
        format="json",
    )
    assert response.status_code == 201
    assert ProductReview.objects.get(id=response.json()["id"]).user_id == User.objects.get(
        email=TURISTA
    ).id


def test_duplicado_rechazado_y_restricciones_en_base():
    tour = tour_publicado()
    api = cliente()
    assert _create(api, tour.id).status_code == 201
    duplicate = _create(api, tour.id)
    assert duplicate.status_code == 400
    assert "reseña" in str(duplicate.json()).lower()
    user = User.objects.get(email=OTRO_TURISTA)
    for rating, comment in [(0, "Bueno"), (6, "Bueno"), (5, "  ")]:
        with pytest.raises(IntegrityError), transaction.atomic():
            ProductReview.objects.create(
                user=user, product=tour, rating=rating, comment=comment,
            )


def test_editar_eliminar_y_negar_resenas_ajenas():
    tour = tour_publicado()
    owner = cliente()
    other = cliente(OTRO_TURISTA)
    review_id = _create(owner, tour.id).json()["id"]
    url = f"/api/v1/me/resenas/{review_id}/"
    assert other.patch(url, {"calificacion": 1}, format="json").status_code == 404
    assert other.delete(url).status_code == 404
    assert APIClient().patch(url, {"calificacion": 1}, format="json").status_code == 401
    changed = owner.patch(url, {"calificacion": 3, "comentario": "  Mejorable  "}, format="json")
    assert changed.status_code == 200
    assert changed.json()["calificacion"] == 3
    assert changed.json()["comentario"] == "Mejorable"
    assert owner.patch(url, {"comentario": "  "}, format="json").status_code == 400
    assert owner.delete(url).status_code == 204
    assert owner.delete(url).status_code == 404


def test_promedio_se_actualiza_al_crear_editar_y_eliminar():
    tour = tour_publicado()
    first = cliente()
    second = cliente(OTRO_TURISTA)
    assert _summary(first, tour.id)["calificacion_promedio"] is None
    assert _summary(first, tour.id)["cantidad_resenas"] == 0

    first_id = _create(first, tour.id, 3).json()["id"]
    assert _create(second, tour.id, 5).status_code == 201
    assert _summary(first, tour.id)["calificacion_promedio"] == 4
    assert _summary(first, tour.id)["cantidad_resenas"] == 2

    first.patch(f"/api/v1/me/resenas/{first_id}/", {"calificacion": 1}, format="json")
    assert _summary(first, tour.id)["calificacion_promedio"] == 3
    assert first.delete(f"/api/v1/me/resenas/{first_id}/").status_code == 204
    assert _summary(first, tour.id)["calificacion_promedio"] == 5
    assert _summary(first, tour.id)["cantidad_resenas"] == 1


def test_productos_ocultos_o_inexistentes_no_admiten_consulta_ni_publicacion():
    tour = tour_publicado()
    api = cliente()
    for product_id in (999999999,):
        assert APIClient().get(_url(product_id)).status_code == 404
        assert _create(api, product_id).status_code == 404
    TourismProduct.objects.filter(id=tour.id).update(status="INACTIVO")
    assert APIClient().get(_url(tour.id)).status_code == 404
    assert _create(api, tour.id).status_code == 404


def test_hoteles_y_habitaciones_usan_id_de_producto_y_no_categoria_estrellas():
    hotel = hotel_publicado()
    room = habitacion_publicada()
    api = cliente()
    assert _create(api, hotel.product_id, 2).status_code == 201
    hotel_response = api.get(f"/api/v1/marketplace/hospedajes/{hotel.id}/")
    assert hotel_response.status_code == 200
    assert hotel_response.json()["calificacion_promedio"] == 2
    assert hotel_response.json()["categoria_estrellas"] == hotel.star_rating
    assert _create(api, room.product_id, 4).status_code == 201
    room_response = api.get(f"/api/v1/marketplace/habitaciones/{room.id}/")
    assert room_response.status_code == 200
    assert room_response.json()["calificacion_promedio"] == 4
    assert _summary(api, hotel.product_id)["calificacion_promedio"] == 2
    TourismProduct.objects.filter(id=room.establishment.product_id).update(status="INACTIVO")
    assert APIClient().get(_url(room.product_id)).status_code == 404


def test_marketplace_sigue_paginando_sin_n_mas_una_consultas_por_resenas():
    tour = tour_publicado()
    _create(cliente(), tour.id, 5)
    api = APIClient()
    with CaptureQueriesContext(connection) as one:
        first = api.get("/api/v1/marketplace/productos/", {"page_size": 1})
    with CaptureQueriesContext(connection) as many:
        full = api.get("/api/v1/marketplace/productos/", {"page_size": 12})
    assert first.status_code == full.status_code == 200
    assert len(full.json()["results"]) > len(first.json()["results"])
    assert len(many) <= len(one) + 1
    assert any(item["id"] == tour.id for item in full.json()["results"]) or _summary(api, tour.id)["cantidad_resenas"] == 1


def test_listado_publico_ordenado_y_paginado():
    tour = tour_publicado()
    _create(cliente(), tour.id, 2)
    _create(cliente(OTRO_TURISTA), tour.id, 5)
    page = APIClient().get(_url(tour.id), {"page_size": 1, "page": 1}).json()
    assert page["count"] == 2
    assert len(page["results"]) == 1
    assert page["next"]
    assert page["distribucion_calificaciones"] == {
        "1": 0, "2": 1, "3": 0, "4": 0, "5": 1,
    }


def test_distribucion_se_actualiza_sin_depender_de_la_pagina():
    tour = tour_publicado()
    first = cliente()
    second = cliente(OTRO_TURISTA)
    first_id = _create(first, tour.id, 4).json()["id"]
    _create(second, tour.id, 5)

    with CaptureQueriesContext(connection) as page_one_queries:
        first_page = APIClient().get(_url(tour.id), {"page_size": 1, "page": 1})
    with CaptureQueriesContext(connection) as page_two_queries:
        second_page = APIClient().get(_url(tour.id), {"page_size": 1, "page": 2})
    assert first_page.status_code == second_page.status_code == 200
    expected = {"1": 0, "2": 0, "3": 0, "4": 1, "5": 1}
    assert first_page.json()["distribucion_calificaciones"] == expected
    assert second_page.json()["distribucion_calificaciones"] == expected
    assert len(page_one_queries) == len(page_two_queries)

    first.patch(f"/api/v1/me/resenas/{first_id}/", {"calificacion": 1}, format="json")
    expected.update({"1": 1, "4": 0})
    assert APIClient().get(_url(tour.id)).json()["distribucion_calificaciones"] == expected
    assert first.delete(f"/api/v1/me/resenas/{first_id}/").status_code == 204
    expected["1"] = 0
    assert APIClient().get(_url(tour.id)).json()["distribucion_calificaciones"] == expected


def test_baja_de_cuenta_retira_sus_comentarios_y_recalcula_el_resumen():
    tour = tour_publicado()
    api = cliente()
    assert _create(api, tour.id, 4).status_code == 201
    assert api.post("/api/v1/auth/me/eliminar/", {"password": PASSWORD}, format="json").status_code == 204
    assert ProductReview.objects.filter(product_id=tour.id).count() == 0
    assert _summary(APIClient(), tour.id)["cantidad_resenas"] == 0
