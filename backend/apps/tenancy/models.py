from django.db import models


class Tenant(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDIENTE", "Pendiente"
        ACTIVE = "ACTIVO", "Activo"
        INACTIVE = "INACTIVO", "Inactivo"
        SUSPENDED = "SUSPENDIDO", "Suspendido"

    id = models.BigAutoField(primary_key=True)
    city_id = models.BigIntegerField(db_column="id_ciudad", null=True, blank=True)
    legal_name = models.CharField(db_column="razon_social", max_length=180)
    trade_name = models.CharField(db_column="nombre_comercial", max_length=180)
    subdomain = models.CharField(db_column="subdominio", max_length=80, unique=True)
    tax_id = models.CharField(db_column="nit", max_length=30, null=True, blank=True, unique=True)
    contact_email = models.EmailField(db_column="email_contacto", null=True, blank=True)
    phone = models.CharField(db_column="telefono", max_length=30, null=True, blank=True)
    status = models.CharField(db_column="estado", max_length=20, choices=Status.choices)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="actualizado_en", auto_now=True)

    class Meta:
        managed = False
        db_table = "tenant"
        ordering = ("trade_name",)

    def __str__(self) -> str:
        return self.trade_name


class UserTenant(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVO", "Activo"
        INACTIVE = "INACTIVO", "Inactivo"
        INVITED = "INVITADO", "Invitado"

    pk = models.CompositePrimaryKey("user", "tenant")
    user = models.ForeignKey(
        "accounts.User", db_column="id_usuario", on_delete=models.DO_NOTHING, related_name="tenant_memberships"
    )
    tenant = models.ForeignKey(Tenant, db_column="id_tenant", on_delete=models.DO_NOTHING, related_name="memberships")
    status = models.CharField(db_column="estado", max_length=20, choices=Status.choices)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "usuario_tenant"
        unique_together = (("user", "tenant"),)
