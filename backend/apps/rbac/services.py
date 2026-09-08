# Guarda la logica mas compleja

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record_audit
from apps.tenancy.models import UserTenant

from .models import Permission, Role, RolePermission, UserRole


def is_superadmin(user) -> bool:
    return UserRole.objects.filter(
        user=user, role__code="SUPER_ADMIN", role__scope=Role.Scope.GLOBAL, tenant__isnull=True
    ).exists()


def has_permission(user, code: str, tenant_id: int | None = None) -> bool:
    assignments = UserRole.objects.filter(
        user=user, role__role_permissions__permission__code=code
    )
    if tenant_id is None:
        return assignments.filter(tenant__isnull=True).exists()
    return assignments.filter(tenant_id=tenant_id).exists() or assignments.filter(
        tenant__isnull=True, role__scope=Role.Scope.GLOBAL
    ).exists()


def require_tenant_access(user, tenant_id: int) -> None:
    if is_superadmin(user):
        return
    if not UserTenant.objects.filter(
        user=user, tenant_id=tenant_id, status=UserTenant.Status.ACTIVE
    ).exists():
        raise PermissionDenied("No tiene acceso al tenant solicitado.")


def require_permission(user, code: str, tenant_id: int | None = None) -> None:
    if is_superadmin(user):
        return
    if not has_permission(user, code, tenant_id):
        raise PermissionDenied("No cuenta con el permiso requerido.")


@transaction.atomic
def create_tenant_role(*, actor, tenant_id: int, code: str, name: str, permission_codes: list[str], request=None) -> Role:
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "ROLES_GESTIONAR", tenant_id)
    if Role.objects.filter(tenant_id=tenant_id, code__iexact=code).exists():
        raise ValidationError({"code": "Ya existe un rol con ese código en la empresa."})

    role = Role.objects.create(
        tenant_id=tenant_id,
        code=code.upper(),
        name=name,
        scope=Role.Scope.TENANT,
        is_system=False,
    )
    permissions = list(Permission.objects.filter(code__in=permission_codes))
    if len(permissions) != len(set(permission_codes)):
        raise ValidationError({"permissions": "Uno o más permisos no existen."})
    RolePermission.objects.bulk_create(
        [RolePermission(role=role, permission=permission) for permission in permissions]
    )
    record_audit(
        actor=actor,
        tenant_id=tenant_id,
        action="CREAR",
        entity="rol",
        entity_id=str(role.id),
        new_data={"code": role.code, "name": role.name, "permissions": permission_codes},
        request=request,
    )
    return role
