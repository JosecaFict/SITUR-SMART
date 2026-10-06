from rest_framework.exceptions import NotFound

from apps.catalog.models import TourismProduct
from apps.catalog.services import marketplace_visible_products, with_lodging_from_price

from .models import Favorite


def public_products():
    """Productos que el Marketplace muestra hoy, con el precio "desde" anotado.

    Misma regla que el detalle publico: publicado, empresa activa y, si es un
    hotel, con al menos una habitacion que ofrecer.
    """
    return marketplace_visible_products(
        with_lodging_from_price(
            TourismProduct.objects.select_related(
                "tenant", "product_type", "city__country", "currency",
                "room__establishment__product", "lodging",
            )
        )
    ).filter(status=TourismProduct.Status.PUBLISHED, tenant__status="ACTIVO")


def list_favorites(*, user) -> list[TourismProduct]:
    """Favoritos visibles del usuario, del mas reciente al mas viejo.

    Un favorito cuyo producto dejo de publicarse no se borra: si la empresa lo
    vuelve a publicar, reaparece en la lista. Solo se oculta mientras tanto.
    """
    ids = list(Favorite.objects.filter(user=user).values_list("product_id", flat=True))
    products = {product.id: product for product in public_products().filter(id__in=ids)}
    return [products[product_id] for product_id in ids if product_id in products]


def add_favorite(*, user, product_id: int) -> bool:
    """Marca un producto. Devuelve True si se creo, False si ya estaba."""
    if not public_products().filter(id=product_id).exists():
        raise NotFound("Producto no encontrado.")
    _, created = Favorite.objects.get_or_create(user=user, product_id=product_id)
    return created


def remove_favorite(*, user, product_id: int) -> None:
    """Quita la marca. Quitar algo que no estaba no es un error."""
    Favorite.objects.filter(user=user, product_id=product_id).delete()
