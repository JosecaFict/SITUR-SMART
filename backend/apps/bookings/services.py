"""Reservas del turista: cupos automaticos, bloqueo mientras paga y estados.

Cupos automaticos
    Nadie carga disponibilidad a mano. El cupo de un dia sale del producto:
    una habitacion ofrece ``cantidad_habitaciones`` por noche; un tour,
    experiencia, atraccion, restaurante o paquete, ``capacidad_maxima``
    personas por dia. La fila de ``disponibilidad`` se crea la primera vez que
    alguien reserva esa fecha, porque ``reserva_detalle`` la exige como FK. Una
    empresa puede cerrar un dia marcando ``cerrado``.

Ocupacion de un cupo
    Lo confirmado (detalle de reservas CONFIRMADA, PAGO_PARCIAL o COMPLETADA)
    mas lo apartado (bloqueos ACTIVO que todavia no vencen). Un bloqueo vencido
    deja de contar solo por la hora, sin esperar a que nadie lo limpie.

Concurrencia
    Las filas de disponibilidad se toman con SELECT ... FOR UPDATE en orden de
    fecha: dos turistas que reservan la misma noche se ponen en fila y el
    segundo ve el cupo que dejo el primero. Nunca se vende de mas.

Pago
    La reserva nace CREADA con su bloqueo y un pago PENDIENTE. Stripe confirma
    por webhook; si el webhook no llega (desarrollo local, panel mal
    configurado), consultar la reserva concilia contra Stripe.
"""

import secrets
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core import signing
from django.db import connection, transaction
from django.db.models import Prefetch, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ValidationError

from apps.accounts.models import CustomerProfile
from apps.catalog.models import ROOM_PRODUCT_CODE, Availability, TourismProduct
from apps.payments import gateway
from apps.payments.models import Payment

from . import events
from .models import (
    Booking,
    BookingDetail,
    BookingState,
    BookingStatusHistory,
    InventoryLock,
    Order,
    OrderState,
)

BOOKABLE_CODES = frozenset({ROOM_PRODUCT_CODE, "TOUR", "EXPERIENCIA", "ATRACCION", "RESTAURANTE", "PAQUETE"})
OCCUPYING_STATES = (BookingState.CONFIRMED, BookingState.PARTIAL, BookingState.COMPLETED)
MAX_NIGHTS = 30
MAX_DAYS_AHEAD = 365
VOUCHER_SALT = "situr.voucher"

# Cada estado de la reserva y el que toma su orden (una reserva por orden).
ORDER_STATE_FOR = {
    BookingState.CREATED: OrderState.CREATED,
    BookingState.PARTIAL: OrderState.PARTIAL,
    BookingState.CONFIRMED: OrderState.CONFIRMED,
    BookingState.CANCELLED: OrderState.CANCELLED,
    BookingState.EXPIRED: OrderState.EXPIRED,
    BookingState.COMPLETED: OrderState.COMPLETED,
}


class NoCapacity(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Ya no quedan cupos suficientes para esa fecha."
    default_code = "sin_cupo"


def _zone() -> ZoneInfo:
    return ZoneInfo(settings.TIME_ZONE)


def _slot_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=_zone())


# --- Cotizacion ----------------------------------------------------------------


@dataclass
class Quote:
    product: TourismProduct
    is_room: bool
    days: list[date]
    quantity: int
    guests: int | None
    capacity: int
    unit_price: Decimal

    @property
    def total(self) -> Decimal:
        return self.unit_price * self.quantity * len(self.days)

    @property
    def start(self) -> date:
        return self.days[0]

    @property
    def end(self) -> date:
        """Salida en una habitacion; el mismo dia en lo demas."""
        return self.days[-1] + timedelta(days=1) if self.is_room else self.days[0]


def _bookable_product(product_id: int) -> TourismProduct:
    product = (
        TourismProduct.objects.select_related(
            "tenant", "product_type", "currency", "city", "room__establishment__product"
        )
        .filter(
            id=product_id,
            status=TourismProduct.Status.PUBLISHED,
            tenant__status="ACTIVO",
            product_type__code__in=BOOKABLE_CODES,
        )
        .first()
    )
    if product is None:
        raise NotFound("Este producto no se puede reservar.")
    if product.product_type.code == ROOM_PRODUCT_CODE:
        hotel = product.room.establishment.product
        if hotel.status != TourismProduct.Status.PUBLISHED:
            raise NotFound("Este producto no se puede reservar.")
    return product


def build_quote(
    *, product_id: int, start: date, end: date | None, quantity: int, guests: int | None
) -> Quote:
    """Valida lo pedido contra el producto. No mira la ocupacion."""
    product = _bookable_product(product_id)
    is_room = product.product_type.code == ROOM_PRODUCT_CODE
    today = timezone.localdate()

    if start < today:
        raise ValidationError({"fecha_inicio": "Elige una fecha desde hoy en adelante."})
    if start > today + timedelta(days=MAX_DAYS_AHEAD):
        raise ValidationError({"fecha_inicio": "Solo se puede reservar hasta un año adelante."})
    if product.base_price is None or product.base_price <= 0:
        raise ValidationError({"producto_id": "Este producto todavía no tiene precio publicado."})

    if is_room:
        room = product.room
        if end is None or end <= start:
            raise ValidationError({"fecha_fin": "La salida debe ser posterior a la llegada."})
        nights = (end - start).days
        if nights > MAX_NIGHTS:
            raise ValidationError({"fecha_fin": f"Se puede reservar hasta {MAX_NIGHTS} noches seguidas."})
        if quantity > room.quantity:
            raise ValidationError(
                {"cantidad": f"Este hospedaje tiene {room.quantity} habitaciones de este tipo."}
            )
        if guests is None:
            raise ValidationError({"huespedes": "Indica cuántos huéspedes se alojan."})
        if guests < quantity:
            raise ValidationError({"huespedes": "Cada habitación necesita al menos un huésped."})
        per_room = product.max_capacity
        if guests > quantity * per_room:
            needed = -(-guests // per_room)
            raise ValidationError(
                {"huespedes": f"Para {guests} huéspedes necesitas al menos {needed} habitaciones de este tipo."}
            )
        days = [start + timedelta(days=offset) for offset in range(nights)]
        capacity = room.quantity
    else:
        if quantity > product.max_capacity:
            raise ValidationError({"cantidad": f"El máximo es de {product.max_capacity} personas."})
        days = [start]
        guests = None
        capacity = product.max_capacity

    return Quote(
        product=product,
        is_room=is_room,
        days=days,
        quantity=quantity,
        guests=guests,
        capacity=capacity,
        unit_price=product.base_price,
    )


def _occupied(slot_ids: list[int], *, exclude_booking_id: int | None = None) -> dict[int, int]:
    """Unidades tomadas en cada cupo: confirmadas mas apartadas vigentes."""
    used: dict[int, int] = defaultdict(int)
    confirmed = BookingDetail.objects.filter(slot_id__in=slot_ids, booking__status__in=OCCUPYING_STATES)
    held = InventoryLock.objects.filter(
        slot_id__in=slot_ids, status=InventoryLock.State.ACTIVE, expires_at__gt=timezone.now()
    )
    if exclude_booking_id is not None:
        confirmed = confirmed.exclude(booking_id=exclude_booking_id)
        held = held.exclude(booking_id=exclude_booking_id)
    for queryset in (confirmed, held):
        for row in queryset.values("slot_id").annotate(total=Sum("quantity")):
            used[row["slot_id"]] += row["total"]
    return used


def availability(quote: Quote) -> int:
    """Cuantas unidades quedan libres en el dia mas lleno del pedido.

    Solo lee: no crea cupos ni aparta nada. Un dia sin fila de disponibilidad
    todavia no tiene reservas, asi que esta entero.
    """
    slots = {
        slot.start: slot
        for slot in Availability.objects.filter(
            product=quote.product, start__in=[_slot_start(day) for day in quote.days]
        )
    }
    used = _occupied([slot.id for slot in slots.values()])
    remaining = quote.capacity
    for day in quote.days:
        slot = slots.get(_slot_start(day))
        if slot is None:
            continue
        free = 0 if slot.closed else quote.capacity - used.get(slot.id, 0)
        remaining = min(remaining, free)
    return max(remaining, 0)


# --- Crear --------------------------------------------------------------------


def _code(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def _lock_slots(quote: Quote) -> list[Availability]:
    """Crea los cupos que falten y los bloquea en orden de fecha."""
    product = quote.product
    starts = [_slot_start(day) for day in quote.days]
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO disponibilidad (id_producto, id_tenant, inicio, fin, cupo_total)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id_producto, inicio) DO NOTHING
            """,
            [
                (product.id, product.tenant_id, start, _slot_start(day + timedelta(days=1)), quote.capacity)
                for day, start in zip(quote.days, starts, strict=True)
            ],
        )
    slots = list(
        Availability.objects.select_for_update().filter(product=product, start__in=starts).order_by("start")
    )
    # El cupo sigue al producto: si la empresa agrego habitaciones, la fila se pone al dia.
    stale = [slot.id for slot in slots if slot.total_capacity != quote.capacity]
    if stale:
        Availability.objects.filter(id__in=stale).update(total_capacity=quote.capacity)
        for slot in slots:
            slot.total_capacity = quote.capacity
    return slots


def _check_capacity(
    slots: list[Availability], *, quantity: int, is_room: bool, exclude_booking_id: int | None = None
) -> None:
    used = _occupied([slot.id for slot in slots], exclude_booking_id=exclude_booking_id)
    for slot in slots:
        day = slot.start.astimezone(_zone()).date()
        free = 0 if slot.closed else slot.total_capacity - used.get(slot.id, 0)
        if free < quantity:
            when = day.strftime("%d/%m/%Y")
            if free <= 0:
                raise NoCapacity(f"No quedan cupos para el {when}.")
            unit = "habitaciones" if is_room else "lugares"
            raise NoCapacity(f"Para el {when} solo quedan {free} {unit}.")


def _transition(booking: Booking, new_status: str, *, user=None, reason: str | None = None) -> None:
    previous = booking.status
    if previous == new_status:
        return
    booking.status = new_status
    booking.save(update_fields=["status", "updated_at"])
    Order.objects.filter(id=booking.order_id).update(
        status=ORDER_STATE_FOR[new_status], updated_at=timezone.now()
    )
    BookingStatusHistory.objects.create(
        booking=booking, user=user, previous_status=previous, new_status=new_status, reason=reason
    )
    # Avisos y correo solo si la transaccion se confirma.
    actor_id = getattr(user, "id", None)
    transaction.on_commit(lambda: events.booking_changed(booking.id, new_status, actor_id))


def _description(quote: Quote) -> str:
    product = quote.product
    if quote.is_room:
        hotel = product.room.establishment.product.name
        nights = len(quote.days)
        return f"{hotel} - {product.name} ({nights} {'noche' if nights == 1 else 'noches'})"
    return f"{product.name} - {quote.start.strftime('%d/%m/%Y')}"


@dataclass
class CreatedBooking:
    booking: Booking
    checkout_url: str | None


def create_booking(
    *,
    user,
    product_id: int,
    start: date,
    end: date | None,
    quantity: int,
    guests: int | None,
    success_url: str,
    cancel_url: str,
    idempotency_key: str | None = None,
) -> CreatedBooking:
    """Aparta el cupo, registra la reserva y abre el pago en Stripe.

    Con la misma ``idempotency_key`` (cabecera Idempotency-Key) devuelve la
    reserva ya creada en vez de crear otra: un doble toque o un reintento por
    mala conexion no reserva dos veces.
    """
    key = f"{user.id}:{idempotency_key}"[:100] if idempotency_key else f"{user.id}:{secrets.token_hex(16)}"
    existing = Payment.objects.select_related("booking").filter(idempotency_key=key, payer=user).first()
    if existing is not None:
        session = gateway.retrieve_session(existing.reference) if existing.reference else None
        return CreatedBooking(booking=existing.booking, checkout_url=session.url if session else None)

    if not gateway.is_configured():
        raise gateway.PaymentUnavailable()

    quote = build_quote(product_id=product_id, start=start, end=end, quantity=quantity, guests=guests)
    expires_at = timezone.now() + timedelta(minutes=settings.RESERVA_MINUTOS_PAGO)

    with transaction.atomic():
        slots = _lock_slots(quote)
        _check_capacity(slots, quantity=quote.quantity, is_room=quote.is_room)

        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        order = Order.objects.create(customer=profile, code=_code("ORD"))
        booking = Booking.objects.create(
            order=order,
            tenant_id=quote.product.tenant_id,
            currency_id=quote.product.currency_id,
            code=_code("RES"),
            expires_at=expires_at,
            guests=quote.guests,
        )
        BookingDetail.objects.bulk_create(
            [
                BookingDetail(
                    booking=booking,
                    tenant_id=booking.tenant_id,
                    slot=slot,
                    quantity=quote.quantity,
                    unit_price=quote.unit_price,
                )
                for slot in slots
            ]
        )
        InventoryLock.objects.bulk_create(
            [
                InventoryLock(
                    slot=slot,
                    booking=booking,
                    tenant_id=booking.tenant_id,
                    quantity=quote.quantity,
                    expires_at=expires_at,
                )
                for slot in slots
            ]
        )
        BookingStatusHistory.objects.create(
            booking=booking, user=user, previous_status=None, new_status=BookingState.CREATED
        )
        payment = Payment.objects.create(
            booking=booking,
            payer=user,
            currency_id=booking.currency_id,
            amount=quote.total,
            method=Payment.Method.CARD,
            provider=gateway.PROVIDER,
            idempotency_key=key,
        )

    # Fuera de la transaccion: la llamada a Stripe no debe retener los cupos
    # bloqueados. Si falla, la reserva se libera enseguida.
    try:
        session = gateway.create_checkout_session(
            reference=booking.code,
            description=_description(quote),
            amount=quote.total,
            currency=quote.product.currency.iso_code,
            customer_email=user.email,
            success_url=success_url.replace("{CODIGO}", booking.code),
            cancel_url=cancel_url.replace("{CODIGO}", booking.code),
            expires_at=expires_at,
            idempotency_key=key,
            metadata={"reserva": booking.code, "reserva_id": str(booking.id)},
        )
    except gateway.PaymentUnavailable:
        _release(booking, BookingState.CANCELLED, reason="No se pudo iniciar el pago.")
        raise

    payment.reference = session.id
    payment.save(update_fields=["reference"])
    return CreatedBooking(booking=booking, checkout_url=session.url)


# --- Cambios de estado ----------------------------------------------------------


def _release(booking: Booking, new_status: str, *, user=None, reason: str | None = None) -> None:
    """Cancela o vence una reserva sin pagar y devuelve su cupo."""
    lock_status = (
        InventoryLock.State.RELEASED if new_status == BookingState.CANCELLED else InventoryLock.State.EXPIRED
    )
    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(id=booking.id)
        if booking.status != BookingState.CREATED:
            return
        InventoryLock.objects.filter(booking=booking, status=InventoryLock.State.ACTIVE).update(status=lock_status)
        Payment.objects.filter(booking=booking, status=Payment.State.PENDING).update(
            status=Payment.State.VOIDED, processed_at=timezone.now()
        )
        _transition(booking, new_status, user=user, reason=reason)


def confirm_paid_session(session_id: str) -> Booking | None:
    """Stripe cobro la sesion: aprueba el pago y confirma la reserva.

    Idempotente: Stripe puede avisar varias veces y la conciliacion tambien
    puede llegar primero. Si la reserva ya se habia liberado (pago a ultimo
    segundo), se confirma igual cuando el cupo sigue libre.
    """
    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update()
            .filter(provider=gateway.PROVIDER, reference=session_id)
            .first()
        )
        if payment is None:
            return None
        booking = Booking.objects.select_for_update().get(id=payment.booking_id)
        if payment.status == Payment.State.APPROVED:
            return booking

        payment.status = Payment.State.APPROVED
        payment.processed_at = timezone.now()
        payment.save(update_fields=["status", "processed_at"])

        if booking.status == BookingState.CREATED:
            InventoryLock.objects.filter(booking=booking, status=InventoryLock.State.ACTIVE).update(
                status=InventoryLock.State.CONSUMED
            )
            _transition(booking, BookingState.CONFIRMED, reason="Pago aprobado por Stripe.")
        elif booking.status in (BookingState.EXPIRED, BookingState.CANCELLED):
            slots = list(
                Availability.objects.select_for_update()
                .filter(booking_details__booking=booking)
                .order_by("start")
            )
            detail = booking.details.select_related("slot__product__product_type").first()
            try:
                _check_capacity(
                    slots,
                    quantity=detail.quantity,
                    is_room=detail.slot.product.product_type.code == ROOM_PRODUCT_CODE,
                    exclude_booking_id=booking.id,
                )
            except NoCapacity:
                _record(booking, "Pago recibido sin cupo disponible: requiere reembolso.")
                transaction.on_commit(lambda: events.payment_needs_review(booking.id))
            else:
                _transition(booking, BookingState.CONFIRMED, reason="Pago aprobado después del vencimiento.")
        return booking


def _record(booking: Booking, reason: str) -> None:
    BookingStatusHistory.objects.create(
        booking=booking, previous_status=None, new_status=booking.status, reason=reason
    )


def expire_session(session_id: str) -> Booking | None:
    """Stripe cerro la sesion sin cobro: el cupo vuelve a estar libre."""
    payment = Payment.objects.select_related("booking").filter(
        provider=gateway.PROVIDER, reference=session_id
    ).first()
    if payment is None:
        return None
    _release(payment.booking, BookingState.EXPIRED, reason="Venció el plazo de pago.")
    payment.booking.refresh_from_db()
    return payment.booking


def sync(booking: Booking) -> Booking:
    """Pone al dia una reserva sin esperar al webhook ni a una tarea programada.

    * CREADA: pregunta a Stripe si ya se pago o si la sesion vencio; sin
      respuesta, la vence por la hora.
    * CONFIRMADA cuyo ultimo dia ya paso: COMPLETADA.
    """
    if booking.status == BookingState.CREATED:
        payment = booking.payments.filter(status=Payment.State.PENDING).exclude(reference=None).first()
        session = gateway.retrieve_session(payment.reference) if payment else None
        if session is not None and session.paid:
            confirm_paid_session(session.id)
        elif (session is not None and session.status == "expired") or (
            booking.expires_at and booking.expires_at <= timezone.now()
        ):
            _release(booking, BookingState.EXPIRED, reason="Venció el plazo de pago.")
        booking.refresh_from_db()
    elif booking.status == BookingState.CONFIRMED:
        last = booking.details.order_by("-slot__start").values_list("slot__start", flat=True).first()
        if last is not None and last.astimezone(_zone()).date() < timezone.localdate():
            _transition(booking, BookingState.COMPLETED, reason="El servicio ya se prestó.")
    return booking


def cancel_booking(*, user, booking_id: int) -> Booking:
    """El turista desiste antes de pagar. Una reserva pagada no se cancela aqui."""
    booking = sync(get_customer_booking(user=user, booking_id=booking_id))
    if booking.status != BookingState.CREATED:
        if booking.status in OCCUPYING_STATES:
            raise ValidationError(
                "Esta reserva ya está pagada. Para cancelarla comunícate con la empresa."
            )
        raise ValidationError("Esta reserva ya no está activa.")
    payment = booking.payments.filter(status=Payment.State.PENDING).exclude(reference=None).first()
    if payment is not None:
        gateway.expire_session(payment.reference)
    _release(booking, BookingState.CANCELLED, user=user, reason="Cancelada por el turista antes de pagar.")
    booking.refresh_from_db()
    return booking


def checkout_url(*, user, booking_id: int) -> str:
    """Enlace para retomar el pago de una reserva pendiente."""
    booking = sync(get_customer_booking(user=user, booking_id=booking_id))
    if booking.status != BookingState.CREATED:
        raise ValidationError("Esta reserva ya no está pendiente de pago.")
    payment = booking.payments.filter(status=Payment.State.PENDING).exclude(reference=None).first()
    session = gateway.retrieve_session(payment.reference) if payment else None
    if session is None or session.status != "open" or not session.url:
        raise gateway.PaymentUnavailable()
    return session.url


def expire_overdue() -> int:
    """Concilia las reservas pendientes cuyo plazo ya vencio. Para cron."""
    overdue = Booking.objects.filter(status=BookingState.CREATED, expires_at__lte=timezone.now())
    count = 0
    for booking in overdue:
        if sync(booking).status != BookingState.CREATED:
            count += 1
    return count


# --- Consultas -----------------------------------------------------------------


def _customer_bookings(user):
    return (
        Booking.objects.filter(order__customer__user=user)
        .select_related("tenant", "currency", "order")
        .prefetch_related(
            Prefetch(
                "details",
                queryset=BookingDetail.objects.select_related(
                    "slot__product__product_type",
                    "slot__product__city",
                    "slot__product__room__establishment__product",
                ).order_by("slot__start"),
            ),
            Prefetch("payments", queryset=Payment.objects.order_by("-created_at")),
        )
        .order_by("-created_at", "-id")
    )


def get_customer_booking(*, user, booking_id: int) -> Booking:
    booking = _customer_bookings(user).filter(id=booking_id).first()
    if booking is None:
        raise NotFound("Reserva no encontrada.")
    return booking


def list_customer_bookings(*, user) -> list[Booking]:
    bookings = list(_customer_bookings(user))
    # Pocas por turista: se ponen al dia antes de mostrarlas.
    stale = [booking.id for booking in bookings if _needs_sync(booking)]
    for booking in bookings:
        if booking.id in stale:
            sync(booking)
    return list(_customer_bookings(user)) if stale else bookings


def _needs_sync(booking: Booking) -> bool:
    if booking.status == BookingState.CREATED:
        return True
    if booking.status == BookingState.CONFIRMED:
        details = list(booking.details.all())
        return bool(details) and details[-1].slot.start.astimezone(_zone()).date() < timezone.localdate()
    return False


def voucher_token(booking: Booking) -> str:
    """Contenido del QR: firmado, asi una captura editada no pasa por valida."""
    return signing.dumps({"r": booking.id, "c": booking.code}, salt=VOUCHER_SALT, compress=True)


def read_voucher(token: str) -> dict:
    """Valida un QR leido. Levanta signing.BadSignature si fue alterado."""
    return signing.loads(token, salt=VOUCHER_SALT)
