"""Que se le avisa al turista cuando su reserva cambia de estado.

Se llama con ``transaction.on_commit``: nunca se avisa de algo que despues se
deshizo. El correo sale en un hilo aparte para no demorar al webhook de
Stripe; el HTML se arma antes, asi el hilo no toca la base.
"""

import logging
import threading
from datetime import date

from django.conf import settings
from django.utils.html import escape

from apps.accounts.brevo import send_email
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .models import Booking, BookingState

logger = logging.getLogger(__name__)

MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def _day(value: str) -> str:
    parsed = date.fromisoformat(value)
    return f"{parsed.day} {MONTHS[parsed.month - 1]} {parsed.year}"


def _summary(booking: Booking) -> dict:
    # Import diferido: el serializer importa los servicios, que importan este modulo.
    from .serializers import BookingSerializer

    data = BookingSerializer(booking).data
    product = data["producto"] or {}
    dates = data["fechas"] or {}
    amount = data["importe"]
    title = product.get("establecimiento") or product.get("nombre") or "tu reserva"
    if dates.get("noches"):
        nights = dates["noches"]
        when = f"{_day(dates['inicio'])} al {_day(dates['fin'])} ({nights} {'noche' if nights == 1 else 'noches'})"
    elif dates:
        when = _day(dates["inicio"])
    else:
        when = ""
    return {
        "code": data["codigo"],
        "title": title,
        "subtitle": product.get("nombre") if product.get("establecimiento") else None,
        "city": ", ".join(part for part in (product.get("localidad"), product.get("ciudad")) if part),
        "company": data["empresa"],
        "when": when,
        "quantity": f"{amount['cantidad']} {amount['unidad']}",
        "guests": data["huespedes"],
        "total": f"{data['moneda_simbolo']} {amount['total']}",
    }


def booking_changed(booking_id: int, new_status: str, actor_id: int | None = None) -> None:
    booking = (
        Booking.objects.select_related("order__customer__user", "currency", "tenant")
        .filter(id=booking_id)
        .first()
    )
    if booking is None:
        return
    customer = booking.order.customer.user
    info = _summary(booking)
    data = {"reserva_id": booking.id, "codigo": booking.code}

    if new_status == BookingState.CONFIRMED:
        notify(
            user=customer,
            kind=Notification.Kind.BOOKING_CONFIRMED,
            title="¡Reserva confirmada!",
            message=f"{info['title']} · {info['when']}. Tu código es {info['code']}.",
            data=data,
        )
        _send_later(
            to_email=customer.email,
            to_name=customer.get_full_name(),
            subject=f"Reserva confirmada {info['code']} - SITUR-SMART",
            html=confirmation_html(info, name=f"Hola {customer.first_names}"),
        )
    elif new_status == BookingState.EXPIRED:
        notify(
            user=customer,
            kind=Notification.Kind.BOOKING_EXPIRED,
            title="Tu reserva venció",
            message=(
                f"No se completó el pago de {info['title']} a tiempo. "
                "El cupo quedó libre y no se cobró nada."
            ),
            data=data,
        )
    elif new_status == BookingState.CANCELLED and actor_id is not None and actor_id != customer.id:
        # Si la cancela el propio turista no hace falta avisarle.
        notify(
            user=customer,
            kind=Notification.Kind.BOOKING_CANCELLED,
            title="Tu reserva fue cancelada",
            message=f"{info['title']} · {info['when']} fue cancelada por {info['company']}.",
            data=data,
        )


def payment_needs_review(booking_id: int) -> None:
    """Stripe cobro una reserva que ya habia vencido y su cupo se ocupo."""
    booking = Booking.objects.select_related("order__customer__user").filter(id=booking_id).first()
    if booking is None:
        return
    notify(
        user=booking.order.customer.user,
        kind=Notification.Kind.PAYMENT_ISSUE,
        title="Estamos revisando tu pago",
        message=(
            f"Recibimos el pago de la reserva {booking.code} cuando ya había vencido y el cupo "
            "ya no estaba libre. Te devolveremos el dinero; la empresa se comunicará contigo."
        ),
        data={"reserva_id": booking.id, "codigo": booking.code},
    )


def _send_later(**kwargs) -> None:
    def send() -> None:
        if not send_email(**kwargs):
            logger.info("No se envió el correo \"%s\" a %s.", kwargs["subject"], kwargs["to_email"])

    if getattr(settings, "CORREOS_EN_SEGUNDO_PLANO", True):
        threading.Thread(target=send, daemon=True).start()
    else:
        send()


def confirmation_html(info: dict, *, name: str) -> str:
    """Correo de reserva confirmada, con la misma identidad que el del OTP."""
    e = {key: escape(value) if isinstance(value, str) else value for key, value in info.items()}
    greeting = escape(name.strip())
    rows = [
        ("Código", f"<strong style=\"font-family: monospace; font-size: 16px; color: #0f766e;\">{e['code']}</strong>"),
        ("Fechas", e["when"]),
        ("Cantidad", e["quantity"]),
    ]
    if info.get("guests"):
        guests = info["guests"]
        rows.append(("Huéspedes", f"{guests} {'huésped' if guests == 1 else 'huéspedes'}"))
    rows += [("Lugar", e["city"]), ("Ofrecido por", e["company"]), ("Total pagado", f"<strong>{e['total']}</strong>")]
    table = "".join(
        f'<tr><td style="padding: 8px 0; color: #64748b; font-size: 13px; width: 40%;">{label}</td>'
        f'<td style="padding: 8px 0; color: #0f172a; font-size: 14px;">{value}</td></tr>'
        for label, value in rows
        if value
    )
    subtitle = f'<p style="margin: 2px 0 0 0; color: #475569; font-size: 14px;">{e["subtitle"]}</p>' if e.get("subtitle") else ""
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reserva confirmada - SITUR-SMART</title></head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; padding: 32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" style="max-width: 520px; background-color: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #e2e8f0;">
        <tr><td style="background: linear-gradient(135deg, #0d5c58 0%, #115e59 100%); padding: 28px 24px; text-align: center;">
          <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 800;">SITUR-SMART</h1>
          <p style="margin: 6px 0 0 0; color: #99f6e4; font-size: 13px;">Tu reserva está confirmada</p>
        </td></tr>
        <tr><td style="padding: 28px;">
          <p style="margin: 0 0 16px 0; color: #475569; font-size: 14px; line-height: 1.6;">
            {greeting}, recibimos tu pago. Estos son los datos de tu reserva:
          </p>
          <h2 style="margin: 0; color: #0f172a; font-size: 19px; font-weight: 700;">{e['title']}</h2>
          {subtitle}
          <table role="presentation" width="100%" style="margin-top: 16px; border-top: 1px solid #e2e8f0;">{table}</table>
          <p style="margin: 20px 0 0 0; color: #475569; font-size: 13px; line-height: 1.5;">
            Muestra tu código de reserva al llegar. También lo encuentras en la app, en <strong>Mis viajes</strong>.
          </p>
        </td></tr>
        <tr><td style="background-color: #f8fafc; padding: 18px 24px; text-align: center; border-top: 1px solid #e2e8f0;">
          <p style="margin: 0; color: #94a3b8; font-size: 11px;">© 2026 SITUR-SMART. Todos los derechos reservados.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""
