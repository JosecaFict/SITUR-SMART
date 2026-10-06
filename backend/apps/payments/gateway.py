"""Unico punto de contacto con Stripe.

Todo lo demas habla con estas funciones, asi las pruebas reemplazan la
pasarela sin tocar la red y un cambio de proveedor queda en un solo archivo.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

import stripe
from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)

PROVIDER = "STRIPE"


class PaymentUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Los pagos no están disponibles en este momento. Inténtalo más tarde."
    default_code = "pagos_no_disponibles"


@dataclass(frozen=True)
class CheckoutSession:
    id: str
    url: str | None
    # open, complete o expired.
    status: str
    # paid, unpaid o no_payment_required.
    payment_status: str

    @property
    def paid(self) -> bool:
        return self.status == "complete" and self.payment_status in ("paid", "no_payment_required")


def is_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def to_minor_units(amount: Decimal) -> int:
    """Bs 450.50 -> 45050. Stripe cobra en centavos."""
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _session(data) -> CheckoutSession:
    return CheckoutSession(
        id=data["id"],
        url=data.get("url"),
        status=data.get("status") or "open",
        payment_status=data.get("payment_status") or "unpaid",
    )


def create_checkout_session(
    *,
    reference: str,
    description: str,
    amount: Decimal,
    currency: str,
    customer_email: str | None,
    success_url: str,
    cancel_url: str,
    expires_at: datetime,
    idempotency_key: str,
    metadata: dict[str, str],
) -> CheckoutSession:
    if not is_configured():
        raise PaymentUnavailable()
    try:
        data = stripe.checkout.Session.create(
            api_key=settings.STRIPE_SECRET_KEY,
            idempotency_key=idempotency_key,
            mode="payment",
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": currency.lower(),
                        "unit_amount": to_minor_units(amount),
                        "product_data": {"name": description[:250]},
                    },
                }
            ],
            customer_email=customer_email or None,
            client_reference_id=reference,
            metadata=metadata,
            payment_intent_data={"metadata": metadata},
            success_url=success_url,
            cancel_url=cancel_url,
            expires_at=int(expires_at.timestamp()),
            locale="es",
        )
    except stripe.StripeError as exc:
        logger.warning("Stripe rechazo la sesion de Checkout de %s: %s", reference, exc)
        raise PaymentUnavailable() from exc
    return _session(data)


def retrieve_session(session_id: str) -> CheckoutSession | None:
    """La sesion tal como la ve Stripe, o None si no se pudo consultar."""
    if not is_configured():
        return None
    try:
        return _session(stripe.checkout.Session.retrieve(session_id, api_key=settings.STRIPE_SECRET_KEY))
    except stripe.StripeError as exc:
        logger.warning("No se pudo consultar la sesion %s: %s", session_id, exc)
        return None


def expire_session(session_id: str) -> None:
    """Cierra una sesion abierta para que ya no se pueda pagar. Sin errores."""
    if not is_configured():
        return
    try:
        stripe.checkout.Session.expire(session_id, api_key=settings.STRIPE_SECRET_KEY)
    except stripe.StripeError as exc:
        # Ya pagada o ya vencida: no hay nada que cerrar.
        logger.info("No se expiro la sesion %s: %s", session_id, exc)


def parse_webhook(payload: bytes, signature: str | None):
    """Evento verificado con STRIPE_WEBHOOK_SECRET.

    Levanta ValueError si falta el secreto, la firma no coincide o el cuerpo no
    es un evento valido: quien llama responde 400 y Stripe reintenta.
    """
    secret = settings.STRIPE_WEBHOOK_SECRET
    if not secret or not signature:
        raise ValueError("Falta la firma o el secreto del webhook.")
    try:
        return stripe.Webhook.construct_event(payload, signature, secret)
    except stripe.SignatureVerificationError as exc:
        raise ValueError("Firma de Stripe inválida.") from exc
