"""Recordatorios previos al inicio de reservas confirmadas.

El cron corre cada diez minutos. Las ventanas toleran ese intervalo y la tabla
de entregas garantiza que reintentos o dos procesos concurrentes no dupliquen
el aviso en la bandeja ni el push de Firebase.
"""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Min
from django.utils import timezone

from apps.bookings.models import Booking, BookingState

from .models import BookingReminderDelivery, Notification
from .services import notify

WINDOW = timedelta(minutes=12)
REMINDERS = (
    (timedelta(hours=24), Notification.Kind.BOOKING_REMINDER_24H, "mañana"),
    (timedelta(hours=2), Notification.Kind.BOOKING_REMINDER_2H, "en aproximadamente 2 horas"),
)


def _send_once(*, booking: Booking, kind: str, when_text: str, starts_at) -> bool:
    try:
        with transaction.atomic():
            _, created = BookingReminderDelivery.objects.get_or_create(
                booking=booking, kind=kind
            )
            if not created:
                return False
            detail = booking.details.select_related("slot__product").order_by("slot__start").first()
            product = detail.slot.product.name if detail else "tu actividad"
            local_start = timezone.localtime(starts_at)
            notify(
                user=booking.order.customer.user,
                kind=kind,
                title=f"Tu reserva comienza {when_text}",
                message=(
                    f"{product} comienza el {local_start:%d/%m/%Y} a las "
                    f"{local_start:%H:%M}. Tu código es {booking.code}."
                ),
                data={
                    "reserva_id": booking.id,
                    "codigo": booking.code,
                    "inicio": starts_at.isoformat(),
                },
            )
    except IntegrityError:
        return False
    return True


def process_due(*, now=None) -> int:
    now = now or timezone.now()
    sent = 0
    for offset, kind, when_text in REMINDERS:
        target = now + offset
        bookings = (
            Booking.objects.filter(status=BookingState.CONFIRMED)
            .annotate(service_start=Min("details__slot__start"))
            .filter(
                service_start__gte=target - WINDOW,
                service_start__lt=target + WINDOW,
            )
            .select_related("order__customer__user")
        )
        for booking in bookings.iterator():
            if _send_once(
                booking=booking,
                kind=kind,
                when_text=when_text,
                starts_at=booking.service_start,
            ):
                sent += 1
    return sent
