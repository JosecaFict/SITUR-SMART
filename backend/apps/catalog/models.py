from django.db import models

HOTEL_PRODUCT_CODE = "HOTEL"
ROOM_PRODUCT_CODE = "HABITACION"

# Un producto de estos dos tipos solo tiene sentido acompaniado de su fila en
# establecimiento_hospedaje o habitacion. Por eso no se crean ni se editan por
# /api/v1/productos/: ese camino dejaria un hotel sin ficha, incapaz de tener
# habitaciones e invisible para el Marketplace de hospedaje.
LODGING_PRODUCT_CODES = frozenset({HOTEL_PRODUCT_CODE, ROOM_PRODUCT_CODE})


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


class LodgingType(models.Model):
    """Catalogo de tipos de hospedaje.

    Los cinco tipos quedan sembrados para poder ampliar sin rediseniar la base,
    pero solo los de ``AVAILABLE_LODGING_TYPE_CODES`` se aceptan por API.
    """

    class Code(models.TextChoices):
        HOTEL = "HOTEL", "Hotel"
        HOSTEL = "HOSTAL", "Hostal"
        CABIN = "CABANA", "Cabaña"
        APARTMENT = "APARTAMENTO_TURISTICO", "Apartamento turístico"
        RURAL = "HOSPEDAJE_RURAL", "Hospedaje rural"

    id = models.BigAutoField(primary_key=True)
    code = models.CharField(db_column="codigo", max_length=50, unique=True)
    name = models.CharField(db_column="nombre", max_length=120, unique=True)

    class Meta:
        managed = False
        db_table = "tipo_hospedaje"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


# Tipos de hospedaje habilitados en esta fase. La restriccion vive en el backend
# a proposito: que la web deshabilite las otras opciones del desplegable no
# impide un POST directo, asi que el limite se aplica donde no se puede eludir.
# Para habilitar HOSTAL, CABANA y los demas basta agregarlos aqui; la tabla y el
# modelo ya los soportan.
AVAILABLE_LODGING_TYPE_CODES = frozenset({LodgingType.Code.HOTEL})

UNSUPPORTED_LODGING_TYPE_MESSAGE = "En esta versión solamente se admite el tipo HOTEL."


class LodgingEstablishment(models.Model):
    """Datos propios de un hotel, hostal o cabaña.

    Extiende 1 a 1 un ``TourismProduct`` de tipo HOTEL: nombre, ciudad,
    localidad, moneda, estado e imagen no se duplican aqui. ``tenant`` si se
    repite, porque la restriccion de integridad multitenant se apoya en una
    clave foranea compuesta contra ``producto_turistico(id, id_tenant)``.
    """

    id = models.BigAutoField(primary_key=True)
    product = models.OneToOneField(
        TourismProduct, db_column="id_producto", on_delete=models.DO_NOTHING, related_name="lodging"
    )
    tenant = models.ForeignKey(
        "tenancy.Tenant", db_column="id_tenant", on_delete=models.DO_NOTHING, related_name="lodgings"
    )
    lodging_type = models.ForeignKey(
        LodgingType, db_column="id_tipo_hospedaje", on_delete=models.DO_NOTHING, related_name="establishments"
    )
    address = models.CharField(db_column="direccion", max_length=250, null=True, blank=True)
    star_rating = models.SmallIntegerField(db_column="categoria_estrellas", null=True, blank=True)
    check_in = models.TimeField(db_column="hora_check_in", null=True, blank=True)
    check_out = models.TimeField(db_column="hora_check_out", null=True, blank=True)
    services = models.JSONField(db_column="servicios", default=list, blank=True)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="actualizado_en", auto_now=True)

    class Meta:
        managed = False
        db_table = "establecimiento_hospedaje"
        ordering = ("id",)

    def __str__(self) -> str:
        return self.product.name


class Room(models.Model):
    """Tipo de habitacion ofertado dentro de un establecimiento.

    No representa una habitacion fisica numerada: ``quantity`` cuenta cuantas
    unidades de este tipo existen y las capacidades indican cuantas personas
    entran en una. El precio por noche es ``product.base_price``.
    """

    id = models.BigAutoField(primary_key=True)
    product = models.OneToOneField(
        TourismProduct, db_column="id_producto", on_delete=models.DO_NOTHING, related_name="room"
    )
    establishment = models.ForeignKey(
        LodgingEstablishment,
        db_column="id_establecimiento",
        on_delete=models.DO_NOTHING,
        related_name="rooms",
    )
    tenant = models.ForeignKey(
        "tenancy.Tenant", db_column="id_tenant", on_delete=models.DO_NOTHING, related_name="rooms"
    )
    quantity = models.PositiveIntegerField(db_column="cantidad_habitaciones", default=1)
    adults_capacity = models.PositiveSmallIntegerField(db_column="capacidad_adultos", default=2)
    children_capacity = models.PositiveSmallIntegerField(db_column="capacidad_ninos", default=0)
    bed_type = models.CharField(db_column="tipo_cama", max_length=60, null=True, blank=True)
    includes_breakfast = models.BooleanField(db_column="incluye_desayuno", default=False)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="actualizado_en", auto_now=True)

    class Meta:
        managed = False
        db_table = "habitacion"
        ordering = ("id",)

    def __str__(self) -> str:
        return self.product.name


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
