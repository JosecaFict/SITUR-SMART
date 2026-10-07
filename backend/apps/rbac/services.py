from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record_audit
from apps.tenancy.models import (
    TENANT_BLOCK_REASONS,
    TENANT_OPERATIONAL_STATUS,
    Tenant,
    UserTenant,
)

from .models import Permission, Role, RolePermission, UserRole

FORBIDDEN_TENANT_PERMISSIONS = {
    "TENANTS_LEER",
    "TENANTS_GESTIONAR",
    "SUSCRIPCIONES_GESTIONAR",
    "REPORTES_GLOBALES",
    "CLIENTES_GESTIONAR",
}


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


def require_tenant_membership(user, tenant_id: int) -> None:
    """Comprueba que el usuario pertenezca a la empresa, sin mirar su estado.

    Es la version permisiva, para las lecturas que deben seguir funcionando
    cuando la empresa esta suspendida: justamente las que permiten enterarse de
    que lo esta. Hoy son dos, la ficha de la empresa y su suscripcion.

    Para cualquier otra cosa se usa ``require_tenant_access``, que ademas exige
    que la empresa este operativa. La asimetria es deliberada y el nombre por
    omision es el estricto: si alguien agrega una operacion nueva y olvida
    elegir, falla cerrada.
    """
    if is_superadmin(user):
        return
    if not UserTenant.objects.filter(
        user=user, tenant_id=tenant_id, status=UserTenant.Status.ACTIVE
    ).exists():
        raise PermissionDenied("No tiene acceso al tenant solicitado.")


def require_tenant_access(user, tenant_id: int) -> None:
    """Pertenencia a la empresa **y** empresa operativa.

    Una empresa que no esta ACTIVO no deja de existir: su gente sigue
    autenticandose y viendo su perfil, pero no puede trabajar dentro de ella.
    Suspender tiene que cortar el servicio, no solo esconder la oferta del
    Marketplace.

    El 403 lleva el estado en ``details`` para que la interfaz pueda explicar
    el bloqueo en vez de mostrar un error en crudo. El SUPER_ADMIN pasa, porque
    administrar una empresa suspendida es precisamente parte de su trabajo.
    """
    require_tenant_membership(user, tenant_id)
    if is_superadmin(user):
        return
    status = (
        Tenant.objects.filter(pk=tenant_id).values_list("status", flat=True).first()
    )
    if status is None:
        raise PermissionDenied("No tiene acceso al tenant solicitado.")
    if status != TENANT_OPERATIONAL_STATUS:
        raise PermissionDenied(
            {
                "detail": TENANT_BLOCK_REASONS.get(status, "La empresa no está operativa."),
                "empresa_estado": status,
                "codigo": "EMPRESA_NO_OPERATIVA",
            }
        )


def require_permission(user, code: str, tenant_id: int | None = None) -> None:
    if is_superadmin(user):
        return
    if not has_permission(user, code, tenant_id):
        raise PermissionDenied("No cuenta con el permiso requerido.")


def _tenant_permissions(permission_codes: list[str]) -> list[Permission]:
    unique_codes = list(dict.fromkeys(permission_codes))
    forbidden = sorted(set(unique_codes) & FORBIDDEN_TENANT_PERMISSIONS)
    if forbidden:
        raise ValidationError(
            {"permissions": "Los permisos globales de plataforma no pueden asignarse a una empresa."}
        )
    permissions = list(Permission.objects.filter(code__in=unique_codes))
    if len(permissions) != len(unique_codes):
        raise ValidationError({"permissions": "Uno o más permisos no existen."})
    return permissions


def get_tenant_role(*, actor, tenant_id: int, role_id: int) -> Role:
    require_tenant_access(actor, tenant_id)
    require_permission(actor, "ROLES_GESTIONAR", tenant_id)
    role = (
        Role.objects.filter(id=role_id, scope=Role.Scope.TENANT)
        .filter(Q(tenant_id=tenant_id) | Q(tenant__isnull=True))
        .first()
    )
    if role is None:
        raise ValidationError({"role": "El rol no pertenece a esta empresa."})
    return role


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
    permissions = _tenant_permissions(permission_codes)
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


@transaction.atomic
def update_tenant_role(
    *,
    actor,
    tenant_id: int,
    role_id: int,
    name: str | None = None,
    permission_codes: list[str] | None = None,
    request=None,
) -> Role:
    role = get_tenant_role(actor=actor, tenant_id=tenant_id, role_id=role_id)
    if role.is_system:
        raise PermissionDenied("Los roles del sistema no pueden modificarse.")

    changes = {}
    if name is not None:
        role.name = name
        role.save(update_fields=["name"])
        changes["name"] = name
    if permission_codes is not None:
        permissions = _tenant_permissions(permission_codes)
        RolePermission.objects.filter(role=role).delete()
        RolePermission.objects.bulk_create(
            [RolePermission(role=role, permission=permission) for permission in permissions]
        )
        changes["permissions"] = permission_codes

    record_audit(
        actor=actor,
        tenant_id=tenant_id,
        action="ACTUALIZAR",
        entity="rol",
        entity_id=str(role.id),
        new_data=changes,
        request=request,
    )
    return role


@transaction.atomic
def delete_tenant_role(*, actor, tenant_id: int, role_id: int, request=None) -> None:
    role = get_tenant_role(actor=actor, tenant_id=tenant_id, role_id=role_id)
    if role.is_system:
        raise PermissionDenied("Los roles del sistema no pueden eliminarse.")
    if UserRole.objects.filter(role=role, tenant_id=tenant_id).exists():
        raise ValidationError(
            {"role": "Este rol está asignado a empleados. Reasígnalos antes de eliminarlo."}
        )
    record_audit(
        actor=actor,
        tenant_id=tenant_id,
        action="ELIMINAR",
        entity="rol",
        entity_id=str(role.id),
        previous_data={"code": role.code, "name": role.name},
        request=request,
    )
    role.delete()
