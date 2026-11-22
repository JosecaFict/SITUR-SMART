"""Cola persistente para Brevo, independiente de push y sin correos masivos expuestos."""

import json
import logging
import urllib.error
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import F, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts import brevo
from apps.accounts.models import User

from .email_content import build_email
from .marketing import suppression_reason
from .models import CommunicationEmail

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5


def send_one(row, content, user):
    """Un destinatario por llamada; sin nombres, direcciones o claves en los logs."""
    if not brevo.is_configured():
        return "NOT_CONFIGURED", ""
    payload = {"sender": {"name": settings.BREVO_SENDER_NAME, "email": settings.BREVO_SENDER_EMAIL},
               "to": [{"email": row.recipient_email, "name": user.get_full_name()}],
               "subject": content["subject"], "htmlContent": content["html"], "textContent": content["text"],
               "headers": {"idempotencyKey": str(row.idempotency_key)}, "tags": ["situr-comunicaciones"]}
    req = urllib.request.Request(brevo.BREVO_API_URL, data=json.dumps(payload).encode(), method="POST",
        headers={"api-key": settings.BREVO_API_KEY, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            provider_id = data.get("messageId") if isinstance(data, dict) else None
            if provider_id and isinstance(provider_id, str):
                return None, provider_id[:255]
            return "INVALID_RESPONSE", ""
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 409):
            try:
                reason = json.loads(exc.read().decode()).get("code")
                if reason == "duplicate_parameter":
                    return "PROVIDER_DUPLICATE", ""
            except (ValueError, AttributeError):
                pass
        return f"HTTP_{exc.code}", ""
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return "CONNECTION_ERROR", ""


def process_pending_email(limit=100):
    if transaction.get_connection().in_atomic_block:
        raise RuntimeError("Run email worker outside transaction.atomic()")
    now = timezone.now()
    ready = Q(status="PENDIENTE", next_attempt_at__lte=now) & (Q(locked_until__isnull=True) | Q(locked_until__lte=now))
    ids = list(CommunicationEmail.objects.filter(ready).order_by("next_attempt_at", "pk").values_list("pk", flat=True)[:limit])
    processed = 0
    for pk in ids:
        previous = CommunicationEmail.objects.filter(pk=pk).first()
        if previous is None:
            continue
        if previous.first_attempt_at and timezone.now() - previous.first_attempt_at > timedelta(minutes=29):
            CommunicationEmail.objects.filter(ready, pk=pk, attempts=previous.attempts).update(
                status="REVISION", last_error="PROVIDER_WINDOW_EXPIRED", locked_until=None)
            continue
        lease = timezone.now() + timedelta(minutes=5)
        updates = {"locked_until": lease, "attempts": F("attempts") + 1}
        if brevo.is_configured():
            updates["first_attempt_at"] = Coalesce("first_attempt_at", timezone.now())
        if not CommunicationEmail.objects.filter(ready, pk=pk).update(**updates):
            continue
        processed += 1
        try:
            with transaction.atomic():
                row = CommunicationEmail.objects.select_for_update().select_related("delivery__communication").get(pk=pk, locked_until=lease)
                delivery = row.delivery
                user = User.objects.select_for_update().get(pk=delivery.user_id)
                notification = delivery.notification
                error = suppression_reason(notification) if notification else "INVALID_NOTIFICATION"
                if user.status != User.Status.ACTIVE or user.email.casefold() != row.recipient_email.casefold():
                    error = "RECIPIENT_CHANGED"
                if error:
                    row.status, row.last_error = "OMITIDO", error
                elif row.attempts > MAX_ATTEMPTS:
                    row.status, row.last_error = "FALLIDO", "RETRY_EXHAUSTED"
                else:
                    try:
                        validate_email(row.recipient_email)
                        content = build_email(delivery.communication, notification, user)
                        error, provider_id = send_one(row, content, user)
                    except (ValueError, ValidationError):
                        error, provider_id = "INVALID_EMAIL_OR_URL", ""
                    if error is None:
                        row.status, row.provider_id, row.accepted_at = "ACEPTADO", provider_id, timezone.now()
                        row.last_error = ""
                    else:
                        row.last_error = error
                        permanent = error in ("HTTP_400", "HTTP_401", "HTTP_403", "HTTP_404", "HTTP_422", "INVALID_EMAIL_OR_URL", "INVALID_RESPONSE")
                        row.status = "REVISION" if error == "PROVIDER_DUPLICATE" else "FALLIDO" if permanent or row.attempts >= MAX_ATTEMPTS else "PENDIENTE"
                        row.next_attempt_at = timezone.now() + timedelta(seconds=30 * 2 ** min(row.attempts - 1, 6))
                row.locked_until = None
                row.save(update_fields=("status", "last_error", "provider_id", "accepted_at", "next_attempt_at", "locked_until"))
        except Exception:
            # Keep the lease after an interruption. No exception payloads containing provider data.
            logger.error("Communication email interrupted for job %s", pk)
    return processed
