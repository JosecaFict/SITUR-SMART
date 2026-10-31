"""Compra atómica de todos los componentes de un paquete personalizado."""

import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import CustomerProfile
from apps.accounts.security import require_verified_email
from apps.bookings import services as bookings
from apps.bookings.models import (
    Booking,
    BookingDetail,
    BookingState,
    BookingStatusHistory,
    InventoryLock,
    Order,
)
from apps.catalog.models import TourismProduct
from apps.payments import gateway
from apps.payments.models import Payment

from .models import PackagePurchase, PackagePurchaseAllocation
from .services import _configuration, _values, owned_package

PACKAGE_PROVIDER = "STRIPE_PAQUETE"


def _payment_key(purchase_key: str, booking_id: int) -> str:
    return f"{purchase_key}:{booking_id}"[:100]


def _session_reference(payment: Payment) -> str | None:
    try:
        return payment.booking.package_allocation.purchase.provider_reference
    except PackagePurchaseAllocation.DoesNotExist:
        return payment.reference


def create_purchase(
    *, user, package_id: int, success_url: str, cancel_url: str,
    policies_accepted: bool, billing_name: str | None,
    billing_tax_id: str | None, idempotency_key: str | None,
) -> PackagePurchase:
    if not policies_accepted:
        raise ValidationError({"acepta_politicas": "Debes aceptar las condiciones de todos los servicios."})
    if not gateway.is_configured():
        raise gateway.PaymentUnavailable()
    require_verified_email(user)
    key = f"paquete:{user.id}:{idempotency_key or secrets.token_hex(16)}"[:100]
    existing = PackagePurchase.objects.filter(idempotency_key=key, package__user=user).first()
    if existing:
        session = gateway.retrieve_session(existing.provider_reference) if existing.provider_reference else None
        existing.checkout_url = session.url if session else None
        return existing
    expires_at = timezone.now() + timedelta(minutes=settings.RESERVA_MINUTOS_PAGO)

    with transaction.atomic():
        package = owned_package(user, package_id, lock=True)
        components = list(package.components.select_related("product", "departure").order_by("product_id", "id"))
        if not components:
            raise ValidationError({"componentes": "Agrega al menos un servicio."})
        if hasattr(package, "purchase"):
            raise ValidationError("Este paquete ya tiene una compra asociada.")
        product_ids = sorted({item.product_id for item in components})
        list(TourismProduct.objects.select_for_update().filter(id__in=product_ids).order_by("id"))
        quotes = [(item, _configuration(package, _values(item), exclude_id=item.id)) for item in components]
        currency_ids = {quote.product.currency_id for _, quote in quotes}
        if len(currency_ids) != 1:
            raise ValidationError("Todos los servicios deben usar la misma moneda.")
        locked = []
        for _, quote in quotes:
            slots = bookings._lock_slots(quote)
            bookings._check_capacity(slots, quantity=quote.quantity, is_room=quote.is_room)
            locked.append((quote, slots))

        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        order = Order.objects.create(customer=profile, code=bookings._code("ORD"))
        purchase = PackagePurchase.objects.create(
            package=package, order=order, currency_id=next(iter(currency_ids)),
            status=PackagePurchase.Status.CREATED,
            original_amount=sum((quote.total for _, quote in quotes), Decimal("0.00")),
            discount_amount=Decimal("0.00"),
            final_amount=sum((quote.total for _, quote in quotes), Decimal("0.00")),
            provider=gateway.PROVIDER, idempotency_key=key, expires_at=expires_at,
        )
        for quote, slots in locked:
            booking = Booking.objects.create(
                order=order, tenant_id=quote.product.tenant_id,
                currency_id=quote.product.currency_id, code=bookings._code("RES"),
                expires_at=expires_at, guests=quote.guests,
                original_amount=quote.total, discount_amount=Decimal("0.00"),
                final_amount=quote.total,
                cancellation_policy_snapshot=bookings.cancellation_policy_snapshot(
                    quote.product, source="CUSTOM_PACKAGE"
                ),
                policy_accepted_at=timezone.now(), billing_name=billing_name,
                billing_tax_id=billing_tax_id,
            )
            BookingDetail.objects.bulk_create([
                BookingDetail(booking=booking, tenant_id=booking.tenant_id, slot=slot,
                              quantity=quote.quantity, unit_price=quote.unit_price)
                for slot in slots
            ])
            InventoryLock.objects.bulk_create([
                InventoryLock(slot=slot, booking=booking, tenant_id=booking.tenant_id,
                              quantity=quote.quantity, expires_at=expires_at)
                for slot in slots
            ])
            BookingStatusHistory.objects.create(
                booking=booking, user=user, previous_status=None, new_status=BookingState.CREATED
            )
            PackagePurchaseAllocation.objects.create(
                purchase=purchase, booking=booking, original_amount=quote.total,
                discount_amount=Decimal("0.00"), final_amount=quote.total,
            )
            Payment.objects.create(
                booking=booking, payer=user, currency_id=booking.currency_id,
                amount=quote.total, method=Payment.Method.CARD,
                provider=PACKAGE_PROVIDER, idempotency_key=_payment_key(key, booking.id),
            )

    try:
        session = gateway.create_checkout_session(
            reference=order.code, description=f"Paquete {package.name}",
            amount=purchase.final_amount, currency=purchase.currency.iso_code,
            customer_email=user.email,
            success_url=success_url.replace("{ID}", str(purchase.id)),
            cancel_url=cancel_url.replace("{ID}", str(purchase.id)),
            expires_at=expires_at, idempotency_key=key,
            metadata={"tipo": "PAQUETE_PERSONALIZADO", "compra_paquete_id": str(purchase.id)},
        )
    except gateway.PaymentUnavailable:
        expire_purchase(purchase.id, cancelled=True)
        raise
    PackagePurchase.objects.filter(id=purchase.id).update(provider_reference=session.id)
    for allocation in purchase.allocations.all():
        Payment.objects.filter(booking=allocation.booking).update(
            reference=f"{session.id}:{allocation.booking_id}"
        )
    purchase.provider_reference = session.id
    purchase.checkout_url = session.url
    return purchase


@transaction.atomic
def confirm_purchase(session_id: str) -> PackagePurchase | None:
    purchase = PackagePurchase.objects.select_for_update().filter(provider_reference=session_id).first()
    if purchase is None or purchase.status == PackagePurchase.Status.CONFIRMED:
        return purchase
    for allocation in purchase.allocations.select_related("booking"):
        booking = Booking.objects.select_for_update().get(id=allocation.booking_id)
        Payment.objects.filter(booking=booking, status=Payment.State.PENDING).update(
            status=Payment.State.APPROVED, processed_at=timezone.now()
        )
        InventoryLock.objects.filter(booking=booking, status=InventoryLock.State.ACTIVE).update(
            status=InventoryLock.State.CONSUMED
        )
        if booking.status == BookingState.CREATED:
            bookings._transition(booking, BookingState.CONFIRMED, reason="Pago consolidado del paquete aprobado.")
    purchase.status = PackagePurchase.Status.CONFIRMED
    purchase.save(update_fields=("status", "updated_at"))
    return purchase


@transaction.atomic
def expire_purchase(purchase_id: int, *, cancelled=False) -> PackagePurchase:
    purchase = PackagePurchase.objects.select_for_update().get(id=purchase_id)
    if purchase.status != PackagePurchase.Status.CREATED:
        return purchase
    state = BookingState.CANCELLED if cancelled else BookingState.EXPIRED
    for allocation in purchase.allocations.select_related("booking"):
        bookings._release(allocation.booking, state, reason="La compra consolidada no se completó.")
    purchase.status = PackagePurchase.Status.CANCELLED if cancelled else PackagePurchase.Status.EXPIRED
    purchase.save(update_fields=("status", "updated_at"))
    return purchase


def expire_session(session_id: str) -> PackagePurchase | None:
    purchase = PackagePurchase.objects.filter(provider_reference=session_id).first()
    return expire_purchase(purchase.id) if purchase else None


def cancellation_quote(*, user, purchase_id: int) -> dict:
    purchase = PackagePurchase.objects.filter(id=purchase_id, package__user=user).first()
    if purchase is None:
        raise ValidationError("Compra de paquete no encontrada.")
    if purchase.status != PackagePurchase.Status.CONFIRMED:
        raise ValidationError("Solo se puede cancelar un paquete pagado y confirmado.")
    items = []
    for allocation in purchase.allocations.select_related("booking__tenant"):
        quote = bookings.quote_paid_cancellation(user=user, booking_id=allocation.booking_id)
        items.append({
            "reserva_id": quote.booking_id,
            "empresa": allocation.booking.tenant.trade_name,
            "pagado": str(quote.paid_amount),
            "penalizacion": str(quote.penalty_amount),
            "reembolso": str(quote.refund_amount),
            "porcentaje_penalizacion": str(quote.penalty_percentage),
            "politica": quote.policy_name,
        })
    return {
        "compra_id": purchase.id,
        "pagado": str(sum((Decimal(item["pagado"]) for item in items), Decimal("0.00"))),
        "penalizacion": str(sum((Decimal(item["penalizacion"]) for item in items), Decimal("0.00"))),
        "reembolso": str(sum((Decimal(item["reembolso"]) for item in items), Decimal("0.00"))),
        "componentes": items,
    }


def cancel_purchase(*, user, purchase_id: int, reason: str, idempotency_key: str | None) -> dict:
    from apps.payments import refunds

    purchase = PackagePurchase.objects.filter(id=purchase_id, package__user=user).first()
    if purchase is None:
        raise ValidationError("Compra de paquete no encontrada.")
    if purchase.status == PackagePurchase.Status.REFUNDED:
        return {"compra_id": purchase.id, "estado": purchase.status, "reembolsos": []}
    if purchase.status != PackagePurchase.Status.CONFIRMED:
        raise ValidationError("La compra ya no se puede cancelar.")
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationError({"motivo": "Explica el motivo (al menos 5 caracteres)."})
    base_key = idempotency_key or f"cancelar-paquete-{purchase.id}"
    results = []
    for allocation in purchase.allocations.order_by("id"):
        cancellation, refund = refunds.request_booking_cancellation(
            user=user, booking_id=allocation.booking_id, reason=reason,
            idempotency_key=f"{base_key}:{allocation.booking_id}",
        )
        results.append({
            "reserva_id": allocation.booking_id,
            "cancelacion_id": cancellation.id,
            "reembolso_id": refund.id if refund else None,
            "estado": refund.status if refund else "COMPLETADO",
            "monto": str(cancellation.refund_amount),
        })
    if all(item["estado"] == "COMPLETADO" for item in results):
        PackagePurchase.objects.filter(id=purchase.id).update(status=PackagePurchase.Status.REFUNDED)
        purchase.status = PackagePurchase.Status.REFUNDED
    return {"compra_id": purchase.id, "estado": purchase.status, "reembolsos": results}


def refresh_refund_status(booking_id: int) -> None:
    allocation = PackagePurchaseAllocation.objects.filter(booking_id=booking_id).select_related("purchase").first()
    if allocation is None:
        return
    purchase = allocation.purchase
    pending = purchase.allocations.exclude(
        booking__cancellation__refunds__status="COMPLETADO"
    ).exists()
    if not pending:
        PackagePurchase.objects.filter(id=purchase.id).update(status=PackagePurchase.Status.REFUNDED)
