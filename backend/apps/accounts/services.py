from datetime import UTC, datetime
from hashlib import sha256

from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import (
    AuthenticationFailed,
    PermissionDenied,
    ValidationError,
)
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.services import record_audit
from apps.rbac.models import Role, UserRole
from apps.rbac.services import is_superadmin, require_permission, require_tenant_access
from apps.tenancy.models import UserTenant

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


def _resolve_tenant_role(role_code: str, tenant_id: int) -> Role:
    role = (
        Role.objects.filter(code=role_code, scope=Role.Scope.TENANT)
        .filter(Q(tenant_id=tenant_id) | Q(tenant__isnull=True))
        .first()
    )
    if role is None:
        raise ValidationError({"role_code": "Rol inválido para esta empresa."})
    return role


def _require_assignable_role(actor, role: Role) -> None:
    if is_superadmin(actor):
        return
    if role.scope != Role.Scope.TENANT or role.code == "TENANT_ADMIN":
        raise PermissionDenied("No puede asignar el rol de propietario.")


def _protect_company_owner(actor, user_id: int, tenant_id: int) -> None:
    if UserRole.objects.filter(
        user_id=user_id,
        tenant_id=tenant_id,
        role__code="TENANT_ADMIN",
        role__scope=Role.Scope.TENANT,
    ).exists():
        raise PermissionDenied("El propietario solo puede modificarse desde la gestión de empresas.")


def _require_company_employee_management(actor) -> None:
    if is_superadmin(actor):
        raise PermissionDenied(
            "El SuperAdministrador administra empresas, no los empleados internos."
        )


def list_tenant_users(*, actor, tenant_id: int):
    _require_company_employee_management(actor)
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "USUARIOS_GESTIONAR", tenant_id)
    user_ids = UserTenant.objects.filter(
        tenant_id=tenant_id, status=UserTenant.Status.ACTIVE
    ).values_list("user_id", flat=True)
    return User.objects.filter(id__in=user_ids)


@transaction.atomic
def create_or_link_tenant_user(
    *,
    actor,
    tenant_id: int,
    email: str,
    first_names: str,
    last_names: str,
    role_code: str,
    phone: str | None = None,
    password: str | None = None,
    request=None,
) -> User:
    _require_company_employee_management(actor)
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "USUARIOS_GESTIONAR", tenant_id)

    role = _resolve_tenant_role(role_code, tenant_id)
    _require_assignable_role(actor, role)

    user = User.objects.filter(email__iexact=email).first()
    created = False
    if user is None:
        if not password or len(password) < 8:
            raise ValidationError({"password": "La contraseña debe tener al menos 8 caracteres."})
        user = User.objects.create_user(
            email=email,
            password=password,
            first_names=first_names,
            last_names=last_names,
            phone=phone,
            status=User.Status.ACTIVE,
        )
        created = True
    else:
        _protect_company_owner(actor, user.id, tenant_id)

    membership, _ = UserTenant.objects.get_or_create(
        user=user, tenant_id=tenant_id, defaults={"status": UserTenant.Status.ACTIVE}
    )
    if membership.status != UserTenant.Status.ACTIVE:
        membership.status = UserTenant.Status.ACTIVE
        membership.save(update_fields=["status"])

    UserRole.objects.filter(user=user, tenant_id=tenant_id).delete()
    UserRole.objects.create(user=user, role=role, tenant_id=tenant_id)

    record_audit(
        actor=actor,
        tenant_id=tenant_id,
        action="CREAR" if created else "VINCULAR",
        entity="usuario",
        entity_id=str(user.id),
        new_data={"email": user.email, "role": role.code},
        request=request,
    )
    return user


@transaction.atomic
def update_tenant_user(
    *,
    actor,
    tenant_id: int,
    user_id: int,
    first_names: str | None = None,
    last_names: str | None = None,
    phone: str | None = None,
    role_code: str | None = None,
    request=None,
) -> User:
    _require_company_employee_management(actor)
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "USUARIOS_GESTIONAR", tenant_id)
    _protect_company_owner(actor, user_id, tenant_id)

    if not UserTenant.objects.filter(
        user_id=user_id, tenant_id=tenant_id, status=UserTenant.Status.ACTIVE
    ).exists():
        raise ValidationError({"user": "El usuario no pertenece a esta empresa."})

    user = User.objects.get(pk=user_id)
    fields = []
    if first_names is not None:
        user.first_names = first_names
        fields.append("first_names")
    if last_names is not None:
        user.last_names = last_names
        fields.append("last_names")
    if phone is not None:
        user.phone = phone
        fields.append("phone")
    if fields:
        user.save(update_fields=fields)

    if role_code:
        role = _resolve_tenant_role(role_code, tenant_id)
        _require_assignable_role(actor, role)
        UserRole.objects.filter(user=user, tenant_id=tenant_id).delete()
        UserRole.objects.get_or_create(user=user, role=role, tenant_id=tenant_id)

    record_audit(
        actor=actor,
        tenant_id=tenant_id,
        action="ACTUALIZAR",
        entity="usuario",
        entity_id=str(user.id),
        new_data={"role": role_code} if role_code else None,
        request=request,
    )
    return user


@transaction.atomic
def remove_tenant_user(*, actor, tenant_id: int, user_id: int, request=None) -> None:
    _require_company_employee_management(actor)
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "USUARIOS_GESTIONAR", tenant_id)
    _protect_company_owner(actor, user_id, tenant_id)
    updated = UserTenant.objects.filter(user_id=user_id, tenant_id=tenant_id).update(
        status=UserTenant.Status.INACTIVE
    )
    if not updated:
        raise ValidationError({"user": "El usuario no pertenece a esta empresa."})
    UserRole.objects.filter(user_id=user_id, tenant_id=tenant_id).delete()
    record_audit(
        actor=actor,
        tenant_id=tenant_id,
        action="DESACTIVAR",
        entity="usuario",
        entity_id=str(user_id),
        request=request,
    )

