"""Tours y experiencias (CU20) contra PostgreSQL real.

Cubre la ficha y el recorrido, las salidas (sueltas y repetidas), los guias,
las reglas para publicar, la reserva por salida y el paso de un tour del
catalogo generico al modulo de tours.
"""

from datetime import datetime, time, timedelta
from decimal import Decimal
from itertools import pairwise
from zoneinfo import ZoneInfo

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.bookings.models import InventoryLock
from apps.catalog.models import (
    Availability,
    Guide,
    TourDetail,
    TourismProduct,
    TourStop,
)
from apps.tenancy.models import PlanLimit, Subscription
from apps.tenancy.subscriptions import owner_ids

from .datos import _hoy, aceptar_politica, cliente, tour_publicado

pytestmark = pytest.mark.django_db

ZONA = ZoneInfo(settings.TIME_ZONE)


# --- Ayudas ---------------------------------------------------------------------


def _empresa_con_tours() -> int:
    return tour_publicado().tenant_id


def _dueno(tenant_id: int) -> APIClient:
    api = APIClient()
    api.force_authenticate(User.objects.get(id=owner_ids(tenant_id)[0]))
    api.credentials(HTTP_X_TENANT_ID=str(tenant_id))
    return api


def _otra_empresa(tenant_id: int) -> int:
    return (
        TourismProduct.objects.exclude(tenant_id=tenant_id)
        .filter(tenant__status="ACTIVO")
        .values_list("tenant_id", flat=True)
        .first()
    )


def _hora(dias: int, hora: int = 8, minuto: int = 0) -> datetime:
    return datetime.combine(_hoy() + timedelta(days=dias), time(hora, minuto), tzinfo=ZONA)


def _datos_tour(**cambios) -> dict:
    base = tour_publicado()
    return {
        "tipo_codigo": "TOUR",
        "nombre": "Salar al amanecer",
        "descripcion": "Recorrido por el salar con desayuno.",
        "ciudad_id": base.city_id,
        "moneda_codigo": base.currency.iso_code,
        "precio_base": "350.00",
        "capacidad_maxima": 12,
        "duracion_minutos": 210,
        "idioma": "Español",
        "dificultad": "MEDIA",
        "edad_minima": 8,
        "punto_encuentro": "Plaza principal de Uyuni",
        "latitud": "-20.4600001234",
        "longitud": "-66.8250005678",
        "incluye": ["Transporte", "Desayuno"],
        "no_incluye": ["Propinas"],
        "paradas": [
            {"nombre": "Cementerio de trenes", "duracion_minutos": 30},
            {"nombre": "Isla Incahuasi", "descripcion": "Cactus gigantes", "duracion_minutos": 60},
        ],
        **cambios,
    }


def _crear_tour(api: APIClient, **cambios) -> dict:
    respuesta = api.post("/api/v1/tours/", _datos_tour(**cambios), format="json")
    assert respuesta.status_code == 201, respuesta.json()
    return respuesta.json()


def _crear_salida(api: APIClient, tour_id: int, inicio: datetime, **extra) -> dict:
    respuesta = api.post(f"/api/v1/tours/{tour_id}/salidas/", {"inicio": inicio.isoformat(), **extra}, format="json")
    assert respuesta.status_code == 201, respuesta.json()
    return respuesta.json()


def _publicar(api: APIClient, tour_id: int):
    return api.patch(f"/api/v1/tours/{tour_id}/", {"estado": "PUBLICADO"}, format="json")


def _tour_publicado_con_salida(api: APIClient, **cambios) -> tuple[dict, dict]:
    tour = _crear_tour(api, **cambios)
    salida = _crear_salida(api, tour["id"], _hora(5))
    assert _publicar(api, tour["id"]).status_code == 200
    return tour, salida


def _detalles(respuesta) -> dict:
    return respuesta.json()["error"]["details"]


# --- Ficha y recorrido ------------------------------------------------------------


def test_crear_un_tour_guarda_producto_ficha_y_paradas_en_borrador():
    tenant_id = _empresa_con_tours()
    tour = _crear_tour(_dueno(tenant_id))

    assert tour["estado"] == "BORRADOR"
    assert tour["tipo_codigo"] == "TOUR"
    assert tour["detalle"]["duracion"] == "3 h 30 min"
    assert tour["detalle"]["incluye"] == ["Transporte", "Desayuno"]
    # Las coordenadas se redondean a seis decimales, como en hospedaje.
    assert tour["detalle"]["latitud"] == "-20.460000"
    assert [p["orden"] for p in tour["paradas"]] == [1, 2]
    assert tour["paradas"][1]["nombre"] == "Isla Incahuasi"
    assert TourDetail.objects.filter(product_id=tour["id"], tenant_id=tenant_id).exists()


def test_un_tour_nuevo_no_nace_publicado():
    respuesta = _dueno(_empresa_con_tours()).post("/api/v1/tours/", _datos_tour(estado="PUBLICADO"), format="json")
    assert respuesta.status_code == 400
    assert "estado" in _detalles(respuesta)


def test_media_coordenada_es_un_error():
    datos = _datos_tour()
    datos.pop("longitud")
    respuesta = _dueno(_empresa_con_tours()).post("/api/v1/tours/", datos, format="json")
    assert respuesta.status_code == 400
    assert "longitud" in _detalles(respuesta)


def test_guardar_el_recorrido_reemplaza_las_paradas_en_el_orden_recibido():
    api = _dueno(_empresa_con_tours())
    tour = _crear_tour(api)

    respuesta = api.put(
        f"/api/v1/tours/{tour['id']}/paradas/",
        {"paradas": [{"nombre": "Ojos del Salar"}, {"nombre": "Cementerio de trenes"}, {"nombre": "Atardecer"}]},
        format="json",
    )

    assert respuesta.status_code == 200, respuesta.json()
    assert [p["nombre"] for p in respuesta.json()] == ["Ojos del Salar", "Cementerio de trenes", "Atardecer"]
    assert TourStop.objects.filter(product_id=tour["id"]).count() == 3


def test_la_lista_incluye_los_tours_del_catalogo_generico_sin_ficha():
    tenant_id = _empresa_con_tours()
    lista = _dueno(tenant_id).get("/api/v1/tours/").json()
    generico = tour_publicado()

    fila = next(item for item in lista if item["id"] == generico.id)
    assert fila["detalle"] is None


def test_otra_empresa_no_ve_ni_edita_el_tour():
    tenant_id = _empresa_con_tours()
    tour = _crear_tour(_dueno(tenant_id))
    ajena = _dueno(_otra_empresa(tenant_id))

    assert ajena.get(f"/api/v1/tours/{tour['id']}/").status_code == 404
    assert ajena.patch(f"/api/v1/tours/{tour['id']}/", {"nombre": "x"}, format="json").status_code == 404
    assert ajena.post(f"/api/v1/tours/{tour['id']}/salidas/", {"inicio": _hora(3).isoformat()}, format="json").status_code == 404


def test_sin_iniciar_sesion_la_api_de_empresa_da_401():
    assert APIClient().get("/api/v1/tours/", HTTP_X_TENANT_ID="1").status_code == 401


# --- Salidas ----------------------------------------------------------------------


def test_una_salida_toma_el_fin_de_la_duracion_y_el_cupo_de_la_capacidad():
    api = _dueno(_empresa_con_tours())
    tour = _crear_tour(api)

    salida = _crear_salida(api, tour["id"], _hora(4))

    inicio = datetime.fromisoformat(salida["inicio"])
    fin = datetime.fromisoformat(salida["fin"])
    assert fin - inicio == timedelta(minutes=210)
    assert salida["cupo"] == 12
    assert salida["disponibles"] == 12


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"inicio": "2000-01-01T08:00:00-04:00"}, "inicio"),
        ({"cupo": 99}, "cupo"),
    ],
)
def test_una_salida_valida_horario_y_cupo(cambios, campo):
    api = _dueno(_empresa_con_tours())
    tour = _crear_tour(api)
    respuesta = api.post(f"/api/v1/tours/{tour['id']}/salidas/", {"inicio": _hora(4).isoformat(), **cambios}, format="json")
    assert respuesta.status_code == 400
    assert campo in _detalles(respuesta)


def test_no_se_repite_la_hora_de_una_salida():
    api = _dueno(_empresa_con_tours())
    tour = _crear_tour(api)
    _crear_salida(api, tour["id"], _hora(4))

    respuesta = api.post(f"/api/v1/tours/{tour['id']}/salidas/", {"inicio": _hora(4).isoformat()}, format="json")
    assert respuesta.status_code == 400
    assert "inicio" in _detalles(respuesta)


def test_un_tour_sin_ficha_no_tiene_salidas():
    generico = tour_publicado()
    respuesta = _dueno(generico.tenant_id).post(
        f"/api/v1/tours/{generico.id}/salidas/", {"inicio": _hora(4).isoformat()}, format="json"
    )
    assert respuesta.status_code == 400
    assert "tour" in _detalles(respuesta)


def test_salidas_repetidas_crean_una_por_dia_elegido_y_omiten_las_que_ya_existen():
    api = _dueno(_empresa_con_tours())
    tour = _crear_tour(api)
    desde = _hoy() + timedelta(days=1)
    hasta = desde + timedelta(days=13)
    pedido = {"dias_semana": [0, 3], "hora_inicio": "08:00", "desde": desde.isoformat(), "hasta": hasta.isoformat()}

    primera = api.post(f"/api/v1/tours/{tour['id']}/salidas/", pedido, format="json")

    assert primera.status_code == 201, primera.json()
    esperadas = sum(1 for n in range(14) if (desde + timedelta(days=n)).weekday() in (0, 3))
    assert len(primera.json()["creadas"]) == esperadas == 4
    for salida in primera.json()["creadas"]:
        local = datetime.fromisoformat(salida["inicio"]).astimezone(ZONA)
        assert local.weekday() in (0, 3)
        assert local.time() == time(8, 0)

    # Repetir la misma carga no duplica nada.
    segunda = api.post(f"/api/v1/tours/{tour['id']}/salidas/", pedido, format="json")
    assert segunda.status_code == 400
    assert Availability.objects.filter(product_id=tour["id"]).count() == 4


def test_salidas_repetidas_tienen_un_tope_de_dias():
    api = _dueno(_empresa_con_tours())
    tour = _crear_tour(api)
    desde = _hoy() + timedelta(days=1)
    pedido = {"dias_semana": [0], "hora_inicio": "08:00", "desde": desde.isoformat(),
              "hasta": (desde + timedelta(days=120)).isoformat()}
    respuesta = api.post(f"/api/v1/tours/{tour['id']}/salidas/", pedido, format="json")
    assert respuesta.status_code == 400
    assert "hasta" in _detalles(respuesta)


def test_una_salida_sin_reservas_se_mueve_y_se_elimina():
    api = _dueno(_empresa_con_tours())
    tour = _crear_tour(api)
    salida = _crear_salida(api, tour["id"], _hora(4))

    movida = api.patch(f"/api/v1/salidas/{salida['id']}/", {"inicio": _hora(4, 14).isoformat()}, format="json")
    assert movida.status_code == 200, movida.json()
    # Al mover solo el inicio, la salida conserva su duracion.
    assert datetime.fromisoformat(movida.json()["fin"]) - datetime.fromisoformat(movida.json()["inicio"]) == timedelta(minutes=210)

    assert api.delete(f"/api/v1/salidas/{salida['id']}/").status_code == 204
    assert not Availability.objects.filter(id=salida["id"]).exists()


# --- Guias ------------------------------------------------------------------------


def test_un_guia_no_puede_estar_en_dos_salidas_que_se_cruzan():
    api = _dueno(_empresa_con_tours())
    guia = api.post("/api/v1/guias/", {"nombres": "Marcelo Choque", "idiomas": ["Español", "Inglés"]}, format="json")
    assert guia.status_code == 201, guia.json()
    guia_id = guia.json()["id"]
    tour = _crear_tour(api)
    _crear_salida(api, tour["id"], _hora(6, 8), guia_id=guia_id)

    otra = _crear_tour(api, nombre="Ojos del salar")
    cruzada = api.post(
        f"/api/v1/tours/{otra['id']}/salidas/", {"inicio": _hora(6, 10).isoformat(), "guia_id": guia_id}, format="json"
    )
    assert cruzada.status_code == 400
    assert "guia_id" in _detalles(cruzada)

    # Despues de terminar la primera, el guia si esta libre.
    libre = api.post(
        f"/api/v1/tours/{otra['id']}/salidas/", {"inicio": _hora(6, 13).isoformat(), "guia_id": guia_id}, format="json"
    )
    assert libre.status_code == 201, libre.json()


def test_un_guia_con_salidas_proximas_no_se_desactiva_y_uno_inactivo_no_se_asigna():
    api = _dueno(_empresa_con_tours())
    guia_id = api.post("/api/v1/guias/", {"nombres": "Rosa Mamani"}, format="json").json()["id"]
    tour = _crear_tour(api)
    salida = _crear_salida(api, tour["id"], _hora(6), guia_id=guia_id)

    bloqueado = api.delete(f"/api/v1/guias/{guia_id}/")
    assert bloqueado.status_code == 400

    api.patch(f"/api/v1/salidas/{salida['id']}/", {"guia_id": None}, format="json")
    assert api.delete(f"/api/v1/guias/{guia_id}/").json()["estado"] == "INACTIVO"

    respuesta = api.post(f"/api/v1/tours/{tour['id']}/salidas/", {"inicio": _hora(7).isoformat(), "guia_id": guia_id}, format="json")
    assert respuesta.status_code == 400
    assert "guia_id" in _detalles(respuesta)


def test_el_guia_de_otra_empresa_no_se_asigna():
    tenant_id = _empresa_con_tours()
    ajeno = Guide.objects.create(tenant_id=_otra_empresa(tenant_id), names="Guía ajeno")
    api = _dueno(tenant_id)
    tour = _crear_tour(api)

    respuesta = api.post(f"/api/v1/tours/{tour['id']}/salidas/", {"inicio": _hora(4).isoformat(), "guia_id": ajeno.id}, format="json")
    assert respuesta.status_code == 400
    assert "guia_id" in _detalles(respuesta)


# --- Publicar ---------------------------------------------------------------------


def test_publicar_sin_salidas_ni_punto_de_encuentro_dice_que_falta():
    api = _dueno(_empresa_con_tours())
    tour = _crear_tour(api, punto_encuentro="")

    respuesta = _publicar(api, tour["id"])

    assert respuesta.status_code == 400
    problemas = " ".join(_detalles(respuesta)["estado"])
    assert "punto de encuentro" in problemas
    assert "salida futura" in problemas


def test_con_salida_y_punto_de_encuentro_se_publica_y_aparece_en_el_marketplace():
    api = _dueno(_empresa_con_tours())
    tour, salida = _tour_publicado_con_salida(api)

    ficha = APIClient().get(f"/api/v1/marketplace/tours/{tour['id']}/")
    salidas = APIClient().get(f"/api/v1/marketplace/tours/{tour['id']}/salidas/")

    assert ficha.status_code == 200
    assert ficha.json()["detalle"]["punto_encuentro"] == "Plaza principal de Uyuni"
    assert ficha.json()["salidas_proximas"] == 1
    assert [s["id"] for s in salidas.json()] == [salida["id"]]
    # El turista no ve el telefono del guia.
    assert "guia_id" not in salidas.json()[0]


def test_la_via_generica_tampoco_publica_un_tour_sin_salidas():
    api = _dueno(_empresa_con_tours())
    tour = _crear_tour(api)
    respuesta = api.patch(f"/api/v1/productos/{tour['id']}/", {"estado": "PUBLICADO"}, format="json")
    assert respuesta.status_code == 400


def test_el_limite_del_plan_frena_la_publicacion():
    tenant_id = _empresa_con_tours()
    api = _dueno(tenant_id)
    plan = Subscription.objects.get(tenant_id=tenant_id, status="ACTIVA").plan
    publicados = TourismProduct.objects.filter(tenant_id=tenant_id, product_type__code="TOUR", status="PUBLICADO").count()
    PlanLimit.objects.update_or_create(plan=plan, resource="TOURS_PUBLICADOS", defaults={"limit": publicados})
    tour = _crear_tour(api)
    _crear_salida(api, tour["id"], _hora(5))

    respuesta = _publicar(api, tour["id"])

    assert respuesta.status_code == 400
    assert "plan" in " ".join(_detalles(respuesta)["estado"])


def test_el_cron_no_publica_un_tour_sin_salidas():
    from apps.catalog.scheduling import process_due

    api = _dueno(_empresa_con_tours())
    tour = _crear_tour(api)
    TourismProduct.objects.filter(id=tour["id"]).update(publish_at=timezone.now() - timedelta(minutes=1))

    process_due()

    assert TourismProduct.objects.get(id=tour["id"]).status == "BORRADOR"


# --- Reservar por salida ------------------------------------------------------------


def _pedido(tour: dict, **extra) -> dict:
    producto = TourismProduct.objects.get(id=tour["id"])
    return aceptar_politica(producto, {"producto_id": tour["id"], "cantidad": 2, **extra})


def test_cotizar_y_reservar_una_salida_toma_su_cupo(stripe):
    api = _dueno(_empresa_con_tours())
    tour, salida = _tour_publicado_con_salida(api)

    cotizacion = cliente().post("/api/v1/me/reservas/cotizacion/", _pedido(tour, salida_id=salida["id"]), format="json")
    assert cotizacion.status_code == 200, cotizacion.json()
    assert cotizacion.json()["salida_id"] == salida["id"]
    assert cotizacion.json()["disponibles"] == 12
    assert Decimal(cotizacion.json()["total"]) == Decimal("700.00")

    reserva = cliente().post("/api/v1/me/reservas/", _pedido(tour, salida_id=salida["id"]), format="json")
    assert reserva.status_code == 201, reserva.json()
    lock = InventoryLock.objects.get(booking_id=reserva.json()["id"])
    assert lock.slot_id == salida["id"]
    # No se crea ningun cupo diario a medianoche.
    assert Availability.objects.filter(product_id=tour["id"]).count() == 1

    vista = api.get(f"/api/v1/tours/{tour['id']}/salidas/").json()
    assert vista[0]["reservados"] == 2
    assert vista[0]["disponibles"] == 10


def test_reservar_por_fecha_usa_la_unica_salida_de_ese_dia(stripe):
    api = _dueno(_empresa_con_tours())
    tour, salida = _tour_publicado_con_salida(api)
    dia = datetime.fromisoformat(salida["inicio"]).astimezone(ZONA).date()

    cotizacion = cliente().post("/api/v1/me/reservas/cotizacion/", _pedido(tour, fecha_inicio=dia.isoformat()), format="json")

    assert cotizacion.status_code == 200, cotizacion.json()
    assert cotizacion.json()["salida_id"] == salida["id"]


def test_con_dos_salidas_el_mismo_dia_y_solo_la_fecha_se_usa_la_primera_con_lugar(stripe):
    """Contrato de la app movil: solo fecha. Se toma la primera salida que tenga cupo."""
    api = _dueno(_empresa_con_tours())
    tour, salida = _tour_publicado_con_salida(api)
    tarde = _crear_salida(api, tour["id"], _hora(5, 15))
    dia = datetime.fromisoformat(salida["inicio"]).astimezone(ZONA).date()

    respuesta = cliente().post("/api/v1/me/reservas/cotizacion/", _pedido(tour, fecha_inicio=dia.isoformat()), format="json")
    assert respuesta.status_code == 200, respuesta.json()
    assert respuesta.json()["salida_id"] == salida["id"]

    # Llena la primera: la siguiente cotizacion por fecha toma la de la tarde.
    api.patch(f"/api/v1/salidas/{salida['id']}/", {"cupo": 1}, format="json")
    respuesta = cliente().post("/api/v1/me/reservas/cotizacion/", _pedido(tour, fecha_inicio=dia.isoformat()), format="json")
    assert respuesta.json()["salida_id"] == tarde["id"]


def test_un_dia_sin_salidas_no_se_reserva(stripe):
    api = _dueno(_empresa_con_tours())
    tour, _ = _tour_publicado_con_salida(api)
    respuesta = cliente().post(
        "/api/v1/me/reservas/cotizacion/", _pedido(tour, fecha_inicio=(_hoy() + timedelta(days=20)).isoformat()), format="json"
    )
    assert respuesta.status_code == 400
    assert "fecha_inicio" in _detalles(respuesta)


def test_una_salida_con_reservas_no_cambia_de_hora_ni_baja_su_cupo_ni_se_elimina(stripe):
    api = _dueno(_empresa_con_tours())
    tour, salida = _tour_publicado_con_salida(api)
    cliente().post("/api/v1/me/reservas/", _pedido(tour, salida_id=salida["id"], cantidad=3), format="json")

    hora = api.patch(f"/api/v1/salidas/{salida['id']}/", {"inicio": _hora(5, 16).isoformat()}, format="json")
    cupo = api.patch(f"/api/v1/salidas/{salida['id']}/", {"cupo": 2}, format="json")
    borrar = api.delete(f"/api/v1/salidas/{salida['id']}/")

    assert hora.status_code == 400
    assert cupo.status_code == 400
    assert borrar.status_code == 400
    assert api.patch(f"/api/v1/salidas/{salida['id']}/", {"cupo": 3}, format="json").status_code == 200


def test_una_salida_cerrada_deja_de_venderse_pero_conserva_sus_reservas(stripe):
    api = _dueno(_empresa_con_tours())
    tour, salida = _tour_publicado_con_salida(api)
    reserva = cliente().post("/api/v1/me/reservas/", _pedido(tour, salida_id=salida["id"]), format="json").json()

    cerrada = api.post(f"/api/v1/salidas/{salida['id']}/cerrar/")

    assert cerrada.status_code == 200
    assert cerrada.json()["cerrada"] is True
    assert APIClient().get(f"/api/v1/marketplace/tours/{tour['id']}/salidas/").json() == []
    otra = cliente("turista2@situr.com.bo").post(
        "/api/v1/me/reservas/cotizacion/", _pedido(tour, salida_id=salida["id"]), format="json"
    )
    assert otra.status_code == 400
    assert cliente().get(f"/api/v1/me/reservas/{reserva['id']}/").status_code == 200


# --- Del catalogo generico al modulo de tours ---------------------------------------


def test_completar_la_ficha_de_un_tour_generico_publicado_lo_pasa_a_salidas(stripe):
    generico = tour_publicado()
    api = _dueno(generico.tenant_id)
    # Un cupo diario a futuro, como los que crea el catalogo generico al reservar.
    pedido = aceptar_politica(
        generico, {"producto_id": generico.id, "fecha_inicio": (_hoy() + timedelta(days=9)).isoformat(), "cantidad": 1}
    )
    assert cliente().post("/api/v1/me/reservas/", pedido, format="json").status_code == 201

    respuesta = api.patch(
        f"/api/v1/tours/{generico.id}/", {"punto_encuentro": "Oficina central", "duracion_minutos": 180}, format="json"
    )

    assert respuesta.status_code == 200, respuesta.json()
    assert respuesta.json()["estado"] == "BORRADOR"
    assert "salidas" in respuesta.json()["aviso"]
    # Los cupos diarios futuros se cierran; la reserva que ya tenian sigue.
    assert not Availability.objects.filter(product=generico, closed=False, start__gt=timezone.now()).exists()


# --- Datos de demostracion (seed_bolivia) ---------------------------------------------


def test_el_seed_deja_los_tours_con_ficha_recorrido_guias_y_salidas():
    from .datos import tour_con_salidas

    tour = tour_con_salidas()
    assert tour is not None
    detalle = TourDetail.objects.get(product=tour)
    assert detalle.meeting_point
    assert TourStop.objects.filter(product=tour).count() >= 2
    proximas = Availability.objects.filter(product=tour, start__gt=timezone.now(), closed=False)
    assert proximas.count() >= 5
    # Ningun guia queda en dos salidas abiertas que se cruzan.
    for guia in Guide.objects.filter(tenant_id=tour.tenant_id):
        salidas = list(Availability.objects.filter(guide=guia, closed=False).order_by("start"))
        for anterior, siguiente in pairwise(salidas):
            assert anterior.end <= siguiente.start, (guia.names, anterior.start, siguiente.start)


def test_el_seed_deja_un_borrador_sin_salidas_y_una_experiencia_sin_ficha():
    borrador = TourismProduct.objects.get(name="Amanecer en el Espejo del Salar")
    assert borrador.status == "BORRADOR"
    assert TourDetail.objects.filter(product=borrador).exists()
    assert not Availability.objects.filter(product=borrador).exists()

    sin_ficha = TourismProduct.objects.get(name="Caminata Guiada al Muro de Huellas")
    assert not TourDetail.objects.filter(product=sin_ficha).exists()


def test_volver_a_ejecutar_el_seed_no_duplica_salidas_ni_guias():
    from io import StringIO

    from django.core.management import call_command

    salidas = Availability.objects.count()
    guias = Guide.objects.count()
    fichas = TourDetail.objects.count()

    call_command("seed_bolivia", stdout=StringIO())

    assert Availability.objects.count() == salidas
    assert Guide.objects.count() == guias
    assert TourDetail.objects.count() == fichas


def test_el_seed_completa_los_tours_de_una_empresa_que_ya_existia():
    """Como en Railway: la empresa ya estaba cargada de antes de CU20."""
    from io import StringIO

    from django.core.management import call_command

    tour = TourismProduct.objects.get(name="Salar de Uyuni Día Completo")
    Availability.objects.filter(product=tour).delete()
    TourStop.objects.filter(product=tour).delete()
    TourDetail.objects.filter(product=tour).delete()

    call_command("seed_bolivia", stdout=StringIO())

    tour.refresh_from_db()
    assert TourDetail.objects.filter(product=tour).exists()
    assert Availability.objects.filter(product=tour, start__gt=timezone.now()).count() >= 30
    assert tour.status == "PUBLICADO"


def test_un_turista_reserva_una_salida_del_seed(stripe):
    from .datos import tour_con_salidas

    tour = tour_con_salidas()
    salida = APIClient().get(f"/api/v1/marketplace/tours/{tour.id}/salidas/").json()[0]
    pedido = aceptar_politica(tour, {"producto_id": tour.id, "salida_id": salida["id"], "cantidad": 1})

    respuesta = cliente().post("/api/v1/me/reservas/", pedido, format="json")

    assert respuesta.status_code == 201, respuesta.json()
    assert InventoryLock.objects.get(booking_id=respuesta.json()["id"]).slot_id == salida["id"]
