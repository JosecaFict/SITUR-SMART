"""Outbox sobre PostgreSQL real y seed_bolivia; Firebase usa la fixture falsa.

El worker reserva intentos mediante commits propios y rechaza un atomic externo.
Por eso no se usa django_db(transaction=False), ni transaction=True (su flush
borraría el seed compartido): se habilita acceso en autocommit y se eliminan
exclusivamente las filas creadas por cada prueba.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from django.db import connection, connections, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.notifications import communications, outbox, push
from apps.notifications.models import (
    Communication,
    CommunicationDelivery,
    CommunicationEmail,
    Notification,
    PushAttempt,
    PushDevice,
)

from .datos import OTRO_TURISTA, TURISTA

pytestmark = pytest.mark.skipif(connection.vendor != "postgresql", reason="Requiere PostgreSQL real")


@pytest.fixture
def cola_pg(django_db_setup, django_db_blocker, firebase, monkeypatch):
    clock = [timezone.now()]
    monkeypatch.setattr(timezone, "now", lambda: clock[0])
    communication_ids, notification_ids, device_ids = [], [], []
    with django_db_blocker.unblock():
        assert connection.get_autocommit()
        assert not connection.in_atomic_block
        user = User.objects.get(email=TURISTA)
        other = User.objects.get(email=OTRO_TURISTA)

        def device(*, owner=None):
            row = PushDevice.objects.create(
                user=owner or user, token=f"outbox-pg-{uuid4().hex}",
                platform=PushDevice.Platform.ANDROID,
            )
            device_ids.append(row.pk)
            return row

        def delivery(*, status="PENDIENTE"):
            with transaction.atomic():
                item = Communication.objects.create(
                    author=user, title="Prueba de outbox PG", message="Contenido persistente",
                    kind=Communication.Kind.OPERATIONAL, state=Communication.State.PUBLISHED,
                    sender_name="SITUR-SMART", published_at=clock[0],
                )
                notice = Notification.objects.create(
                    user=user, kind="COMUNICACION", title=item.title, message=item.message,
                    data={"comunicacion_id": item.pk, "ruta": "/viajero/notificaciones"},
                )
                row = CommunicationDelivery.objects.create(
                    communication=item, user=user, notification=notice, push_status=status,
                    next_attempt_at=clock[0] - timedelta(days=1),
                )
            communication_ids.append(item.pk)
            notification_ids.append(notice.pk)
            return row

        try:
            yield SimpleNamespace(
                user=user, other=other, device=device, delivery=delivery,
                clock=clock, firebase=firebase,
            )
        finally:
            # No flush, no seed edits, no dependency on another agent's test file.
            Communication.objects.filter(pk__in=communication_ids).delete()
            Notification.objects.filter(pk__in=notification_ids).delete()
            PushDevice.objects.filter(pk__in=device_ids).delete()


def _process(delivery):
    assert outbox.process_pending_push(limit=1) == 1
    delivery.refresh_from_db()


def _advance(cola_pg, delivery):
    cola_pg.clock[0] = delivery.next_attempt_at


def test_worker_persiste_intentos_reales_y_envia_solo_dispositivos_del_destinatario(cola_pg):
    delivery = cola_pg.delivery()
    own = [cola_pg.device(), cola_pg.device()]
    unrelated = cola_pg.device(owner=cola_pg.other)
    assert Notification._meta.managed is False
    assert CommunicationDelivery._meta.managed is True
    assert PushAttempt._meta.managed is True
    assert not delivery.push_attempts.exists()
    assert cola_pg.firebase.enviados == []

    _process(delivery)

    attempts = list(delivery.push_attempts.order_by("device_id"))
    assert [(row.device_id, row.token, row.status, row.attempts) for row in attempts] == [
        (device.pk, device.token, "ACEPTADO", 1) for device in own
    ]
    assert delivery.push_status == "ACEPTADO"
    assert delivery.accepted_at == cola_pg.clock[0]
    assert delivery.locked_until is None
    notice = Notification.objects.get(pk=delivery.notification_id)
    assert notice.user_id == delivery.user_id == cola_pg.user.pk
    assert {message["token"] for message in cola_pg.firebase.enviados} == {device.token for device in own}
    for message in cola_pg.firebase.enviados:
        assert message["data"]["notificacion_id"] == str(notice.pk)
        assert message["data"]["comunicacion_id"] == str(delivery.communication_id)
        assert "token" not in message["data"]
    assert PushDevice.objects.filter(pk=unrelated.pk, user=cola_pg.other).exists()
    stats = communications.as_dict(delivery.communication)
    assert stats["push_aceptados"] == 1
    assert stats["push_pendientes"] == stats["push_fallidos"] == 0
    assert all(device.token not in str(stats) for device in own)
    _advance(cola_pg, delivery)
    assert outbox._claim(delivery.pk) is None


def test_reintento_no_reenvia_al_dispositivo_que_ya_acepto(cola_pg):
    delivery = cola_pg.delivery()
    accepted, retry = cola_pg.device(), cola_pg.device()
    cola_pg.firebase.rechazos[retry.token] = "UNAVAILABLE"

    _process(delivery)
    accepted_at = delivery.accepted_at
    assert delivery.push_status == "PENDIENTE"
    assert delivery.next_attempt_at == cola_pg.clock[0] + timedelta(seconds=30)
    assert delivery.push_attempts.get(device=accepted).status == "ACEPTADO"
    assert outbox._claim(delivery.pk) is None

    del cola_pg.firebase.rechazos[retry.token]
    _advance(cola_pg, delivery)
    _process(delivery)

    assert delivery.push_status == "ACEPTADO"
    assert delivery.accepted_at == accepted_at
    assert delivery.push_attempts.get(device=accepted).attempts == 1
    assert delivery.push_attempts.get(device=retry).attempts == 2
    tokens = [message["token"] for message in cola_pg.firebase.enviados]
    assert tokens.count(accepted.token) == 1
    assert tokens.count(retry.token) == 2


@pytest.mark.parametrize("error", sorted(push.STALE_TOKEN_ERRORS))
def test_token_stale_elimina_dispositivo_y_aplica_set_null_sin_romper_fk(cola_pg, error):
    delivery = cola_pg.delivery()
    stale = cola_pg.device()
    unrelated = cola_pg.device(owner=cola_pg.other)
    previous = cola_pg.delivery(status="ACEPTADO")
    old_attempt = PushAttempt.objects.create(
        delivery=previous, device=stale, token=stale.token, status="ACEPTADO", attempts=1,
    )
    cola_pg.firebase.rechazos[stale.token] = error

    _process(delivery)
    connection.check_constraints()

    attempt = delivery.push_attempts.get()
    assert attempt.status == "INVALIDO"
    assert attempt.last_error == error
    assert attempt.attempts == 1
    assert attempt.device_id is None
    assert attempt.token == stale.token  # Snapshot privado permanece para auditoría.
    assert not PushDevice.objects.filter(pk=stale.pk).exists()
    assert PushDevice.objects.filter(pk=unrelated.pk, token=unrelated.token).exists()
    old_attempt.refresh_from_db()
    assert old_attempt.device_id is None
    assert old_attempt.token == stale.token
    assert old_attempt.status == "ACEPTADO"
    assert delivery.push_status == "FALLIDO"
    assert delivery.last_error == error
    assert delivery.locked_until is None
    assert Notification.objects.filter(pk=delivery.notification_id, user=cola_pg.user).exists()
    assert [message["token"] for message in cola_pg.firebase.enviados] == [stale.token]


def test_token_transferido_de_cuenta_despues_del_snapshot_no_se_envia(cola_pg):
    delivery = cola_pg.delivery()
    device = cola_pg.device()
    lease = outbox._claim(delivery.pk)
    assert lease is not None
    _, lease = outbox._initialize(delivery.pk, lease)
    attempt = delivery.push_attempts.get()
    assert attempt.token == device.token

    PushDevice.objects.filter(pk=device.pk).update(user=cola_pg.other)
    outbox._process(delivery.pk, lease)

    attempt.refresh_from_db()
    delivery.refresh_from_db()
    assert cola_pg.firebase.enviados == []
    assert attempt.status == "INVALIDO"
    assert attempt.last_error == "DEVICE_CHANGED"
    assert delivery.push_status == "FALLIDO"
    assert PushDevice.objects.filter(pk=device.pk, token=device.token, user=cola_pg.other).exists()


def test_dos_conexiones_pg_solo_pueden_reclamar_una_vez_la_entrega(cola_pg):
    delivery = cola_pg.delivery()
    cola_pg.device()
    barrier = Barrier(2)

    def claim():
        try:
            barrier.wait(timeout=5)
            return outbox._claim(delivery.pk)
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim) for _ in range(2)]
        leases = [future.result(timeout=15) for future in futures]
    winners = [lease for lease in leases if lease is not None]
    assert len(winners) == 1
    delivery.refresh_from_db()
    assert delivery.attempts == 1
    assert delivery.locked_until == winners[0]

    outbox._process(delivery.pk, winners[0])
    delivery.refresh_from_db()
    assert delivery.push_status == "ACEPTADO"
    assert delivery.push_attempts.count() == 1
    assert len(cola_pg.firebase.enviados) == 1


def test_sin_credencial_conserva_error_y_falla_al_quinto_intento(cola_pg, monkeypatch):
    delivery = cola_pg.delivery()
    cola_pg.device()
    monkeypatch.setattr(push, "is_configured", lambda: False)

    for number in range(1, 6):
        _process(delivery)
        attempt = delivery.push_attempts.get()
        assert attempt.attempts == number
        assert attempt.last_error == delivery.last_error == "NOT_CONFIGURED"
        assert delivery.push_status == ("PENDIENTE" if number < 5 else "FALLIDO")
        _advance(cola_pg, delivery)

    assert attempt.status == "FALLIDO"
    assert outbox._claim(delivery.pk) is None
    assert cola_pg.firebase.enviados == []


def test_sin_dispositivos_termina_y_se_refleja_en_estadisticas(cola_pg):
    delivery = cola_pg.delivery()
    for number in range(1, 6):
        _process(delivery)
        assert delivery.attempts == number
        assert delivery.last_error == "NO_DEVICE"
        assert delivery.push_status == ("PENDIENTE" if number < 5 else "SIN_DISPOSITIVO")
        _advance(cola_pg, delivery)

    assert not delivery.push_attempts.exists()
    assert outbox._claim(delivery.pk) is None
    assert cola_pg.firebase.enviados == []
    stats = communications.as_dict(delivery.communication)
    assert stats["sin_dispositivo"] == 1
    assert stats["push_pendientes"] == stats["push_aceptados"] == stats["push_fallidos"] == 0


def test_dos_workers_de_correo_pg_solo_envian_una_vez(cola_pg, monkeypatch, settings):
    from apps.notifications import email_outbox
    settings.WEB_APP_URL = "https://web.situr.test"
    delivery = cola_pg.delivery()
    row = CommunicationEmail.objects.create(delivery=delivery, recipient_email=cola_pg.user.email, next_attempt_at=cola_pg.clock[0])
    sender = Mock(return_value=(None, "provider-pg-id"))
    monkeypatch.setattr(email_outbox, "send_one", sender)
    monkeypatch.setattr(email_outbox.brevo, "is_configured", lambda: True)
    barrier = Barrier(2)

    def run():
        try:
            barrier.wait(timeout=5)
            return email_outbox.process_pending_email(limit=1)
        finally:
            connections["default"].close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        processed = [future.result(timeout=15) for future in futures]
    row.refresh_from_db()
    assert sorted(processed) == [0, 1]
    assert row.status == "ACEPTADO"
    assert row.attempts == 1
    assert row.first_attempt_at is not None
    sender.assert_called_once()
    assert communications.as_dict(delivery.communication)["leidas"] == 0


def test_correo_pg_omite_direccion_cambiada_sin_afectar_bandeja(cola_pg, monkeypatch):
    from apps.notifications import email_outbox
    delivery = cola_pg.delivery()
    row = CommunicationEmail.objects.create(delivery=delivery, recipient_email="old-address@situr.test", next_attempt_at=cola_pg.clock[0])
    sender = Mock()
    monkeypatch.setattr(email_outbox, "send_one", sender)
    assert email_outbox.process_pending_email(limit=1) == 1
    row.refresh_from_db()
    assert (row.status, row.last_error) == ("OMITIDO", "RECIPIENT_CHANGED")
    assert Notification.objects.filter(pk=delivery.notification_id).exists()
    sender.assert_not_called()
