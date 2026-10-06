"""Comando expirar_reservas (lo que corre el cron de Railway) contra PostgreSQL real."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection

from apps.bookings.models import Booking
from apps.notifications.models import Notification

from .datos import (
    _hoy,
    _pedido_habitacion,
    _session_id,
    _vencer,
    _webhook,
    cliente,
    habitacion_publicada,
    tour_publicado,
)

pytestmark = pytest.mark.django_db(transaction=False)


def _correr(django_capture_on_commit_callbacks) -> str:
    salida = StringIO()
    with django_capture_on_commit_callbacks(execute=True):
        call_command("expirar_reservas", stdout=salida)
    return salida.getvalue()


def _reservar():
    respuesta = cliente().post("/api/v1/me/reservas/", _pedido_habitacion(habitacion_publicada()), format="json")
    return respuesta.json()


def _registrar_celular():
    cliente().post("/api/v1/me/dispositivos/", {"token": "celular"}, format="json")


def test_vence_la_reserva_sin_pagar_y_avisa_por_push(stripe, firebase, django_capture_on_commit_callbacks):
    _registrar_celular()
    vencida = _reservar()
    vigente = _reservar()
    _vencer(vencida["id"])

    salida = _correr(django_capture_on_commit_callbacks)

    assert "Reservas conciliadas: 1" in salida
    assert Booking.objects.get(id=vencida["id"]).status == "EXPIRADA_LIBERADA"
    assert Booking.objects.get(id=vigente["id"]).status == "CREADA"
    assert Notification.objects.get().kind == "RESERVA_VENCIDA"
    [mensaje] = firebase.enviados
    assert mensaje["data"]["reserva_id"] == str(vencida["id"])


def test_si_stripe_alcanzo_a_cobrar_la_confirma_en_vez_de_vencerla(stripe, firebase, django_capture_on_commit_callbacks):
    creada = _reservar()
    _vencer(creada["id"])
    stripe.pay(_session_id(creada["id"]))

    _correr(django_capture_on_commit_callbacks)

    assert Booking.objects.get(id=creada["id"]).status == "CONFIRMADA"
    assert Notification.objects.get().kind == "RESERVA_CONFIRMADA"


def test_completa_las_reservas_cuyo_servicio_ya_paso(stripe, firebase, django_capture_on_commit_callbacks):
    pedido = {"producto_id": tour_publicado().id, "fecha_inicio": (_hoy() + timedelta(days=2)).isoformat(), "cantidad": 1}
    pasada = cliente().post("/api/v1/me/reservas/", pedido, format="json").json()
    _webhook("checkout.session.completed", _session_id(pasada["id"]))
    otro_dia = {**pedido, "fecha_inicio": (_hoy() + timedelta(days=3)).isoformat()}
    futura = cliente().post("/api/v1/me/reservas/", otro_dia, format="json").json()
    _webhook("checkout.session.completed", _session_id(futura["id"]))
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE disponibilidad SET inicio = inicio - interval '10 days', fin = fin - interval '10 days' "
            "WHERE id IN (SELECT id_disponibilidad FROM reserva_detalle WHERE id_reserva = %s)",
            [pasada["id"]],
        )

    salida = _correr(django_capture_on_commit_callbacks)

    assert "Completadas: 1" in salida
    assert Booking.objects.get(id=pasada["id"]).status == "COMPLETADA"
    assert Booking.objects.get(id=futura["id"]).status == "CONFIRMADA"


def test_espera_a_que_salga_el_push_antes_de_terminar(stripe, firebase, settings, django_capture_on_commit_callbacks):
    # Como en Railway: el push va en un hilo aparte. Si el comando no lo
    # esperara, el proceso del cron terminaria antes del envio.
    settings.PUSH_EN_SEGUNDO_PLANO = True
    _registrar_celular()
    creada = _reservar()
    _vencer(creada["id"])

    _correr(django_capture_on_commit_callbacks)

    assert len(firebase.enviados) == 1


def test_sin_nada_que_hacer_no_toca_nada(stripe, django_capture_on_commit_callbacks):
    _reservar()
    salida = _correr(django_capture_on_commit_callbacks)
    assert "Reservas conciliadas: 0. Completadas: 0." in salida
    assert not Notification.objects.exists()
