"""Itinerarios del turista contra PostgreSQL real."""

from datetime import timedelta

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import TourismProduct
from apps.itineraries.models import Itinerary
from apps.tenancy.models import City

from .datos import (
    OTRO_TURISTA,
    _hoy,
    _pedido_habitacion,
    _session_id,
    _webhook,
    cliente,
    habitacion_publicada,
    hotel_publicado,
    tour_publicado,
)

pytestmark = pytest.mark.django_db(transaction=False)

URL = "/api/v1/me/itinerarios/"


def _dia(offset: int) -> str:
    return (_hoy() + timedelta(days=offset)).isoformat()


def _crear(api=None, *, desde=10, hasta=13, **extra):
    api = api or cliente()
    respuesta = api.post(URL, {"nombre": "Viaje a Santa Cruz", "inicio": _dia(desde), "fin": _dia(hasta), **extra}, format="json")
    assert respuesta.status_code == 201, respuesta.json()
    return respuesta.json()


def _actividad(itinerario_id, **datos):
    return cliente().post(f"{URL}{itinerario_id}/actividades/", datos, format="json")


def _pagar(pedido):
    creada = cliente().post("/api/v1/me/reservas/", pedido, format="json").json()
    _webhook("checkout.session.completed", _session_id(creada["id"]))
    return creada


def test_crear_devuelve_un_dia_por_fecha_del_viaje():
    ciudad = City.objects.filter(active=True).order_by("id").first()
    data = _crear(ciudad_id=ciudad.id, notas="Llevar repelente")

    assert data["dias"] == 4
    assert data["ciudad"] == ciudad.name
    assert [dia["fecha"] for dia in data["agenda"]] == [_dia(10), _dia(11), _dia(12), _dia(13)]
    assert all(dia["reservas"] == [] and dia["actividades"] == [] for dia in data["agenda"])

    [resumen] = cliente().get(URL).json()
    assert resumen["id"] == data["id"]
    assert resumen["actividades"] == 0


@pytest.mark.parametrize(
    ("cambio", "campo"),
    [
        ({"inicio": _dia(5), "fin": _dia(4)}, "fin"),
        ({"inicio": _dia(1), "fin": _dia(61)}, "fin"),
        ({"nombre": "   "}, "nombre"),
        ({"ciudad_id": 999999}, "ciudad_id"),
    ],
)
def test_validaciones_al_crear(cambio, campo):
    pedido = {"nombre": "Viaje", "inicio": _dia(1), "fin": _dia(3), **cambio}
    respuesta = cliente().post(URL, pedido, format="json")
    assert respuesta.status_code == 400
    assert campo in respuesta.json()["error"]["details"]


def test_actividades_libres_y_de_producto_ordenadas_por_hora():
    itinerario = _crear()
    tour = tour_publicado()

    assert _actividad(itinerario["id"], fecha=_dia(11), hora="16:00", titulo="Comprar recuerdos").status_code == 201
    con_producto = _actividad(itinerario["id"], fecha=_dia(11), hora="09:00", producto_id=tour.id)
    assert con_producto.status_code == 201
    assert con_producto.json()["titulo"] == tour.name
    assert _actividad(itinerario["id"], fecha=_dia(11), titulo="Día libre").status_code == 201

    dia = cliente().get(f"{URL}{itinerario['id']}/").json()["agenda"][1]
    assert [a["titulo"] for a in dia["actividades"]] == ["Día libre", tour.name, "Comprar recuerdos"]
    assert [a["tipo"] for a in dia["actividades"]] == ["LIBRE", "PRODUCTO", "LIBRE"]
    assert dia["actividades"][1]["hora"] == "09:00"
    assert dia["actividades"][1]["producto"]["id"] == tour.id


def test_un_hotel_se_agrega_por_su_producto_y_un_producto_oculto_no():
    itinerario = _crear()
    hotel = hotel_publicado()
    assert _actividad(itinerario["id"], fecha=_dia(10), producto_id=hotel.product_id).json()["producto"]["hospedaje_id"] == hotel.id

    borrador = TourismProduct.objects.exclude(status="PUBLICADO").first()
    respuesta = _actividad(itinerario["id"], fecha=_dia(10), producto_id=borrador.id)
    assert respuesta.status_code == 400
    assert "producto_id" in respuesta.json()["error"]["details"]


def test_un_producto_que_deja_de_publicarse_queda_con_su_titulo():
    itinerario = _crear()
    tour = tour_publicado()
    _actividad(itinerario["id"], fecha=_dia(10), producto_id=tour.id)
    TourismProduct.objects.filter(id=tour.id).update(status="BORRADOR")

    [actividad] = cliente().get(f"{URL}{itinerario['id']}/").json()["agenda"][0]["actividades"]
    assert actividad["titulo"] == tour.name
    assert actividad["producto"] is None


def test_la_actividad_tiene_que_caer_dentro_del_viaje_y_tener_titulo():
    itinerario = _crear()
    assert _actividad(itinerario["id"], fecha=_dia(14), titulo="Tarde").status_code == 400
    assert _actividad(itinerario["id"], fecha=_dia(10), titulo="  ").status_code == 400


def test_editar_y_borrar_actividad():
    itinerario = _crear()
    actividad = _actividad(itinerario["id"], fecha=_dia(10), titulo="Museo").json()
    url = f"{URL}{itinerario['id']}/actividades/{actividad['id']}/"

    editada = cliente().patch(url, {"fecha": _dia(12), "hora": "10:30", "nota": "Cierra a las 18"}, format="json").json()
    assert (editada["fecha"], editada["hora"], editada["nota"]) == (_dia(12), "10:30", "Cierra a las 18")
    assert cliente().patch(url, {"fecha": _dia(20)}, format="json").status_code == 400

    assert cliente().delete(url).status_code == 204
    assert cliente().delete(url).status_code == 404


def test_achicar_el_viaje_con_actividades_afuera_se_rechaza():
    itinerario = _crear()
    _actividad(itinerario["id"], fecha=_dia(13), titulo="Último día")
    url = f"{URL}{itinerario['id']}/"

    respuesta = cliente().patch(url, {"fin": _dia(12)}, format="json")
    assert respuesta.status_code == 400
    assert "fuera de las nuevas fechas" in respuesta.json()["error"]["message"]

    ampliado = cliente().patch(url, {"fin": _dia(15), "nombre": "Santa Cruz y Samaipata"}, format="json").json()
    assert ampliado["dias"] == 6
    assert ampliado["nombre"] == "Santa Cruz y Samaipata"


def test_las_reservas_pagadas_aparecen_solas_en_su_dia(stripe):
    itinerario = _crear(desde=10, hasta=13)
    hotel = _pagar(_pedido_habitacion(habitacion_publicada(), dias=10, noches=2))
    tour = _pagar({"producto_id": tour_publicado().id, "fecha_inicio": _dia(11), "cantidad": 1})
    # Pendiente de pago: todavia no es parte del viaje.
    cliente().post("/api/v1/me/reservas/", {"producto_id": tour_publicado().id, "fecha_inicio": _dia(13), "cantidad": 1}, format="json")

    agenda = cliente().get(f"{URL}{itinerario['id']}/").json()["agenda"]
    reservas = {dia["fecha"]: [(r["reserva_id"], r["momento"]) for r in dia["reservas"]] for dia in agenda}
    assert reservas == {
        _dia(10): [(hotel["id"], "LLEGADA")],
        _dia(11): [(tour["id"], None)],
        _dia(12): [(hotel["id"], "SALIDA")],
        _dia(13): [],
    }
    llegada = agenda[0]["reservas"][0]
    assert llegada["codigo"] == hotel["codigo"]
    assert llegada["producto"]["es_hospedaje"] is True
    assert llegada["fechas"]["noches"] == 2


def test_la_salida_de_un_hotel_anterior_al_viaje_tambien_aparece(stripe):
    hotel = _pagar(_pedido_habitacion(habitacion_publicada(), dias=8, noches=2))
    itinerario = _crear(desde=10, hasta=11)

    agenda = cliente().get(f"{URL}{itinerario['id']}/").json()["agenda"]
    assert agenda[0]["reservas"][0]["reserva_id"] == hotel["id"]
    assert agenda[0]["reservas"][0]["momento"] == "SALIDA"


def test_cada_turista_ve_solo_lo_suyo(stripe):
    itinerario = _crear()
    _pagar({"producto_id": tour_publicado().id, "fecha_inicio": _dia(11), "cantidad": 1})
    otro = cliente(OTRO_TURISTA)

    assert otro.get(URL).json() == []
    assert otro.get(f"{URL}{itinerario['id']}/").status_code == 404
    assert otro.post(f"{URL}{itinerario['id']}/actividades/", {"fecha": _dia(10), "titulo": "x"}, format="json").status_code == 404
    assert otro.delete(f"{URL}{itinerario['id']}/").status_code == 404

    propio = _crear(otro)
    assert all(dia["reservas"] == [] for dia in propio["agenda"])
    assert APIClient().get(URL).status_code == 401


def test_borrar_el_itinerario_borra_sus_actividades():
    itinerario = _crear()
    _actividad(itinerario["id"], fecha=_dia(10), titulo="Museo")
    assert cliente().delete(f"{URL}{itinerario['id']}/").status_code == 204
    assert not Itinerary.objects.exists()
