from django.db import models


class Currency(models.Model):
    id = models.BigAutoField(primary_key=True)
    iso_code = models.CharField(db_column="codigo_iso", max_length=3, unique=True)
    name = models.CharField(db_column="nombre", max_length=80)
    symbol = models.CharField(db_column="simbolo", max_length=10)
    decimals = models.SmallIntegerField(db_column="decimales", default=2)

    class Meta:
        managed = False
        db_table = "moneda"
        ordering = ("iso_code",)

    def __str__(self) -> str:
        return self.iso_code


class ProductType(models.Model):
    id = models.BigAutoField(primary_key=True)
    code = models.CharField(db_column="codigo", max_length=50, unique=True)
    name = models.CharField(db_column="nombre", max_length=120, unique=True)

    class Meta:
        managed = False
        db_table = "tipo_producto"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class TourismProduct(models.Model):
    class Status(models.TextChoices):
        DRAFT = "BORRADOR", "Borrador"
        PUBLISHED = "PUBLICADO", "Publicado"
        INACTIVE = "INACTIVO", "Inactivo"

    id = models.BigAutoField(primary_key=True)
    tenant = models.ForeignKey(
        "tenancy.Tenant", db_column="id_tenant", on_delete=models.DO_NOTHING, related_name="products"
    )
    product_type = models.ForeignKey(
        ProductType, db_column="id_tipo_producto", on_delete=models.DO_NOTHING, related_name="products"
    )
    city = models.ForeignKey(
        "tenancy.City", db_column="id_ciudad", on_delete=models.DO_NOTHING, related_name="products"
    )
    currency = models.ForeignKey(
        Currency, db_column="id_moneda", on_delete=models.DO_NOTHING, related_name="products"
    )
    cancellation_policy_id = models.BigIntegerField(
        db_column="id_politica_cancelacion", null=True, blank=True
    )
    code = models.CharField(db_column="codigo", max_length=60)
    name = models.CharField(db_column="nombre", max_length=180)
    description = models.TextField(db_column="descripcion", null=True, blank=True)
    locality = models.CharField(db_column="localidad", max_length=180, null=True, blank=True)
    base_price = models.DecimalField(db_column="precio_base", max_digits=12, decimal_places=2)
    max_capacity = models.PositiveIntegerField(db_column="capacidad_maxima")
    status = models.CharField(db_column="estado", max_length=20, choices=Status.choices)
    image_url = models.CharField(db_column="imagen_url", max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="actualizado_en", auto_now=True)

    class Meta:
        managed = False
        db_table = "producto_turistico"
        ordering = ("-updated_at",)
        unique_together = (("tenant", "code"),)

    def __str__(self) -> str:
        return self.name


class Availability(models.Model):
    id = models.BigAutoField(primary_key=True)
    product = models.ForeignKey(
        TourismProduct,
        db_column="id_producto",
        on_delete=models.DO_NOTHING,
        related_name="availabilities",
    )
    tenant = models.ForeignKey(
        "tenancy.Tenant", db_column="id_tenant", on_delete=models.DO_NOTHING
    )
    start = models.DateTimeField(db_column="inicio")
    end = models.DateTimeField(db_column="fin")
    total_capacity = models.PositiveIntegerField(db_column="cupo_total")
    closed = models.BooleanField(db_column="cerrado", default=False)

    class Meta:
        managed = False
        db_table = "disponibilidad"
