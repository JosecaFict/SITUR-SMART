"""Accesos a los datos de seed_bolivia que usan las pruebas de integracion."""

from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalog.models import LodgingEstablishment, Room, TourismProduct

TURISTA = "turista1@situr.com.bo"
OTRO_TURISTA = "turista2@situr.com.bo"


def cliente(email: str = TURISTA) -> APIClient:
    client = APIClient()
    client.force_authenticate(User.objects.get(email=email))
    return client


def tour_publicado() -> TourismProduct:
    return TourismProduct.objects.filter(
        status="PUBLICADO", tenant__status="ACTIVO", product_type__code="TOUR"
    ).order_by("id").first()


def hotel_publicado() -> LodgingEstablishment:
    return (
        LodgingEstablishment.objects.filter(
            product__status="PUBLICADO",
            tenant__status="ACTIVO",
            rooms__product__status="PUBLICADO",
        )
        .select_related("product")
        .order_by("id")
        .first()
    )


def habitacion_publicada() -> Room:
    return (
        Room.objects.filter(
            product__status="PUBLICADO",
            establishment__product__status="PUBLICADO",
            tenant__status="ACTIVO",
        )
        .select_related("product")
        .order_by("id")
        .first()
    )
