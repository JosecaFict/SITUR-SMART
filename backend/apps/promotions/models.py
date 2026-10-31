from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Promotion(models.Model):
    class Mode(models.TextChoices):
        EXISTING = "EXISTENTE", "Paquete existente"
        COMBINED = "COMBINADO", "Servicios combinados"

    class Status(models.TextChoices):
        DRAFT = "BORRADOR", "Borrador"
        ENABLED = "HABILITADA", "Habilitada"
        DISABLED = "DESACTIVADA", "Desactivada"

    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.PROTECT, related_name="promotions"
    )
    mode = models.CharField(max_length=12, choices=Mode.choices)
    product = models.ForeignKey(
        "catalog.TourismProduct",
        on_delete=models.PROTECT,
        related_name="promotions",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    administrative_status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.DRAFT
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_promotions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "promocion_comercial"
        ordering = ("-created_at", "-id")
        indexes = (
            models.Index(
                fields=["tenant", "administrative_status"],
                name="promo_empresa_estado_idx",
            ),
            models.Index(
                fields=["administrative_status", "starts_at", "ends_at"],
                name="promo_vigencia_idx",
            ),
        )
        constraints = (
            models.CheckConstraint(
                condition=Q(percentage__gt=0, percentage__lt=100),
                name="promo_porcentaje_valido",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")), name="promo_fechas_validas"
            ),
            models.CheckConstraint(
                condition=(
                    Q(mode="EXISTENTE", product__isnull=False)
                    | Q(mode="COMBINADO", product__isnull=True)
                ),
                name="promo_modalidad_producto",
            ),
            models.CheckConstraint(
                condition=Q(
                    administrative_status__in=["BORRADOR", "HABILITADA", "DESACTIVADA"]
                ),
                name="promo_estado_valido",
            ),
        )

    def state_at(self, now=None):
        now = now or timezone.now()
        if self.administrative_status != self.Status.ENABLED:
            return self.administrative_status
        if now < self.starts_at:
            return "PROGRAMADA"
        if now >= self.ends_at:
            return "VENCIDA"
        return "VIGENTE"


class PromotionComponent(models.Model):
    promotion = models.ForeignKey(
        Promotion, on_delete=models.CASCADE, related_name="components"
    )
    product = models.ForeignKey(
        "catalog.TourismProduct",
        on_delete=models.PROTECT,
        related_name="promotion_components",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    quantity = models.PositiveIntegerField()
    guests = models.PositiveIntegerField(null=True, blank=True)
    departure = models.ForeignKey(
        "catalog.Availability", on_delete=models.PROTECT, null=True, blank=True
    )
    reference_unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    reference_total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "promocion_componente"
        ordering = ("start_date", "id")
        constraints = (
            models.CheckConstraint(
                condition=Q(quantity__gte=1, quantity__lte=500),
                name="promo_componente_cantidad",
            ),
            models.CheckConstraint(
                condition=Q(guests__isnull=True) | Q(guests__gte=1, guests__lte=500),
                name="promo_componente_huespedes",
            ),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gt=F("start_date")),
                name="promo_componente_fechas",
            ),
            models.UniqueConstraint(
                fields=["promotion", "product", "start_date"],
                name="promo_componente_unico",
            ),
        )


class BookingPromotionSnapshot(models.Model):
    """Importes pactados: nunca se recalculan al consultar o pagar una reserva."""

    booking = models.OneToOneField(
        "bookings.Booking", on_delete=models.CASCADE, related_name="promotion_snapshot"
    )
    promotion = models.ForeignKey(
        Promotion, on_delete=models.PROTECT, related_name="booking_snapshots"
    )
    name = models.CharField(max_length=200)
    currency = models.ForeignKey("catalog.Currency", on_delete=models.PROTECT)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    original_unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    final_unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    original_total = models.DecimalField(max_digits=14, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reserva_promocion"
        constraints = (
            models.CheckConstraint(
                condition=Q(percentage__gt=0, percentage__lt=100),
                name="reserva_promo_porcentaje",
            ),
            models.CheckConstraint(
                condition=Q(
                    quantity__gt=0, final_unit_price__gt=0, discount_amount__gte=0
                ),
                name="reserva_promo_importes",
            ),
            models.CheckConstraint(
                condition=Q(total=F("original_total") - F("discount_amount")),
                name="reserva_promo_total",
            ),
        )
