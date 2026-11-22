"""Persistent, per-device push delivery for communications.

Publication must create Notification and CommunicationDelivery in the same DB
transaction, without calling services.notify/push_notification. Only this worker
calls FCM. process_pending_push() must run outside a caller's atomic block.

locked_until is both a renewable lease and a CAS fencing value. Workers claim
one delivery at a time; every mutation checks ownership. During each individual
FCM call the delivery and device are write/row locked, so account transfers
cannot race the final ownership check. A crash after FCM accepts and before the
DB commit can still cause a duplicate: FCM has no transactional idempotency key.
The attempt budget is reserved in a separate commit to keep even crashes bounded.

Tokens live only in PushAttempt snapshots and FCM messages, never in results,
logs, Notification.data or last_error. ACEPTADO means provider acceptance,
not that a person has seen the notification.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from . import marketing, models, push

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
RETRY_BASE_SECONDS = 30
RETRY_MAX_SECONDS = 3600
LEASE_SECONDS = 300
DEVICES_PER_PASS = 20

# Never persist arbitrary provider responses/exception text: they may echo tokens.
SAFE_ERRORS = frozenset({
    "UNREGISTERED", "SENDER_ID_MISMATCH", "INVALID_ARGUMENT", "UNAVAILABLE",
    "INTERNAL", "QUOTA_EXCEEDED", "RESOURCE_EXHAUSTED", "PERMISSION_DENIED",
    "UNAUTHENTICATED", "THIRD_PARTY_AUTH_ERROR", "NOT_FOUND", "DEADLINE_EXCEEDED",
    "400", "401", "403", "404", "429", "500", "502", "503", "504",
})


def retry_delay(attempts: int) -> timedelta:
    """30, 60, 120, 240... seconds, capped at one hour."""
    exponent = min(max(attempts - 1, 0), 7)
    return timedelta(seconds=min(RETRY_BASE_SECONDS * 2**exponent, RETRY_MAX_SECONDS))


def _ready(now):
    return models.CommunicationDelivery.objects.filter(
        Q(locked_until__isnull=True) | Q(locked_until__lte=now),
        push_status="PENDIENTE", next_attempt_at__lte=now,
    )


def _claim(delivery_id):
    now = timezone.now()
    lease = now + timedelta(seconds=LEASE_SECONDS)
    # A single conditional UPDATE is atomic even on SQLite (no skip_locked needed).
    changed = _ready(now).filter(pk=delivery_id).update(
        locked_until=lease, attempts=F("attempts") + 1,
    )
    return lease if changed else None


def _renew(delivery_id, lease):
    """Call inside atomic: the UPDATE also locks the delivery until commit."""
    now = timezone.now()
    renewed = now + timedelta(seconds=LEASE_SECONDS)
    changed = models.CommunicationDelivery.objects.filter(
        pk=delivery_id, push_status="PENDIENTE", locked_until=lease,
        locked_until__gt=now,
    ).update(locked_until=renewed)
    return renewed if changed else None


def _initialize(delivery_id, lease):
    with transaction.atomic():
        lease = _renew(delivery_id, lease)
        if lease is None:
            return None, None
        delivery = models.CommunicationDelivery.objects.select_related("notification").get(
            pk=delivery_id,
        )
        notification = delivery.notification
        if notification is None or notification.user_id != delivery.user_id:
            models.CommunicationDelivery.objects.filter(pk=delivery_id, locked_until=lease).update(
                push_status="FALLIDO", locked_until=None, last_error="INVALID_NOTIFICATION",
            )
            return None, None
        if _suppress(delivery, lease):
            return None, None
        if not models.PushAttempt.objects.filter(delivery_id=delivery_id).exists():
            devices = models.PushDevice.objects.filter(user_id=delivery.user_id).values_list(
                "id", "token",
            )
            models.PushAttempt.objects.bulk_create([
                models.PushAttempt(delivery_id=delivery_id, device_id=device_id, token=token,
                                   status="PENDIENTE", attempts=0, next_attempt_at=timezone.now())
                for device_id, token in devices
            ], batch_size=500)
        return delivery, lease


def _suppress(delivery, lease):
    notification = delivery.notification
    if (notification.data or {}).get("tipo_comunicacion") == "PROMOCIONAL":
        from apps.accounts.models import User
        User.objects.select_for_update().get(pk=delivery.user_id)
    reason = marketing.suppression_reason(notification)
    if reason:
        models.CommunicationDelivery.objects.filter(pk=delivery.pk, locked_until=lease).update(
            push_status=reason, last_error=reason, locked_until=None)
        models.PushAttempt.objects.filter(delivery_id=delivery.pk, status="PENDIENTE").update(
            status="INVALIDO", last_error=reason)
        return True
    return False


def _reserve(delivery_id, attempt_id, lease):
    """Persist the send budget before touching the network, including crash cases."""
    with transaction.atomic():
        lease = _renew(delivery_id, lease)
        if lease is None:
            return None, False
        attempt = models.PushAttempt.objects.filter(
            pk=attempt_id, delivery_id=delivery_id, status="PENDIENTE",
            next_attempt_at__lte=timezone.now(),
        ).first()
        if attempt is None:
            return lease, False
        if attempt.attempts >= MAX_ATTEMPTS:
            attempt.status = "FALLIDO"
            attempt.last_error = "RETRY_EXHAUSTED"
            attempt.save(update_fields=["status", "last_error"])
            return lease, False
        attempt.attempts += 1
        attempt.save(update_fields=["attempts"])
        return lease, True


def _send(delivery, attempt_id, lease):
    with transaction.atomic():
        lease = _renew(delivery.pk, lease)
        if lease is None:
            return None
        if _suppress(delivery, lease):
            return None
        attempt = models.PushAttempt.objects.get(pk=attempt_id, delivery_id=delivery.pk)
        if attempt.status != "PENDIENTE":
            return lease
        # Lock the current device, not just its snapshot. This serializes token
        # rotations, logouts and transfers to another account against this send.
        device = models.PushDevice.objects.select_for_update().filter(
            pk=attempt.device_id, token=attempt.token, user_id=delivery.user_id,
        ).first()
        if device is None:
            attempt.status = "INVALIDO"
            attempt.last_error = "DEVICE_CHANGED"
            attempt.save(update_fields=["status", "last_error"])
            return lease
        try:
            error = (push.send_one(push.build_message(attempt.token, delivery.notification))
                     if push.is_configured() else "NOT_CONFIGURED")
        except Exception:
            # Provider/auth/build exceptions must not leak credential/token text.
            error = "SEND_EXCEPTION"
        now = timezone.now()
        if error is None:
            attempt.status = "ACEPTADO"
            attempt.last_error = ""
            models.CommunicationDelivery.objects.filter(
                pk=delivery.pk, locked_until=lease, accepted_at__isnull=True,
            ).update(accepted_at=now)
        elif error in push.STALE_TOKEN_ERRORS:
            attempt.status = "INVALIDO"
            attempt.last_error = error
            # An id/token/user triple avoids deleting a rotated or reassigned device.
            models.PushDevice.objects.filter(
                pk=attempt.device_id, token=attempt.token, user_id=delivery.user_id,
            ).delete()
        else:
            attempt.status = "FALLIDO" if attempt.attempts >= MAX_ATTEMPTS else "PENDIENTE"
            attempt.last_error = error if error in SAFE_ERRORS or error in {
                "NOT_CONFIGURED", "SEND_EXCEPTION",
            } else "FCM_ERROR"
            attempt.next_attempt_at = now + retry_delay(attempt.attempts)
        # device may have been SET_NULL by the stale-token cleanup; don't save it.
        attempt.save(update_fields=["status", "last_error", "next_attempt_at"])
        return lease


def _finalize(delivery_id, lease):
    with transaction.atomic():
        lease = _renew(delivery_id, lease)
        if lease is None:
            return
        delivery = models.CommunicationDelivery.objects.get(pk=delivery_id)
        attempts = models.PushAttempt.objects.filter(delivery_id=delivery_id)
        pending = attempts.filter(status="PENDIENTE").order_by("next_attempt_at", "pk").first()
        values = {"locked_until": None}
        if pending is not None:
            values.update(next_attempt_at=pending.next_attempt_at, last_error=pending.last_error)
        elif attempts.filter(status="ACEPTADO").exists():
            values.update(push_status="ACEPTADO", last_error="",
                          accepted_at=delivery.accepted_at or timezone.now())
        elif attempts.exists():
            errors = set(attempts.exclude(last_error="").values_list("last_error", flat=True))
            values.update(push_status="FALLIDO", last_error=(
                errors.pop() if len(errors) == 1 else "ALL_DEVICES_FAILED"
            ))
        elif delivery.attempts >= MAX_ATTEMPTS:
            values.update(push_status="SIN_DISPOSITIVO", last_error="NO_DEVICE")
        else:
            values.update(next_attempt_at=timezone.now() + retry_delay(delivery.attempts),
                          last_error="NO_DEVICE")
        models.CommunicationDelivery.objects.filter(pk=delivery_id, locked_until=lease).update(**values)


def _process(delivery_id, lease):
    delivery, lease = _initialize(delivery_id, lease)
    if delivery is None:
        return
    attempt_ids = list(models.PushAttempt.objects.filter(
        delivery_id=delivery_id, status="PENDIENTE", next_attempt_at__lte=timezone.now(),
    ).order_by("next_attempt_at", "pk").values_list("pk", flat=True)[:DEVICES_PER_PASS])
    for attempt_id in attempt_ids:
        lease, reserved = _reserve(delivery_id, attempt_id, lease)
        if lease is None:
            return
        if reserved:
            lease = _send(delivery, attempt_id, lease)
            if lease is None:
                return
    _finalize(delivery_id, lease)


def process_pending_push(*, limit: int = 100) -> int:
    """Process at most limit due deliveries; return claims, never tokens.

    New devices are snapshotted only before the first nonempty processing pass.
    Empty recipients get at most five discovery passes. Per-device retries get
    five send reservations each, independently of the delivery's pass counter.
    PENDIENTE remains until every device is terminal; then any acceptance gives
    ACEPTADO, otherwise FALLIDO. accepted_at records the first FCM acceptance.
    """
    if limit < 1:
        raise ValueError("limit must be positive")
    if transaction.get_connection().in_atomic_block:
        raise RuntimeError("Run the push worker outside transaction.atomic()")
    delivery_ids = list(_ready(timezone.now()).order_by(
        "next_attempt_at", "pk",
    ).values_list("pk", flat=True)[:limit])
    processed = 0
    for delivery_id in delivery_ids:
        lease = _claim(delivery_id)
        if lease is None:
            continue
        processed += 1
        try:
            _process(delivery_id, lease)
        except Exception:
            # Leave the lease for crash recovery. Never log DB/provider exceptions
            # which might embed the token snapshot as a query parameter.
            logger.error("Communication push interrupted for delivery %s; lease will expire.",
                         delivery_id)
    return processed
