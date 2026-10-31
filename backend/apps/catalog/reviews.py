"""Reglas de CU35 y agregados de reseñas sobre el catalogo existente."""

from django.db import IntegrityError, transaction
from django.db.models import (
    Avg,
    Count,
    DecimalField,
    IntegerField,
    OuterRef,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from rest_framework.exceptions import NotFound, ValidationError

from apps.tenancy.subscriptions import restricted_tenant_ids

from .models import ProductReview, TourismProduct


def review_stat_annotations(*, product_ref="pk"):
    """Expresiones SQL para un producto; ninguna consulta por tarjeta."""
    grouped = (
        ProductReview.objects.filter(product_id=OuterRef(product_ref))
        .order_by().values("product_id")
        .annotate(average=Avg("rating"), total=Count("id"))
    )
    return {
        "review_average": Subquery(
            grouped.values("average")[:1], output_field=DecimalField(max_digits=3, decimal_places=2)
        ),
        "review_count": Coalesce(
            Subquery(grouped.values("total")[:1], output_field=IntegerField()), Value(0)
        ),
    }


def with_review_stats(queryset, *, product_ref="pk"):
    return queryset.annotate(**review_stat_annotations(product_ref=product_ref))


def public_reviewable_product(product_id: int) -> TourismProduct:
    """La misma visibilidad de las fichas publicas, incluida la de habitaciones."""
    # Importacion local: services utiliza with_review_stats para el Marketplace.
    from .services import marketplace_visible_products, public_rooms

    product = TourismProduct.objects.select_related("product_type").filter(id=product_id).first()
    if product is None:
        raise NotFound("Producto no encontrado.")
    if product.product_type.code == "HABITACION":
        visible = public_rooms().filter(product_id=product_id).exists()
    else:
        visible = marketplace_visible_products(
            TourismProduct.objects.filter(
                id=product_id,
                status=TourismProduct.Status.PUBLISHED,
                tenant__status="ACTIVO",
            ).exclude(tenant_id__in=restricted_tenant_ids())
        ).exists()
    if not visible:
        raise NotFound("Producto no encontrado.")
    return product


def own_review(*, user, review_id: int) -> ProductReview:
    review = ProductReview.objects.select_related("user").filter(id=review_id, user=user).first()
    if review is None:
        raise NotFound("Reseña no encontrada.")
    return review


def create_review(*, user, product_id: int, rating: int, comment: str) -> ProductReview:
    product = public_reviewable_product(product_id)
    if ProductReview.objects.filter(user=user, product=product).exists():
        raise ValidationError({"detail": "Ya registraste una reseña para este producto."})
    try:
        with transaction.atomic():
            return ProductReview.objects.create(
                user=user, product=product, rating=rating, comment=comment,
            )
    except IntegrityError as exc:
        # La restriccion UNIQUE protege tambien dos POST simultaneos.
        constraint = getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None)
        if constraint != "uq_resena_usuario_producto":
            raise
        raise ValidationError({"detail": "Ya registraste una reseña para este producto."}) from exc


def update_review(*, user, review_id: int, **changes) -> ProductReview:
    review = own_review(user=user, review_id=review_id)
    for field, value in changes.items():
        setattr(review, field, value)
    if changes:
        review.save(update_fields=[*changes, "updated_at"])
    return review


def delete_review(*, user, review_id: int) -> None:
    own_review(user=user, review_id=review_id).delete()
