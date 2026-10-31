from django.conf import settings
from django.db import models


class CustomPackage(models.Model):
    class Status(models.TextChoices):
        DRAFT = "BORRADOR", "Borrador"
        SAVED = "GUARDADO", "Guardado"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="custom_packages")
    name = models.CharField(max_length=120)
    city = models.ForeignKey("tenancy.City", null=True, blank=True, on_delete=models.SET_NULL)
    start_date = models.DateField()
    end_date = models.DateField()
    travelers = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "paquete_personalizado"
        ordering = ("-updated_at", "-id")


class PackageComponent(models.Model):
    package = models.ForeignKey(CustomPackage, on_delete=models.CASCADE, related_name="components")
    product = models.ForeignKey("catalog.TourismProduct", on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    quantity = models.PositiveSmallIntegerField()
    guests = models.PositiveSmallIntegerField(null=True, blank=True)
    departure = models.ForeignKey("catalog.Availability", null=True, blank=True, on_delete=models.PROTECT)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "paquete_personalizado_componente"
        ordering = ("start_date", "id")


class PackagePurchase(models.Model):
    """Una sola compra para todas las reservas de un paquete personalizado."""

    class Status(models.TextChoices):
        CREATED = "CREADA", "Pendiente de pago"
        CONFIRMED = "CONFIRMADA", "Confirmada"
        CANCELLED = "CANCELADA", "Cancelada"
        EXPIRED = "EXPIRADA", "Expirada"
        REFUNDED = "REEMBOLSADA", "Reembolsada"

    package = models.OneToOneField(
        CustomPackage, on_delete=models.PROTECT, related_name="purchase"
    )
    order = models.OneToOneField(
        "bookings.Order", on_delete=models.PROTECT, related_name="package_purchase"
    )
    currency = models.ForeignKey("catalog.Currency", on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    original_amount = models.DecimalField(max_digits=14, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    final_amount = models.DecimalField(max_digits=14, decimal_places=2)
    provider = models.CharField(max_length=60, default="STRIPE")
    provider_reference = models.CharField(max_length=150, null=True, blank=True)
    idempotency_key = models.CharField(max_length=100, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "compra_paquete_personalizado"
        constraints = [  # noqa: RUF012 - configuración declarativa de Django
            models.UniqueConstraint(
                fields=("provider", "provider_reference"),
                name="uq_compra_paquete_proveedor_referencia",
                condition=models.Q(provider_reference__isnull=False),
            )
        ]


class PackagePurchaseAllocation(models.Model):
    """Importe congelado que corresponde a cada reserva y empresa."""

    purchase = models.ForeignKey(
        PackagePurchase, on_delete=models.CASCADE, related_name="allocations"
    )
    booking = models.OneToOneField(
        "bookings.Booking", on_delete=models.PROTECT, related_name="package_allocation"
    )
    original_amount = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    final_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "compra_paquete_asignacion"
        constraints = [  # noqa: RUF012 - configuración declarativa de Django
            models.CheckConstraint(
                condition=models.Q(original_amount__gte=0),
                name="chk_asignacion_importe_original",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_amount__gte=0),
                name="chk_asignacion_descuento",
            ),
            models.CheckConstraint(
                condition=models.Q(final_amount__gt=0),
                name="chk_asignacion_importe_final",
            ),
        ]
