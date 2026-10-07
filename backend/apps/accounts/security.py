"""Seguridad y autogestion de la cuenta.

* Bloqueo temporal: 5 contrasenas mal seguidas traban la cuenta 15 minutos.
* Correo verificado: un codigo de 6 digitos; sin el, el turista explora pero
  no reserva (``require_verified_email`` lo exige al crear una reserva).
* El turista cambia su contrasena, ve y cierra sus sesiones y puede darse de
  baja: la cuenta se anonimiza y sus reservas y pagos quedan para las empresas.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.html import escape
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ValidationError

from apps.audit.services import record_audit

from .brevo import send_email
from .models import EmailVerification, User, UserSession

MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15
CODE_MINUTES = 15
CODE_MAX_ATTEMPTS = 5
CODE_RESEND_SECONDS = 60
MIN_PASSWORD = 8


class EmailNotVerified(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Verifica tu correo para poder reservar. Te enviamos un código de 6 dígitos."
    default_code = "correo_no_verificado"


def _hash(value: str) -> str:
    from .services import token_hash

    return token_hash(value)


# --- Bloqueo por intentos fallidos ---------------------------------------------------


def locked_message(user: User) -> str | None:
    if user.locked_until and user.locked_until > timezone.now():
        minutes = max(1, int((user.locked_until - timezone.now()).total_seconds() // 60) + 1)
        return f"Demasiados intentos fallidos. Vuelve a intentarlo en {minutes} minutos o recupera tu contraseña."
    return None


def register_failed_login(user: User) -> None:
    """Suma un intento fallido; al quinto traba la cuenta. Fuera de la transaccion del login."""
    User.objects.filter(id=user.id).update(failed_logins=F("failed_logins") + 1)
    user.refresh_from_db(fields=["failed_logins"])
    if user.failed_logins >= MAX_FAILED_LOGINS:
        User.objects.filter(id=user.id).update(
            failed_logins=0, locked_until=timezone.now() + timedelta(minutes=LOCK_MINUTES)
        )
        record_audit(actor=None, action="BLOQUEO_TEMPORAL", entity="usuario", entity_id=str(user.id))


def reset_failed_logins(user: User) -> None:
    if user.failed_logins or user.locked_until:
        User.objects.filter(id=user.id).update(failed_logins=0, locked_until=None)


# --- Verificacion del correo ---------------------------------------------------------


def require_verified_email(user: User) -> None:
    if user.email_verified_at is None:
        raise EmailNotVerified()


def send_verification_code(*, user: User) -> None:
    if user.email_verified_at is not None:
        raise ValidationError({"detail": "Tu correo ya está verificado."})
    recent = EmailVerification.objects.filter(
        user=user, created_at__gt=timezone.now() - timedelta(seconds=CODE_RESEND_SECONDS)
    ).exists()
    if recent:
        raise ValidationError({"detail": "Espera un momento antes de pedir otro código."})
    code = f"{secrets.randbelow(1_000_000):06d}"
    EmailVerification.objects.filter(user=user, used_at__isnull=True).delete()
    EmailVerification.objects.create(
        user=user, code_hash=_hash(code), expires_at=timezone.now() + timedelta(minutes=CODE_MINUTES)
    )
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:520px;color:#0f172a">'
        '<h2 style="color:#0f766e">SITUR-SMART</h2>'
        f"<p>Hola {escape(user.first_names)}, este es tu código para verificar tu correo:</p>"
        f'<p style="font-size:30px;font-weight:800;letter-spacing:6px;color:#0f766e">{code}</p>'
        f"<p style=\"color:#64748b\">Vence en {CODE_MINUTES} minutos. Si no fuiste tú, ignora este correo.</p></div>"
    )
    if not send_email(
        to_email=user.email, to_name=user.get_full_name(), subject=f"Tu código de verificación: {code} - SITUR-SMART", html=html
    ):
        # Sin Brevo (desarrollo local) el codigo queda en el log, como el OTP.
        import logging

        logging.getLogger(__name__).info("[DEV] Código de verificación para %s: %s", user.email, code)


def confirm_email(*, user: User, code: str, request=None) -> User:
    if user.email_verified_at is not None:
        return user
    pending = EmailVerification.objects.filter(user=user, used_at__isnull=True).order_by("-created_at").first()
    if pending is None or pending.expires_at <= timezone.now():
        raise ValidationError({"codigo": "El código venció. Pide uno nuevo."})
    if pending.attempts >= CODE_MAX_ATTEMPTS:
        raise ValidationError({"codigo": "Demasiados intentos con este código. Pide uno nuevo."})
    if pending.code_hash != _hash((code or "").strip()):
        EmailVerification.objects.filter(id=pending.id).update(attempts=F("attempts") + 1)
        raise ValidationError({"codigo": "El código no es correcto."})
    now = timezone.now()
    pending.used_at = now
    pending.save(update_fields=["used_at"])
    user.email_verified_at = now
    user.save(update_fields=["email_verified_at", "updated_at"])
    record_audit(actor=user, action="VERIFICAR_CORREO", entity="usuario", entity_id=str(user.id), request=request)
    return user


# --- Contrasena y sesiones -----------------------------------------------------------


def change_password(*, user: User, current: str, new: str, request) -> dict[str, str]:
    """Cambia la contrasena, cierra todas las sesiones y devuelve una nueva para este dispositivo."""
    from .services import token_pair_for_user

    if not user.check_password(current or ""):
        raise ValidationError({"actual": "La contraseña actual no es correcta."})
    if len(new or "") < MIN_PASSWORD:
        raise ValidationError({"nueva": f"La contraseña nueva debe tener al menos {MIN_PASSWORD} caracteres."})
    if new == current:
        raise ValidationError({"nueva": "La contraseña nueva tiene que ser distinta de la actual."})
    with transaction.atomic():
        user.set_password(new)
        user.save(update_fields=["password", "updated_at"])
        UserSession.objects.filter(user=user, revoked_at__isnull=True).update(revoked_at=timezone.now())
        tokens = token_pair_for_user(user, request)
        record_audit(actor=user, action="CAMBIAR_CONTRASENA", entity="usuario", entity_id=str(user.id), request=request)
    send_email(
        to_email=user.email, to_name=user.get_full_name(), subject="Tu contraseña cambió - SITUR-SMART",
        html=(
            '<div style="font-family:Arial,sans-serif;max-width:520px;color:#0f172a">'
            f'<h2 style="color:#0f766e">SITUR-SMART</h2><p>Hola {escape(user.first_names)}, tu contraseña se cambió y '
            "cerramos tus sesiones en los demás dispositivos.</p><p>Si no fuiste tú, recupera tu contraseña "
            f"enseguida o escríbenos a {escape(settings.SOPORTE_EMAIL)}.</p></div>"
        ),
    )
    return tokens


def active_sessions(*, user: User, current_refresh: str | None = None) -> list[dict]:
    current_hash = _hash(current_refresh) if current_refresh else None
    sessions = UserSession.objects.filter(
        user=user, revoked_at__isnull=True, expires_at__gt=timezone.now()
    ).order_by("-created_at")
    return [
        {
            "id": session.id,
            "dispositivo": session.user_agent or "Dispositivo desconocido",
            "ip": session.ip,
            "iniciada_en": session.created_at,
            "actual": session.refresh_token_hash == current_hash,
        }
        for session in sessions
    ]


def close_session(*, user: User, session_id: int) -> None:
    updated = UserSession.objects.filter(user=user, id=session_id, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    if not updated:
        raise NotFound("Sesión no encontrada.")


def close_other_sessions(*, user: User, current_refresh: str) -> int:
    return (
        UserSession.objects.filter(user=user, revoked_at__isnull=True)
        .exclude(refresh_token_hash=_hash(current_refresh or ""))
        .update(revoked_at=timezone.now())
    )


# --- Baja de la cuenta -------------------------------------------------------------


def delete_account(*, user: User, password: str, request=None) -> None:
    """Anonimiza la cuenta del turista. Sus reservas y pagos quedan para las empresas.

    El personal de empresas y el SuperAdmin no se dan de baja aqui: su cuenta
    la administra la empresa o la plataforma.
    """
    from apps.bookings.services import cancel_unpaid_for_customer
    from apps.notifications.models import PushDevice

    if not user.check_password(password or ""):
        raise ValidationError({"password": "La contraseña no es correcta."})
    if user.is_staff or user.tenant_memberships.exists():
        raise ValidationError({"detail": "Las cuentas de empresas o de la plataforma no se eliminan desde aquí."})
    with transaction.atomic():
        cancel_unpaid_for_customer(customer=user, actor=user, reason="El turista eliminó su cuenta.")
        PushDevice.objects.filter(user=user).delete()
        UserSession.objects.filter(user=user, revoked_at__isnull=True).update(revoked_at=timezone.now())
        profile = getattr(user, "customer_profile", None)
        if profile is not None:
            profile.document_type = profile.document_number = profile.birth_date = None
            profile.preferences = {}
            profile.save(update_fields=["document_type", "document_number", "birth_date", "preferences"])
        user.email = f"eliminado-{user.id}@cuentas.situr.invalid"
        user.first_names = "Cuenta"
        user.last_names = "eliminada"
        user.phone = None
        user.status = User.Status.INACTIVE
        user.set_unusable_password()
        user.save()
        record_audit(actor=None, action="ELIMINAR_CUENTA", entity="usuario", entity_id=str(user.id), request=request)
