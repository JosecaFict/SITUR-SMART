"""Accesos a los datos de seed_bolivia y ayudas comunes de las pruebas de integracion."""

import hashlib
import hmac
import json
import time
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.bookings.models import Booking, InventoryLock
from apps.catalog.models import LodgingEstablishment, Room, TourismProduct
from apps.payments.models import Payment

WEBHOOK_SECRET = "whsec_pruebas"

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


def _hoy():
    return timezone.localdate()


def _pedido_habitacion(room, *, dias=10, noches=2, cantidad=1, huespedes=None):
    llegada = _hoy() + timedelta(days=dias)
    return {
        "producto_id": room.product_id,
        "fecha_inicio": llegada.isoformat(),
        "fecha_fin": (llegada + timedelta(days=noches)).isoformat(),
        "cantidad": cantidad,
        "huespedes": huespedes or cantidad,
    }


def _session_id(booking_id: int) -> str:
    return Payment.objects.get(booking_id=booking_id).reference


def _webhook(event_type: str, session_id: str, payment_status="paid", secret=WEBHOOK_SECRET):
    payload = json.dumps(
        {
            "id": "evt_test",
            "object": "event",
            "type": event_type,
            "data": {"object": {"id": session_id, "object": "checkout.session", "payment_status": payment_status}},
        }
    )
    timestamp = int(time.time())
    signature = hmac.new(secret.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()
    return APIClient().post(
        "/api/v1/pagos/stripe/webhook/",
        data=payload,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={signature}",
    )


def _vencer(booking_id: int) -> None:
    """Lleva la reserva al pasado: la base exige vencimiento posterior a la creacion."""
    hace_una_hora = timezone.now() - timedelta(hours=1)
    hace_un_minuto = timezone.now() - timedelta(minutes=1)
    InventoryLock.objects.filter(booking_id=booking_id).update(
        created_at=hace_una_hora, expires_at=hace_un_minuto
    )
    Booking.objects.filter(id=booking_id).update(created_at=hace_una_hora, expires_at=hace_un_minuto)
