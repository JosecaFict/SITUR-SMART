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


# Unico estado en el que una empresa opera. El resto permite autenticarse y ver
# el perfil, pero no trabajar dentro de ese tenant.
TENANT_OPERATIONAL_STATUS = Tenant.Status.ACTIVE

# Transiciones permitidas. Es un grafo cerrado a proposito: cualquier par que no
# aparezca aqui se rechaza con 400.
#
# Lo que deliberadamente NO existe es ACTIVO -> PENDIENTE. "Pendiente" significa
# "la plataforma todavia no la reviso", y eso no puede volver a ser cierto una
# vez que la empresa fue activada: para dejar de operar estan SUSPENDIDO, que es
# reversible, e INACTIVO, que es el cierre.
TENANT_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    Tenant.Status.PENDING: frozenset({Tenant.Status.ACTIVE, Tenant.Status.INACTIVE}),
    Tenant.Status.ACTIVE: frozenset({Tenant.Status.SUSPENDED, Tenant.Status.INACTIVE}),
    Tenant.Status.SUSPENDED: frozenset({Tenant.Status.ACTIVE, Tenant.Status.INACTIVE}),
    Tenant.Status.INACTIVE: frozenset({Tenant.Status.ACTIVE}),
}

# Motivo que se devuelve al bloquear una operacion. Es generico a proposito: le
# dice a la persona por que no puede trabajar sin revelar decisiones internas de
# la plataforma ni datos de la empresa.
TENANT_BLOCK_REASONS = {
    Tenant.Status.PENDING: "La empresa todavía no fue activada por la plataforma.",
    Tenant.Status.SUSPENDED: "La empresa está suspendida.",
    Tenant.Status.INACTIVE: "La empresa está inactiva.",
}


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


class Plan(models.Model):
    class Periodicity(models.TextChoices):
        MONTHLY = "MENSUAL", "Mensual"
        YEARLY = "ANUAL", "Anual"

    id = models.BigAutoField(primary_key=True)
    currency = models.ForeignKey(
        "catalog.Currency", db_column="id_moneda", on_delete=models.DO_NOTHING, related_name="plans"
    )
    code = models.CharField(db_column="codigo", max_length=50, unique=True)
    name = models.CharField(db_column="nombre", max_length=100, unique=True)
    description = models.TextField(db_column="descripcion", null=True, blank=True)
    # Precio del periodo que indique `periodicity`.
    #
    # La columna fisica sigue llamandose precio_mensual a proposito: renombrarla
    # romperia SQL externo, consultas guardadas y procesos que la lean por
    # nombre. El atributo se llama `price` porque "mensual" miente en cuanto un
    # plan sea ANUAL, y la API expone `precio` y `precio_mensual` apuntando a
    # esta misma columna, asi que los dos nombres no pueden divergir.
    price = models.DecimalField(db_column="precio_mensual", max_digits=12, decimal_places=2)
    periodicity = models.CharField(
        db_column="periodicidad",
        max_length=10,
        choices=Periodicity.choices,
        default=Periodicity.MONTHLY,
    )

    # DEPRECADAS. Los topes viven en PlanLimit, donde agregar un recurso es un
    # INSERT y no una migracion. Siguen en la base y las sigue leyendo la logica
    # de cuota actual; el reemplazo por plan_limite es la Fase 3.
    max_users = models.PositiveIntegerField(db_column="max_usuarios")
    max_products = models.PositiveIntegerField(db_column="max_productos")

    commission_percentage = models.DecimalField(
        db_column="porcentaje_comision", max_digits=5, decimal_places=2, default=0
    )
    active = models.BooleanField(db_column="activo", default=True)

    class Meta:
        managed = False
        db_table = "plan"
        ordering = ("price",)

    def __str__(self) -> str:
        return self.name


class PlanLimit(models.Model):
    """Tope de un recurso en un plan.

    ``limit`` es nullable a proposito y los tres estados son distintos:

    * ``None`` -- ilimitado;
    * ``0``    -- el recurso no esta permitido en ese plan;
    * ``N > 0``-- tope.

    Es lo que reemplaza al centinela 999999 del plan Max, que existia solo
    porque ``plan.max_productos`` es NOT NULL con CHECK (> 0) y no puede
    expresar "sin tope".
    """

    class Resource(models.TextChoices):
        HOTELS = "HOTELES_PUBLICADOS", "Hoteles publicados"
        ROOMS = "HABITACIONES_OFERTADAS", "Habitaciones ofertadas"
        TOURS = "TOURS_PUBLICADOS", "Tours publicados"
        RESTAURANTS = "RESTAURANTES_PUBLICADOS", "Restaurantes publicados"
        EXPERIENCES = "EXPERIENCIAS_PUBLICADAS", "Experiencias publicadas"
        ATTRACTIONS = "ATRACCIONES_PUBLICADAS", "Atracciones publicadas"
        PACKAGES = "PAQUETES_PUBLICADOS", "Paquetes publicados"
        USERS = "USUARIOS_ACTIVOS", "Usuarios activos"

    id = models.BigAutoField(primary_key=True)
    plan = models.ForeignKey(
        Plan, db_column="id_plan", on_delete=models.CASCADE, related_name="limits"
    )
    resource = models.CharField(db_column="recurso", max_length=40, choices=Resource.choices)
    limit = models.IntegerField(db_column="limite", null=True, blank=True)

    class Meta:
        managed = False
        db_table = "plan_limite"
        ordering = ("resource",)
        unique_together = (("plan", "resource"),)

    def __str__(self) -> str:
        return f"{self.plan.code}:{self.resource}={'∞' if self.limit is None else self.limit}"

    @property
    def is_unlimited(self) -> bool:
        return self.limit is None


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVA", "Activa"
        EXPIRED = "VENCIDA", "Vencida"
        CANCELLED = "CANCELADA", "Cancelada"
        SUSPENDED = "SUSPENDIDA", "Suspendida"

    id = models.BigAutoField(primary_key=True)
    tenant = models.ForeignKey(
        Tenant, db_column="id_tenant", on_delete=models.DO_NOTHING, related_name="subscriptions"
    )
    plan = models.ForeignKey(
        Plan, db_column="id_plan", on_delete=models.DO_NOTHING, related_name="subscriptions"
    )
    start_date = models.DateField(db_column="fecha_inicio")
    end_date = models.DateField(db_column="fecha_fin", null=True, blank=True)
    status = models.CharField(
        db_column="estado", max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    auto_renew = models.BooleanField(db_column="renovacion_automatica", default=False)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)

    # Condiciones congeladas al contratar. Lo que la empresa acepto pagar no
    # depende de lo que el plan cueste hoy: cambiar plan.price no toca estas
    # columnas, y una renovacion crea una fila nueva que copia las vigentes
    # en ese momento.
    contracted_price = models.DecimalField(
        db_column="precio_contratado", max_digits=12, decimal_places=2, null=True, blank=True
    )
    contracted_currency = models.ForeignKey(
        "catalog.Currency",
        db_column="id_moneda_contratada",
        on_delete=models.DO_NOTHING,
        related_name="contracted_subscriptions",
        null=True,
        blank=True,
    )
    contracted_periodicity = models.CharField(
        db_column="periodicidad_contratada",
        max_length=10,
        choices=Plan.Periodicity.choices,
        null=True,
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "suscripcion"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.tenant} -> {self.plan}"
