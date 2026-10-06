"""Reservas y pagos contra PostgreSQL real, con Stripe simulado.

La pasarela se reemplaza por ``StripeFalso``: guarda las sesiones en memoria y
permite marcarlas como pagadas o vencidas, igual que lo haria Stripe. El
webhook se prueba con una firma calculada como la calcula Stripe.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.bookings.models import Booking, InventoryLock, Order
from apps.bookings.services import read_voucher
from apps.catalog.models import TourismProduct
from apps.payments.models import Payment

from .datos import (
    OTRO_TURISTA,
    _hoy,
    _pedido_habitacion,
    _session_id,
    _vencer,
    _webhook,
    cliente,
    habitacion_publicada,
    tour_publicado,
)

pytestmark = pytest.mark.django_db

# --- Cotizacion -----------------------------------------------------------------


def test_cotizar_una_habitacion_calcula_noches_total_y_cupo(stripe):
    room = habitacion_publicada()
    pedido = _pedido_habitacion(room, noches=3, cantidad=1)

    respuesta = cliente().post("/api/v1/me/reservas/cotizacion/", pedido, format="json")

    assert respuesta.status_code == 200, respuesta.json()
    data = respuesta.json()
    assert data["noches"] == 3
    assert Decimal(data["total"]) == room.product.base_price * 3
    assert data["disponibles"] == room.quantity
    assert data["disponible"] is True
    assert data["fecha_fin"] == pedido["fecha_fin"]


def test_cotizar_no_aparta_nada(stripe):
    room = habitacion_publicada()
    cliente().post("/api/v1/me/reservas/cotizacion/", _pedido_habitacion(room), format="json")
    assert not InventoryLock.objects.exists()


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"fecha_inicio": "2000-01-01", "fecha_fin": "2000-01-03"}, "fecha_inicio"),
        ({"fecha_fin": None}, "fecha_fin"),
        ({"huespedes": 99}, "huespedes"),
        ({"cantidad": 999}, "cantidad"),
    ],
)
def test_cotizar_valida_el_pedido(stripe, cambios, campo):
    room = habitacion_publicada()
    pedido = {**_pedido_habitacion(room), **cambios}
    respuesta = cliente().post("/api/v1/me/reservas/cotizacion/", pedido, format="json")
    assert respuesta.status_code == 400
    assert campo in respuesta.json()["error"]["details"]


def test_un_hotel_no_se_reserva_directo_sino_por_sus_habitaciones(stripe):
    hotel = TourismProduct.objects.filter(product_type__code="HOTEL", status="PUBLICADO").first()
    pedido = {"producto_id": hotel.id, "fecha_inicio": (_hoy() + timedelta(days=5)).isoformat(), "cantidad": 1}
    assert cliente().post("/api/v1/me/reservas/cotizacion/", pedido, format="json").status_code == 404


# --- Crear y cupos ---------------------------------------------------------------


def test_reservar_aparta_el_cupo_y_abre_el_pago(stripe):
    room = habitacion_publicada()
    respuesta = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(room, noches=2), format="json")

    assert respuesta.status_code == 201, respuesta.json()
    data = respuesta.json()
    assert data["estado"] == "CREADA"
    assert data["checkout_url"].startswith("https://checkout.stripe.test/")
    assert data["fechas"]["noches"] == 2
    assert data["qr"] is None
    assert data["vence_en"] is not None

    booking = Booking.objects.get(id=data["id"])
    assert booking.details.count() == 2
    assert InventoryLock.objects.filter(booking=booking, status="ACTIVO").count() == 2
    payment = Payment.objects.get(booking=booking)
    assert payment.status == "PENDIENTE"
    assert payment.amount == room.product.base_price * 2
    # El subtotal lo calcula PostgreSQL con la columna generada.
    assert sum(detail.subtotal for detail in booking.details.all()) == payment.amount
    # A Stripe le llega el total en la moneda del producto y vuelve con el codigo.
    enviado = stripe.created[0]
    assert enviado["amount"] == payment.amount
    assert enviado["currency"] == "BOB"
    assert booking.code in enviado["success_url"]


def test_no_se_vende_mas_de_lo_que_hay(stripe):
    room = habitacion_publicada()
    todas = _pedido_habitacion(room, cantidad=room.quantity, huespedes=room.quantity)
    assert cliente().post("/api/v1/me/reservas/", todas, format="json").status_code == 201

    otra = cliente(OTRO_TURISTA).post("/api/v1/me/reservas/", _pedido_habitacion(room), format="json")
    assert otra.status_code == 409
    assert "No quedan cupos" in otra.json()["error"]["message"]

    cotizacion = cliente(OTRO_TURISTA).post(
        "/api/v1/me/reservas/cotizacion/", _pedido_habitacion(room), format="json"
    ).json()
    assert cotizacion["disponibles"] == 0
    assert cotizacion["disponible"] is False


def test_un_bloqueo_vencido_devuelve_el_cupo(stripe):
    room = habitacion_publicada()
    todas = _pedido_habitacion(room, cantidad=room.quantity, huespedes=room.quantity)
    primera = cliente().post("/api/v1/me/reservas/", todas, format="json").json()

    _vencer(primera["id"])

    segunda = cliente(OTRO_TURISTA).post("/api/v1/me/reservas/", _pedido_habitacion(room), format="json")
    assert segunda.status_code == 201

    vencida = cliente().get(f"/api/v1/me/reservas/{primera['id']}/").json()
    assert vencida["estado"] == "EXPIRADA_LIBERADA"
    assert Payment.objects.get(booking_id=primera["id"]).status == "ANULADO"


def test_un_tour_se_reserva_por_personas_en_un_dia(stripe):
    tour = tour_publicado()
    pedido = {"producto_id": tour.id, "fecha_inicio": (_hoy() + timedelta(days=3)).isoformat(), "cantidad": 2}
    data = cliente().post("/api/v1/me/reservas/", pedido, format="json").json()

    assert data["fechas"] == {"inicio": pedido["fecha_inicio"], "fin": pedido["fecha_inicio"], "noches": None}
    assert data["importe"]["unidad"] == "personas"
    assert Decimal(data["importe"]["total"]) == tour.base_price * 2
    assert data["huespedes"] is None


def test_la_misma_clave_de_idempotencia_no_reserva_dos_veces(stripe):
    room = habitacion_publicada()
    api = cliente()
    pedido = _pedido_habitacion(room)
    primera = api.post("/api/v1/me/reservas/", pedido, format="json", HTTP_IDEMPOTENCY_KEY="toque-1").json()
    segunda = api.post("/api/v1/me/reservas/", pedido, format="json", HTTP_IDEMPOTENCY_KEY="toque-1").json()

    assert primera["id"] == segunda["id"]
    assert Booking.objects.count() == 1
    assert len(stripe.created) == 1


def test_si_stripe_falla_no_queda_cupo_tomado(stripe):
    stripe.fail = True
    room = habitacion_publicada()
    respuesta = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(room), format="json")

    assert respuesta.status_code == 503
    booking = Booking.objects.get()
    assert booking.status == "CANCELADA"
    assert not InventoryLock.objects.filter(status="ACTIVO").exists()


def test_sin_stripe_configurado_no_se_reserva(stripe, settings):
    settings.STRIPE_SECRET_KEY = ""
    room = habitacion_publicada()
    respuesta = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(room), format="json")
    assert respuesta.status_code == 503
    assert not Booking.objects.exists()


# --- Pago --------------------------------------------------------------------------


def test_el_webhook_confirma_la_reserva_y_genera_el_voucher(stripe):
    room = habitacion_publicada()
    creada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(room), format="json").json()
    session_id = _session_id(creada["id"])

    assert _webhook("checkout.session.completed", session_id).status_code == 200
    # Stripe reintenta: el segundo aviso no cambia nada.
    assert _webhook("checkout.session.completed", session_id).status_code == 200

    data = cliente().get(f"/api/v1/me/reservas/{creada['id']}/").json()
    assert data["estado"] == "CONFIRMADA"
    assert data["pago"]["estado"] == "APROBADO"
    assert read_voucher(data["qr"]) == {"r": creada["id"], "c": creada["codigo"]}
    assert set(InventoryLock.objects.filter(booking_id=creada["id"]).values_list("status", flat=True)) == {
        "CONSUMIDO"
    }
    assert Order.objects.get(bookings__id=creada["id"]).status == "CONFIRMADA"
    booking = Booking.objects.get(id=creada["id"])
    assert list(booking.history.order_by("id").values_list("new_status", flat=True)) == ["CREADA", "CONFIRMADA"]


def test_una_reserva_pagada_sigue_ocupando_el_cupo(stripe):
    room = habitacion_publicada()
    todas = _pedido_habitacion(room, cantidad=room.quantity, huespedes=room.quantity)
    creada = cliente().post("/api/v1/me/reservas/", todas, format="json").json()
    _webhook("checkout.session.completed", _session_id(creada["id"]))

    otra = cliente(OTRO_TURISTA).post("/api/v1/me/reservas/", _pedido_habitacion(room), format="json")
    assert otra.status_code == 409


def test_un_webhook_con_firma_falsa_se_rechaza(stripe):
    room = habitacion_publicada()
    creada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(room), format="json").json()

    respuesta = _webhook("checkout.session.completed", _session_id(creada["id"]), secret="whsec_otro")

    assert respuesta.status_code == 400
    assert Booking.objects.get(id=creada["id"]).status == "CREADA"


def test_el_webhook_de_sesion_vencida_libera_el_cupo(stripe):
    room = habitacion_publicada()
    creada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(room), format="json").json()

    _webhook("checkout.session.expired", _session_id(creada["id"]), payment_status="unpaid")

    assert Booking.objects.get(id=creada["id"]).status == "EXPIRADA_LIBERADA"
    assert not InventoryLock.objects.filter(booking_id=creada["id"], status="ACTIVO").exists()


def test_sin_webhook_la_app_concilia_al_abrir_la_reserva(stripe):
    room = habitacion_publicada()
    creada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(room), format="json").json()
    stripe.pay(_session_id(creada["id"]))

    assert cliente().get(f"/api/v1/me/reservas/{creada['id']}/").json()["estado"] == "CONFIRMADA"


def test_retomar_el_pago_devuelve_el_enlace_abierto(stripe):
    room = habitacion_publicada()
    creada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(room), format="json").json()

    respuesta = cliente().post(f"/api/v1/me/reservas/{creada['id']}/pagar/")

    assert respuesta.status_code == 200
    assert respuesta.json()["checkout_url"] == creada["checkout_url"]


# --- Cancelar y consultar ---------------------------------------------------------


def test_cancelar_antes_de_pagar_libera_el_cupo_y_cierra_la_sesion(stripe):
    room = habitacion_publicada()
    creada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(room), format="json").json()
    session_id = _session_id(creada["id"])

    respuesta = cliente().post(f"/api/v1/me/reservas/{creada['id']}/cancelar/")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "CANCELADA"
    assert stripe.sessions[session_id]["status"] == "expired"
    assert set(InventoryLock.objects.filter(booking_id=creada["id"]).values_list("status", flat=True)) == {
        "LIBERADO"
    }


def test_una_reserva_pagada_no_se_cancela_desde_la_app(stripe):
    room = habitacion_publicada()
    creada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(room), format="json").json()
    _webhook("checkout.session.completed", _session_id(creada["id"]))

    respuesta = cliente().post(f"/api/v1/me/reservas/{creada['id']}/cancelar/")

    assert respuesta.status_code == 400
    assert Booking.objects.get(id=creada["id"]).status == "CONFIRMADA"


def test_mis_viajes_lista_solo_las_reservas_propias(stripe):
    room = habitacion_publicada()
    creada = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(room), format="json").json()

    propias = cliente().get("/api/v1/me/reservas/").json()
    assert [item["id"] for item in propias] == [creada["id"]]
    assert propias[0]["producto"]["hospedaje_id"] == room.establishment_id
    assert cliente(OTRO_TURISTA).get("/api/v1/me/reservas/").json() == []
    assert cliente(OTRO_TURISTA).get(f"/api/v1/me/reservas/{creada['id']}/").status_code == 404


def test_una_reserva_cuyo_servicio_ya_paso_queda_completada(stripe):
    tour = tour_publicado()
    pedido = {"producto_id": tour.id, "fecha_inicio": (_hoy() + timedelta(days=2)).isoformat(), "cantidad": 1}
    creada = cliente().post("/api/v1/me/reservas/", pedido, format="json").json()
    _webhook("checkout.session.completed", _session_id(creada["id"]))

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE disponibilidad SET inicio = inicio - interval '10 days', fin = fin - interval '10 days' "
            "WHERE id IN (SELECT id_disponibilidad FROM reserva_detalle WHERE id_reserva = %s)",
            [creada["id"]],
        )

    assert cliente().get(f"/api/v1/me/reservas/{creada['id']}/").json()["estado"] == "COMPLETADA"


def test_la_pagina_de_retorno_no_confirma_nada(stripe):
    respuesta = APIClient().get("/api/v1/pagos/stripe/retorno/?resultado=exito&reserva=RES-ABC<script>")
    assert respuesta.status_code == 200
    assert "Pago recibido" in respuesta.content.decode()
    assert "<script>" not in respuesta.content.decode()
