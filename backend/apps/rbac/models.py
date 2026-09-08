# Representa las tablas de la base de datos

from django.db import models


class Role(models.Model):
    class Scope(models.TextChoices):
        GLOBAL = "GLOBAL", "Global"
        TENANT = "TENANT", "Tenant"

    id = models.BigAutoField(primary_key=True)
    tenant = models.ForeignKey(
        "tenancy.Tenant", db_column="id_tenant", null=True, blank=True, on_delete=models.DO_NOTHING, related_name="roles"
    )
    code = models.CharField(db_column="codigo", max_length=60)
    name = models.CharField(db_column="nombre", max_length=120)
    scope = models.CharField(db_column="ambito", max_length=20, choices=Scope.choices)
    is_system = models.BooleanField(db_column="es_sistema")

    class Meta:
        managed = False
        db_table = "rol"
        ordering = ("scope", "code")

    def __str__(self) -> str:
        return self.name


class Permission(models.Model):
    id = models.BigAutoField(primary_key=True)
    code = models.CharField(db_column="codigo", max_length=100, unique=True)
    module = models.CharField(db_column="modulo", max_length=80)
    name = models.CharField(db_column="nombre", max_length=150)

    class Meta:
        managed = False
        db_table = "permiso"
        ordering = ("module", "code")

    def __str__(self) -> str:
        return self.name


class RolePermission(models.Model):
    pk = models.CompositePrimaryKey("role", "permission")
    role = models.ForeignKey(Role, db_column="id_rol", on_delete=models.DO_NOTHING, related_name="role_permissions")
    permission = models.ForeignKey(
        Permission, db_column="id_permiso", on_delete=models.DO_NOTHING, related_name="permission_roles"
    )

    class Meta:
        managed = False
        db_table = "rol_permiso"
        unique_together = (("role", "permission"),)


class UserRole(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        "accounts.User", db_column="id_usuario", on_delete=models.DO_NOTHING, related_name="user_roles"
    )
    role = models.ForeignKey(Role, db_column="id_rol", on_delete=models.DO_NOTHING, related_name="assignments")
    tenant = models.ForeignKey(
        "tenancy.Tenant", db_column="id_tenant", null=True, blank=True, on_delete=models.DO_NOTHING, related_name="role_assignments"
    )
    assigned_at = models.DateTimeField(db_column="asignado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "usuario_rol"
