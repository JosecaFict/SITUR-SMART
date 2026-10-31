"""Precio único para marketplace, cotización y reserva. No escribe inventario."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Prefetch, prefetch_related_objects
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.catalog.models import TourismProduct
from apps.tenancy.subscriptions import restricted_tenant_ids

from .models import Promotion

# La reserva de HABITACION multiplica por noches, mientras el snapshot de CU51
# almacena precio unitario por cantidad. Hasta que ese contrato contemple las
# noches, la modalidad EXISTENTE se limita a productos reservables por día.
EXISTING_PRODUCT_CODES = frozenset(
    {"TOUR", "EXPERIENCIA", "ATRACCION", "RESTAURANTE", "PAQUETE"}
)


@dataclass(frozen=True)
class Discount:
    promotion: Promotion
    original: Decimal
    final: Decimal

    def data(self, quantity=1):
        return {
            "id": self.promotion.id,
            "modalidad": self.promotion.mode,
            "nombre": self.promotion.name,
            "porcentaje_descuento": str(self.promotion.percentage),
            "precio_original": str(self.original),
            "precio_final": str(self.final),
            "monto_descuento": str(self.original - self.final),
            "total_original": str(self.original * quantity),
            "descuento_total": str((self.original - self.final) * quantity),
            "total": str(self.final * quantity),
            "inicio": self.promotion.starts_at,
            "fin": self.promotion.ends_at,
        }


def discounted_price(original, percentage, currency):
    # Las columnas de precios e importes existentes admiten dos decimales.
    if currency.decimals not in (0, 1, 2):
        raise ValidationError(
            {
                "moneda": "La precisión de esta moneda no es compatible con las reservas actuales."
            }
        )
    unit = Decimal(1).scaleb(-currency.decimals)
    if Decimal(original).quantize(unit, rounding=ROUND_HALF_UP) != Decimal(original):
        raise ValidationError(
            {"moneda": "El precio original excede la precisión de esta moneda."}
        )
    original = Decimal(original).quantize(unit, rounding=ROUND_HALF_UP)
    percentage = Decimal(percentage)
    if original <= 0 or not 0 < percentage < 100:
        raise ValidationError(
            {
                "porcentaje_descuento": "Precio positivo y porcentaje mayor que 0 y menor que 100 requeridos."
            }
        )
    final = (original * (1 - percentage / 100)).quantize(unit, rounding=ROUND_HALF_UP)
    if final <= 0 or final >= original:
        raise ValidationError(
            {
                "porcentaje_descuento": "El descuento debe producir un ahorro y un precio final positivo con la precisión de la moneda."
            }
        )
    return original, final


def current_promotions(now=None):
    now = now or timezone.now()
    return Promotion.objects.filter(
        administrative_status=Promotion.Status.ENABLED,
        starts_at__lte=now,
        ends_at__gt=now,
        tenant__status="ACTIVO",
    ).exclude(tenant_id__in=restricted_tenant_ids())


def prefetch_product_discounts(products):
    eligible = [
        product
        for product in products
        if isinstance(product, TourismProduct)
        and product.product_type.code in EXISTING_PRODUCT_CODES
        and product.status == TourismProduct.Status.PUBLISHED
    ]
    prefetch_related_objects(
        eligible,
        Prefetch(
            "promotions",
            queryset=current_promotions().filter(mode=Promotion.Mode.EXISTING),
            to_attr="current_promotions",
        ),
    )


def product_discount(product, *, promotion_id=None):
    valid_product = (
        product.product_type.code in EXISTING_PRODUCT_CODES
        and product.status == TourismProduct.Status.PUBLISHED
    )
    candidates = getattr(product, "current_promotions", None)
    if candidates is None and valid_product:
        candidates = current_promotions().filter(
            product_id=product.id,
            tenant_id=product.tenant_id,
            mode=Promotion.Mode.EXISTING,
        )
    promotion = next(iter(candidates or []), None) if valid_product else None
    if promotion_id is not None and (promotion is None or promotion.id != promotion_id):
        raise ValidationError(
            {
                "promocion_id": "La promoción no está vigente para este producto o todavía no admite reservas."
            }
        )
    if promotion is None:
        return None
    try:
        original, final = discounted_price(
            product.base_price, promotion.percentage, product.currency
        )
    except ValidationError:
        if promotion_id is not None:
            raise
        return None
    return Discount(promotion, original, final)
