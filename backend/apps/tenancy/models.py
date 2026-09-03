from django.db import models


class Country(models.Model):
    id = models.BigAutoField(primary_key=True)
    iso_code = models.CharField(db_column="codigo_iso", max_length=3, unique=True)
    name = models.CharField(db_column="nombre", max_length=100, unique=True)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "pais"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class City(models.Model):
    id = models.BigAutoField(primary_key=True)
    country = models.ForeignKey(
        Country,
        db_column="id_pais",
        on_delete=models.DO_NOTHING,
        related_name="cities",
    )
    name = models.CharField(db_column="nombre", max_length=120)
    latitude = models.DecimalField(
        db_column="latitud", max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        db_column="longitud", max_digits=9, decimal_places=6, null=True, blank=True
    )
    timezone = models.CharField(
        db_column="zona_horaria", max_length=80, null=True, blank=True
    )
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "ciudad"
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name}, {self.country.name}"


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
