from datetime import UTC, datetime
from hashlib import sha256

from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, UserSession


def token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def request_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR")


def token_pair_for_user(user: User, request) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    refresh["email"] = user.email
    raw_refresh = str(refresh)
    expires_at = datetime.fromtimestamp(int(refresh["exp"]), tz=UTC)
    UserSession.objects.create(
        user=user,
        refresh_token_hash=token_hash(raw_refresh),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
        ip=request_ip(request),
        expires_at=expires_at,
    )
    return {"access": str(refresh.access_token), "refresh": raw_refresh}


@transaction.atomic
def login_user(*, email: str, password: str, request) -> tuple[User, dict[str, str]]:
    user = authenticate(request=request, username=email, password=password)
    if user is None:
        raise AuthenticationFailed("Credenciales incorrectas.")
    if not user.is_active:
        raise AuthenticationFailed("La cuenta no se encuentra activa.")
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    return user, token_pair_for_user(user, request)


@transaction.atomic
def rotate_refresh_token(*, raw_refresh: str, request) -> tuple[User, dict[str, str]]:
    try:
        refresh = RefreshToken(raw_refresh)
        user_id = int(refresh["user_id"])
    except Exception as exc:
        raise AuthenticationFailed("Refresh token inválido.") from exc

    session = UserSession.objects.select_for_update().filter(
        refresh_token_hash=token_hash(raw_refresh),
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if session is None or session.user_id != user_id:
        raise AuthenticationFailed("La sesión ya no está activa.")

    user = User.objects.get(pk=user_id)
    if not user.is_active:
        raise AuthenticationFailed("La cuenta no se encuentra activa.")
    session.revoked_at = timezone.now()
    session.save(update_fields=["revoked_at"])
    return user, token_pair_for_user(user, request)


def revoke_refresh_token(raw_refresh: str) -> None:
    UserSession.objects.filter(
        refresh_token_hash=token_hash(raw_refresh), revoked_at__isnull=True
    ).update(revoked_at=timezone.now())

