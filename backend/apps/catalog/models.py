from decimal import Decimal

from django.db import models

HOTEL_PRODUCT_CODE = "HOTEL"
ROOM_PRODUCT_CODE = "HABITACION"
DEFAULT_CANCELLATION_POLICY_NAME = "Política estándar SITUR-SMART"
DEFAULT_CANCELLATION_RULES = (
    (0, 0, "100.00"),
    (1, 2, "50.00"),
    (3, 6, "25.00"),
    (7, None, "0.00"),
)

# Precision que puede guardar NUMERIC(9,6): seis decimales, ~11 cm. Un GPS
# devuelve hasta trece y lo que sobra es ruido del sensor, asi que se redondea
# en vez de rechazarse. Lo comparten el serializer y los servicios para que la
# estrategia sea una sola.
COORDINATE_PRECISION = Decimal("0.000001")
COORDINATE_LIMITS = {"latitud": Decimal("90"), "longitud": Decimal("180")}

COORDINATE_PAIR_MESSAGE = (
    "La latitud y la longitud viajan juntas: envía las dos para fijar la "
    "ubicación, o las dos en null para quitarla."
)

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


class CancellationPolicy(models.Model):
    """Condiciones de cancelacion definidas por una empresa.

    La tabla existe desde el esquema inicial. Se mapea ahora porque CU43 debe
    calcular sus condiciones en el backend; Angular y Flutter solo muestran el
    resultado y nunca reinterpretan los porcentajes.
    """

    id = models.BigAutoField(primary_key=True)
    tenant = models.ForeignKey(
        "tenancy.Tenant",
        db_column="id_tenant",
        on_delete=models.DO_NOTHING,
        related_name="cancellation_policies",
    )
    name = models.CharField(db_column="nombre", max_length=120)
    refundable = models.BooleanField(db_column="reembolsable", default=True)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "politica_cancelacion"
        ordering = ("name", "id")
        unique_together = (("tenant", "name"),)

    def __str__(self) -> str:
        return self.name

    @classmethod
    def ensure_default(cls, tenant_id: int):
        """Politica base idempotente para productos nuevos de una empresa."""
        policy, _ = cls.objects.get_or_create(
            tenant_id=tenant_id,
            name=DEFAULT_CANCELLATION_POLICY_NAME,
            defaults={"refundable": True},
        )
        for minimum, maximum, percentage in DEFAULT_CANCELLATION_RULES:
            PenaltyRule.objects.get_or_create(
                policy=policy,
                minimum_days=minimum,
                maximum_days=maximum,
                defaults={"penalty_percentage": percentage},
            )
        return policy


class PenaltyRule(models.Model):
    """Penalizacion aplicable segun los dias de anticipacion."""

    id = models.BigAutoField(primary_key=True)
    policy = models.ForeignKey(
        CancellationPolicy,
        db_column="id_politica",
        on_delete=models.DO_NOTHING,
        related_name="rules",
    )
    minimum_days = models.PositiveIntegerField(db_column="dias_antes_min")
    maximum_days = models.PositiveIntegerField(db_column="dias_antes_max", null=True)
    penalty_percentage = models.DecimalField(
        db_column="porcentaje_penalizacion", max_digits=5, decimal_places=2
    )

    class Meta:
        managed = False
        db_table = "regla_penalizacion"
        ordering = ("minimum_days", "maximum_days", "id")


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
    cancellation_policy = models.ForeignKey(
        CancellationPolicy,
        db_column="id_politica_cancelacion",
        on_delete=models.DO_NOTHING,
        related_name="products",
        null=True,
        blank=True,
    )
    code = models.CharField(db_column="codigo", max_length=60)
    name = models.CharField(db_column="nombre", max_length=180)
    description = models.TextField(db_column="descripcion", null=True, blank=True)
    locality = models.CharField(db_column="localidad", max_length=180, null=True, blank=True)
    base_price = models.DecimalField(db_column="precio_base", max_digits=12, decimal_places=2)
    max_capacity = models.PositiveIntegerField(db_column="capacidad_maxima")
    status = models.CharField(db_column="estado", max_length=20, choices=Status.choices)
    image_url = models.CharField(db_column="imagen_url", max_length=500, null=True, blank=True)
    # Publicacion programada (catalog/scheduling.py): el cron publica o retira
    # a su hora y deja marcado cuando lo publico solo.
    publish_at = models.DateTimeField(db_column="publicar_en", null=True, blank=True)
    unpublish_at = models.DateTimeField(db_column="retirar_en", null=True, blank=True)
    auto_published_at = models.DateTimeField(db_column="publicado_automaticamente_en", null=True, blank=True)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="actualizado_en", auto_now=True)

    class Meta:
        managed = False
        db_table = "producto_turistico"
        ordering = ("-updated_at",)
        unique_together = (("tenant", "code"),)

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        # Todo producto nuevo nace con condiciones de cancelacion. Hacerlo en
        # el modelo cubre catalogo generico, hospedajes, habitaciones, seeds y
        # futuros comandos sin repetir la regla en cada servicio.
        if self._state.adding and self.cancellation_policy_id is None and self.tenant_id:
            self.cancellation_policy = CancellationPolicy.ensure_default(self.tenant_id)
        return super().save(*args, **kwargs)


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
    # Ubicacion exacta, opcional. Misma forma que ciudad.latitud/longitud:
    # NUMERIC(9,6) resuelve ~11 cm y le alcanza justo a 180.000000. Van siempre
    # en par -- media coordenada no ubica nada -- y la base lo obliga con
    # chk_establecimiento_coordenadas, no solo el backend.
    #
    # Las habitaciones no tienen coordenada propia: usan la de su
    # establecimiento, igual que heredan ciudad y localidad.
    latitude = models.DecimalField(
        db_column="latitud", max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        db_column="longitud", max_digits=9, decimal_places=6, null=True, blank=True
    )
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


class ProductReview(models.Model):
    """Opinion de un usuario sobre un producto turistico concreto."""

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        "accounts.User", db_column="id_usuario", on_delete=models.CASCADE,
        related_name="product_reviews",
    )
    product = models.ForeignKey(
        TourismProduct, db_column="id_producto", on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.SmallIntegerField(db_column="calificacion")
    comment = models.TextField(db_column="comentario")
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="actualizado_en", auto_now=True)

    class Meta:
        managed = False
        db_table = "resena_producto"
        ordering = ("-created_at", "-id")
        constraints = [  # noqa: RUF012 - declaracion de Meta de Django
            models.UniqueConstraint(fields=("user", "product"), name="uq_resena_usuario_producto"),
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="chk_resena_calificacion",
            ),
        ]
        indexes = [  # noqa: RUF012 - declaracion de Meta de Django
            models.Index(fields=("product", "-created_at", "-id"), name="idx_resena_producto_fecha"),
        ]
