"""Real SQLite transactions against isolated tables matching the outbox contract.

The existing domain models are unmanaged and their full legacy schema is not
available in SQLite. These small test-only models exercise actual ORM/CAS/lease
and FK behavior without changing production models or requiring PostgreSQL/FCM.
"""

from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, models, transaction
from django.test.utils import isolate_apps
from django.utils import timezone

from apps.notifications import outbox, push
from apps.notifications.management.commands import process_communication_push as command


@pytest.fixture
def queue(django_db_setup, django_db_blocker, monkeypatch):
    clock = [timezone.now()]
    monkeypatch.setattr(outbox.timezone, "now", lambda: clock[0])
    sender = Mock(return_value=None)
    monkeypatch.setattr(push, "is_configured", lambda: True)
    monkeypatch.setattr(push, "send_one", sender)
    with isolate_apps("apps.notifications"), django_db_blocker.unblock():
        class QueueUser(models.Model):
            class Meta:
                app_label = "notifications"
                db_table = "test_outbox_user"

        class QueueCommunication(models.Model):
            class Meta:
                app_label = "notifications"
                db_table = "test_outbox_communication"

        class QueueNotification(models.Model):
            user = models.ForeignKey(QueueUser, on_delete=models.CASCADE)
            kind = models.CharField(max_length=40, default="COMUNICADO")
            title = models.CharField(max_length=150, default="Nuevo comunicado")
            message = models.TextField(default="Contenido")
            data = models.JSONField(default=dict)

            class Meta:
                app_label = "notifications"
                db_table = "test_outbox_notification"

        class QueueDevice(models.Model):
            user = models.ForeignKey(QueueUser, on_delete=models.CASCADE)
            token = models.CharField(max_length=512, unique=True)

            class Meta:
                app_label = "notifications"
                db_table = "test_outbox_device"

        class QueueDelivery(models.Model):
            communication = models.ForeignKey(QueueCommunication, on_delete=models.CASCADE)
            user = models.ForeignKey(QueueUser, on_delete=models.CASCADE)
            notification = models.OneToOneField(QueueNotification, null=True, on_delete=models.SET_NULL)
            push_status = models.CharField(max_length=20, default="PENDIENTE")
            attempts = models.IntegerField(default=0)
            next_attempt_at = models.DateTimeField(default=timezone.now)
            locked_until = models.DateTimeField(null=True)
            last_error = models.CharField(max_length=255, blank=True, default="")
            accepted_at = models.DateTimeField(null=True)

            class Meta:
                app_label = "notifications"
                db_table = "test_outbox_delivery"

        class QueueAttempt(models.Model):
            delivery = models.ForeignKey(QueueDelivery, related_name="push_attempts", on_delete=models.CASCADE)
            device = models.ForeignKey(QueueDevice, null=True, on_delete=models.SET_NULL)
            token = models.TextField()
            status = models.CharField(max_length=20, default="PENDIENTE")
            attempts = models.IntegerField(default=0)
            last_error = models.CharField(max_length=255, blank=True, default="")
            next_attempt_at = models.DateTimeField(default=timezone.now)

            class Meta:
                app_label = "notifications"
                db_table = "test_outbox_attempt"

        table_models = (QueueUser, QueueCommunication, QueueNotification, QueueDevice,
                        QueueDelivery, QueueAttempt)
        with connection.schema_editor() as editor:
            for model in table_models:
                editor.create_model(model)
        monkeypatch.setattr(outbox, "models", SimpleNamespace(
            CommunicationDelivery=QueueDelivery, PushAttempt=QueueAttempt, PushDevice=QueueDevice,
        ))

        def delivery(*, devices=1, notification=True):
            user = QueueUser.objects.create()
            communication = QueueCommunication.objects.create()
            notice = QueueNotification.objects.create(
                user=user, data={"comunicado_id": communication.pk},
            ) if notification else None
            row = QueueDelivery.objects.create(user=user, communication=communication, notification=notice)
            for index in range(devices):
                QueueDevice.objects.create(user=user, token=f"private-token-{user.pk}-{index}")
            return row

        try:
            yield SimpleNamespace(
                delivery=delivery, Delivery=QueueDelivery, Attempt=QueueAttempt,
                Device=QueueDevice, User=QueueUser, sender=sender, clock=clock,
            )
        finally:
            with connection.schema_editor() as editor:
                for model in reversed(table_models):
                    editor.delete_model(model)


def _advance_to_next(queue, delivery):
    delivery.refresh_from_db()
    queue.clock[0] = delivery.next_attempt_at


def test_publication_only_persists_and_worker_sends_each_device(queue):
    delivery = queue.delivery(devices=2)
    assert delivery.push_status == "PENDIENTE"
    assert queue.Attempt.objects.count() == 0
    queue.sender.assert_not_called()

    assert outbox.process_pending_push(limit=1) == 1
    delivery.refresh_from_db()
    assert delivery.push_status == "ACEPTADO"
    assert delivery.locked_until is None
    assert delivery.accepted_at == queue.clock[0]
    assert list(delivery.push_attempts.values_list("status", "attempts")) == [
        ("ACEPTADO", 1), ("ACEPTADO", 1),
    ]
    assert queue.sender.call_count == 2
    for call in queue.sender.call_args_list:
        payload = call.args[0]["message"]
        assert payload["data"]["notificacion_id"] == str(delivery.notification_id)
        assert "token" not in payload["data"]
    assert outbox.process_pending_push() == 0


def test_partial_success_only_retries_failed_device(queue):
    delivery = queue.delivery(devices=2)
    queue.sender.side_effect = [None, "UNAVAILABLE", None]
    assert outbox.process_pending_push() == 1
    delivery.refresh_from_db()
    accepted_at = delivery.accepted_at
    assert delivery.push_status == "PENDIENTE"
    assert accepted_at is not None
    assert outbox.process_pending_push() == 0
    _advance_to_next(queue, delivery)
    assert outbox.process_pending_push() == 1
    delivery.refresh_from_db()
    assert delivery.push_status == "ACEPTADO"
    assert delivery.accepted_at == accepted_at
    assert list(delivery.push_attempts.order_by("pk").values_list("attempts", flat=True)) == [1, 2]
    tokens = [call.args[0]["message"]["token"] for call in queue.sender.call_args_list]
    assert tokens[0] != tokens[1] == tokens[2]


def test_retry_budget_is_five_with_exponential_wait(queue):
    delivery = queue.delivery()
    queue.sender.return_value = "UNAVAILABLE"
    for number in range(1, 6):
        before = queue.clock[0]
        assert outbox.process_pending_push() == 1
        delivery.refresh_from_db()
        attempt = delivery.push_attempts.get()
        assert attempt.attempts == number
        if number < 5:
            assert delivery.push_status == attempt.status == "PENDIENTE"
            assert delivery.next_attempt_at - before == timedelta(seconds=30 * 2 ** (number - 1))
            assert outbox.process_pending_push() == 0
            _advance_to_next(queue, delivery)
    assert delivery.push_status == attempt.status == "FALLIDO"
    assert queue.sender.call_count == 5
    queue.clock[0] += timedelta(days=1)
    assert outbox.process_pending_push() == 0
    assert outbox.retry_delay(1000) == timedelta(hours=1)


def test_no_devices_stops_after_five_discovery_passes(queue):
    delivery = queue.delivery(devices=0)
    for _ in range(5):
        assert outbox.process_pending_push() == 1
        _advance_to_next(queue, delivery)
    assert delivery.push_status == "SIN_DISPOSITIVO"
    assert delivery.attempts == 5
    assert delivery.locked_until is None
    assert queue.Attempt.objects.count() == 0
    queue.Device.objects.create(user=delivery.user, token="device-registered-too-late")
    queue.clock[0] += timedelta(days=1)
    assert outbox.process_pending_push() == 0
    queue.sender.assert_not_called()


def test_device_registered_before_discovery_deadline_is_used(queue):
    delivery = queue.delivery(devices=0)
    outbox.process_pending_push()
    queue.Device.objects.create(user=delivery.user, token="new-device")
    _advance_to_next(queue, delivery)
    outbox.process_pending_push()
    delivery.refresh_from_db()
    assert delivery.push_status == "ACEPTADO"
    assert queue.sender.call_count == 1


@pytest.mark.parametrize("error", sorted(push.STALE_TOKEN_ERRORS))
def test_stale_token_invalidates_attempt_and_deletes_only_its_device(queue, error):
    delivery = queue.delivery()
    unrelated = queue.delivery()
    unrelated.push_status = "ACEPTADO"
    unrelated.save(update_fields=["push_status"])
    queue.sender.return_value = error
    outbox.process_pending_push()
    delivery.refresh_from_db()
    attempt = delivery.push_attempts.get()
    assert delivery.push_status == "FALLIDO"
    assert attempt.status == "INVALIDO"
    assert attempt.device_id is None
    assert queue.Device.objects.filter(user=unrelated.user).exists()
    assert not queue.Device.objects.filter(user=delivery.user).exists()


@pytest.mark.parametrize("change", ["account", "token", "delete", "replace"])
def test_changed_device_snapshot_is_never_sent(queue, monkeypatch, change):
    delivery = queue.delivery()
    device = queue.Device.objects.get()
    send = outbox._send

    def change_then_send(row, attempt_id, lease):
        if change == "account":
            queue.Device.objects.filter(pk=device.pk).update(user=queue.User.objects.create())
        elif change == "token":
            queue.Device.objects.filter(pk=device.pk).update(token="rotated-token")
        else:
            queue.Device.objects.filter(pk=device.pk).delete()
            if change == "replace":
                queue.Device.objects.create(user=row.user, token=device.token)
        return send(row, attempt_id, lease)

    monkeypatch.setattr(outbox, "_send", change_then_send)
    outbox.process_pending_push()
    queue.sender.assert_not_called()
    attempt = delivery.push_attempts.get()
    assert attempt.status == "INVALIDO"
    assert attempt.last_error == "DEVICE_CHANGED"


@pytest.mark.parametrize("change", ["account", "token"])
def test_stale_response_does_not_delete_changed_registration(queue, change):
    delivery = queue.delivery()
    device = queue.Device.objects.get()

    def stale_after_registration_changes(message):
        if change == "account":
            queue.Device.objects.filter(pk=device.pk).update(user=queue.User.objects.create())
        else:
            queue.Device.objects.filter(pk=device.pk).update(token="new-token")
        return "UNREGISTERED"

    queue.sender.side_effect = stale_after_registration_changes
    outbox.process_pending_push()
    assert queue.Device.objects.filter(pk=device.pk).exists()
    assert delivery.push_attempts.get().status == "INVALIDO"


def test_cas_claim_excludes_second_worker_and_expired_owner_is_fenced(queue):
    delivery = queue.delivery()
    first_lease = outbox._claim(delivery.pk)
    assert first_lease is not None
    assert outbox._claim(delivery.pk) is None
    assert outbox.process_pending_push() == 0
    queue.clock[0] = first_lease + timedelta(seconds=1)
    second_lease = outbox._claim(delivery.pk)
    assert second_lease is not None
    assert second_lease != first_lease
    outbox._process(delivery.pk, first_lease)
    queue.sender.assert_not_called()
    outbox._process(delivery.pk, second_lease)
    delivery.refresh_from_db()
    assert delivery.push_status == "ACEPTADO"
    assert queue.sender.call_count == 1
    assert queue.Attempt.objects.count() == 1


def test_lease_is_refreshed_between_slow_device_sends(queue):
    delivery = queue.delivery(devices=3)

    def slow_send(message):
        # Each send is within the lease, but the full pass takes longer than it.
        queue.clock[0] += timedelta(seconds=outbox.LEASE_SECONDS - 1)

    queue.sender.side_effect = slow_send
    outbox.process_pending_push()
    delivery.refresh_from_db()
    assert delivery.push_status == "ACEPTADO"
    assert queue.sender.call_count == 3


def test_crashed_send_reservations_survive_and_remain_bounded(queue):
    delivery = queue.delivery()
    for _ in range(5):
        lease = outbox._claim(delivery.pk)
        _, lease = outbox._initialize(delivery.pk, lease)
        attempt = delivery.push_attempts.get()
        lease, reserved = outbox._reserve(delivery.pk, attempt.pk, lease)
        assert reserved
        # Simulate process death before network/commit of the result.
        queue.clock[0] = lease + timedelta(seconds=1)
    outbox.process_pending_push()
    delivery.refresh_from_db()
    assert delivery.push_status == "FALLIDO"
    assert delivery.push_attempts.get().attempts == 5
    queue.sender.assert_not_called()


def test_moderate_batch_does_not_snapshot_or_resend_new_devices(queue, monkeypatch):
    monkeypatch.setattr(outbox, "DEVICES_PER_PASS", 2)
    delivery = queue.delivery(devices=3)
    outbox.process_pending_push()
    assert queue.sender.call_count == 2
    delivery.refresh_from_db()
    assert delivery.push_status == "PENDIENTE"
    queue.Device.objects.create(user=delivery.user, token="registered-after-snapshot")
    outbox.process_pending_push()
    delivery.refresh_from_db()
    assert delivery.push_status == "ACEPTADO"
    assert queue.sender.call_count == 3
    assert delivery.push_attempts.count() == 3


@pytest.mark.parametrize("result", ["not-configured", "exception", "unsafe-error"])
def test_configuration_and_provider_errors_are_bounded_and_private(queue, monkeypatch, caplog, result):
    delivery = queue.delivery()
    token = queue.Device.objects.get().token
    if result == "not-configured":
        monkeypatch.setattr(push, "is_configured", lambda: False)
    elif result == "exception":
        queue.sender.side_effect = RuntimeError(f"secret credential and {token}")
    else:
        queue.sender.return_value = f"Firebase echoed {token}"
    for _ in range(5):
        outbox.process_pending_push()
        _advance_to_next(queue, delivery)
    assert delivery.push_status == "FALLIDO"
    attempt = delivery.push_attempts.get()
    assert attempt.attempts == 5
    assert token not in attempt.last_error + delivery.last_error + caplog.text
    assert delivery.notification.data == {"comunicado_id": delivery.communication_id}
    assert queue.sender.call_count == (0 if result == "not-configured" else 5)


def test_missing_or_mismatched_notification_fails_without_network(queue):
    missing = queue.delivery(notification=False)
    mismatched = queue.delivery()
    mismatched.notification.user = queue.User.objects.create()
    mismatched.notification.save(update_fields=["user"])
    assert outbox.process_pending_push() == 2
    for delivery in (missing, mismatched):
        delivery.refresh_from_db()
        assert delivery.push_status == "FALLIDO"
        assert delivery.last_error == "INVALID_NOTIFICATION"
    queue.sender.assert_not_called()


def test_limit_and_future_schedule(queue):
    first = queue.delivery()
    second = queue.delivery()
    future = queue.delivery()
    queue.Delivery.objects.filter(pk=future.pk).update(next_attempt_at=queue.clock[0] + timedelta(days=1))
    assert outbox.process_pending_push(limit=1) == 1
    assert outbox.process_pending_push(limit=1) == 1
    assert outbox.process_pending_push(limit=1) == 0
    first.refresh_from_db()
    second.refresh_from_db()
    future.refresh_from_db()
    assert first.push_status == second.push_status == "ACEPTADO"
    assert future.push_status == "PENDIENTE"


def test_worker_rejects_outer_transaction_and_invalid_limit(queue):
    with pytest.raises(ValueError, match="positive"):
        outbox.process_pending_push(limit=0)
    with transaction.atomic(), pytest.raises(RuntimeError, match="outside"):
        outbox.process_pending_push()


def test_processing_exception_keeps_lease_and_continues_other_deliveries(queue, monkeypatch, caplog):
    first = queue.delivery()
    second = queue.delivery()
    process = outbox._process

    def crash_first(delivery_id, lease):
        if delivery_id == first.pk:
            raise RuntimeError("private-token-from-a-database-error")
        return process(delivery_id, lease)

    monkeypatch.setattr(outbox, "_process", crash_first)
    assert outbox.process_pending_push() == 2
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.push_status == "PENDIENTE"
    assert first.locked_until is not None
    assert second.push_status == "ACEPTADO"
    assert "private-token" not in caplog.text


def test_once_command_processes_real_queue_without_sleep(queue, monkeypatch):
    delivery = queue.delivery()
    sleeper = Mock()
    monkeypatch.setattr(command.time, "sleep", sleeper)
    output = StringIO()
    call_command("process_communication_push", "--once", "--limit", "1", stdout=output)
    delivery.refresh_from_db()
    assert delivery.push_status == "ACEPTADO"
    assert output.getvalue() == "Entregas procesadas: 1.\n"
    sleeper.assert_not_called()


def test_continuous_command_polls_then_stops_cleanly(monkeypatch):
    processor = Mock(return_value=0)
    scheduler = Mock(return_value=0)
    sleeper = Mock(side_effect=KeyboardInterrupt)
    monkeypatch.setattr(command, "process_pending_push", processor)
    monkeypatch.setattr(command, "process_due_campaigns", scheduler)
    email_processor = Mock(return_value=0)
    monkeypatch.setattr(command, "process_pending_email", email_processor)
    monkeypatch.setattr(command.time, "sleep", sleeper)
    monkeypatch.setattr(command, "close_old_connections", Mock())
    output = StringIO()
    call_command("process_communication_push", "--limit", "7", "--poll-seconds", "2", stdout=output)
    processor.assert_called_once_with(limit=7)
    scheduler.assert_called_once_with(limit=7)
    email_processor.assert_called_once_with(limit=7)
    sleeper.assert_called_once_with(2)
    assert "detenido" in output.getvalue()


@pytest.mark.parametrize("arguments", [
    ["--limit", "0"], ["--limit", "1001"], ["--poll-seconds", "0"],
    ["--poll-seconds", "61"], ["--poll-seconds", "nan"], ["--poll-seconds", "inf"],
])
def test_command_rejects_invalid_bounds(arguments):
    with pytest.raises(CommandError):
        call_command("process_communication_push", *arguments)


@pytest.mark.parametrize("scenario", ["accepted", "stale", "not-configured", "no-device"])
def test_worker_with_actual_managed_models_and_legacy_tables(
    django_db_setup, django_db_blocker, monkeypatch, scenario,
):
    """Check the real model contract, including FK SET_NULL and the API counter."""
    from apps.accounts.models import CustomerProfile, User
    from apps.bookings.models import Booking, Order
    from apps.catalog.models import Currency
    from apps.notifications import communications
    from apps.notifications import models as actual
    from apps.tenancy.models import Tenant

    clock = [timezone.now()]
    monkeypatch.setattr(timezone, "now", lambda: clock[0])
    monkeypatch.setattr(push, "is_configured", lambda: scenario != "not-configured")
    sender = Mock(return_value="UNREGISTERED" if scenario == "stale" else None)
    monkeypatch.setattr(push, "send_one", sender)
    roots = (User, Tenant, CustomerProfile, Currency, Order, Booking,
             actual.Notification, actual.PushDevice, actual.Communication,
             actual.CommunicationDelivery, actual.PushAttempt)
    with django_db_blocker.unblock():
        existing = set(connection.introspection.table_names())
        created = []
        rows = []
        delivery = None
        try:
            with connection.schema_editor() as editor:
                for model in roots:
                    if model._meta.db_table not in existing:
                        editor.create_model(model)
                        created.append(model)
            user = User.objects.create(
                email="outbox-real-contract@example.test", first_names="Test",
                last_names="Outbox", status=User.Status.ACTIVE, password="unused",
            )
            rows.append(user)
            item = actual.Communication.objects.create(
                author=user, title="Prueba real", message="Contenido persistido",
                kind=actual.Communication.Kind.OPERATIONAL,
                state=actual.Communication.State.PUBLISHED,
            )
            rows.append(item)
            notice = actual.Notification.objects.create(
                user=user, kind="COMUNICACION", title=item.title, message=item.message,
                data={"comunicacion_id": item.pk, "ruta": "/viajero/notificaciones"},
            )
            rows.append(notice)
            if scenario != "no-device":
                device = actual.PushDevice.objects.create(user=user, token="real-model-private-token")
                rows.append(device)
            delivery = actual.CommunicationDelivery.objects.create(
                communication=item, user=user, notification=notice, next_attempt_at=clock[0],
            )
            rows.append(delivery)
            assert outbox.process_pending_push() == 1
            delivery.refresh_from_db()
            if scenario == "not-configured":
                assert delivery.push_status == "PENDIENTE"
                assert delivery.push_attempts.get().last_error == "NOT_CONFIGURED"
                for _ in range(4):
                    clock[0] = delivery.next_attempt_at
                    outbox.process_pending_push()
                    delivery.refresh_from_db()
                assert delivery.push_status == "FALLIDO"
                assert delivery.last_error == "NOT_CONFIGURED"
                assert delivery.push_attempts.get().attempts == 5
                sender.assert_not_called()
            elif scenario == "no-device":
                assert delivery.push_status == "PENDIENTE"
                assert delivery.last_error == "NO_DEVICE"
                for _ in range(4):
                    clock[0] = delivery.next_attempt_at
                    outbox.process_pending_push()
                    delivery.refresh_from_db()
                assert delivery.push_status == "SIN_DISPOSITIVO"
                assert delivery.attempts == 5
                assert delivery.push_attempts.count() == 0
                sender.assert_not_called()
            elif scenario == "stale":
                assert delivery.push_status == "FALLIDO"
                attempt = delivery.push_attempts.get()
                assert attempt.status == "INVALIDO"
                assert attempt.device_id is None
                assert not actual.PushDevice.objects.filter(pk=device.pk).exists()
            else:
                assert delivery.push_status == "ACEPTADO"
                sender.assert_called_once()
                data = sender.call_args.args[0]["message"]["data"]
                assert data["ruta"] == "/viajero/notificaciones"
                assert data["comunicacion_id"] == str(item.pk)
            stats = communications.as_dict(item)
            assert stats["push_aceptados"] == int(scenario == "accepted")
            assert stats["push_fallidos"] == int(scenario in {"stale", "not-configured"})
            assert stats["sin_dispositivo"] == int(scenario == "no-device")
            assert stats["push_pendientes"] == 0
            assert "real-model-private-token" not in str(stats)
        finally:
            if delivery is not None:
                actual.PushAttempt.objects.filter(delivery=delivery)._raw_delete("default")
            # Delete only these rows, avoiding unrelated unmanaged reverse tables.
            for row in reversed(rows):
                type(row).objects.filter(pk=row.pk)._raw_delete("default")
            with connection.schema_editor() as editor:
                for model in reversed(created):
                    editor.delete_model(model)
