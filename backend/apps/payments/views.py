import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings import services as bookings
from apps.tenancy import subscriptions

from . import gateway

logger = logging.getLogger(__name__)


class StripeWebhookView(APIView):
    """Avisos de Stripe. Solo se confia en el evento si la firma es valida.

    Responde 200 a todo evento firmado, aunque no le interese o no reconozca la
    sesion: un error haria que Stripe reintente durante dias sin sentido.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(exclude=True)
    def post(self, request):
        try:
            event = gateway.parse_webhook(request.body, request.headers.get("Stripe-Signature"))
        except ValueError as exc:
            logger.warning("Webhook de Stripe rechazado: %s", exc)
            return Response({"recibido": False}, status=400)

        session = event["data"]["object"]
        # La misma cuenta de Stripe cobra reservas y planes de empresa; la
        # metadata de la sesion dice cual es.
        is_plan = (session.get("metadata") or {}).get("tipo") == "SUSCRIPCION"
        if event["type"] in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            if session.get("payment_status") in ("paid", "no_payment_required"):
                if is_plan:
                    subscriptions.confirm_payment(session["id"])
                else:
                    bookings.confirm_paid_session(session["id"])
        elif event["type"] in ("checkout.session.expired", "checkout.session.async_payment_failed"):
            if is_plan:
                subscriptions.void_payment(session["id"])
            else:
                bookings.expire_session(session["id"])
        return Response({"recibido": True})


PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SITUR-SMART</title>
<style>
body{{margin:0;font-family:system-ui,sans-serif;background:#f0fdfb;color:#111827;
display:flex;min-height:100vh;align-items:center;justify-content:center;padding:24px}}
main{{max-width:420px;text-align:center;background:#fff;border-radius:20px;padding:32px 24px;
box-shadow:0 10px 30px rgba(15,118,110,.12)}}
h1{{font-size:22px;margin:12px 0 8px}}p{{color:#4b5563;line-height:1.5}}
.icono{{font-size:48px}}.codigo{{font-weight:700;color:#0f766e}}
.boton{{display:inline-block;margin-top:8px;padding:12px 22px;border-radius:12px;background:#0f766e;
color:#fff;font-weight:700;text-decoration:none}}
</style></head><body><main>
<div class="icono">{icon}</div><h1>{title}</h1><p>{message}</p>
<p class="codigo">{code}</p>
{back}
</main>{script}</body></html>"""


def _deep_link(booking_id: str, result: str) -> str | None:
    """situr-smart://app/reserva/12?pago=exito: la app abre esa reserva."""
    if not booking_id.isdigit():
        return None
    outcome = "exito" if result == "exito" else "cancelado"
    return f"{settings.APP_DEEP_LINK.rstrip('/')}/reserva/{booking_id}?pago={outcome}"


@csrf_exempt
def stripe_return(request):
    """Pagina a la que Stripe devuelve al turista. No confirma nada: eso lo
    hace el webhook o la conciliacion al abrir la reserva en la app.

    Con el id de la reserva intenta volver sola a la app (la pestaña de pago se
    cierra porque la app se abre en singleTask) y deja un boton por si el
    navegador no lo permite sin un toque.
    """
    code = escape(request.GET.get("reserva", ""))[:60]
    result = request.GET.get("resultado")
    link = _deep_link(request.GET.get("id", ""), result)
    if link:
        back = f'<a class="boton" href="{escape(link)}">Volver a SITUR-SMART</a>'
        script = f"<script>setTimeout(function(){{window.location.replace({json.dumps(link)});}},400);</script>"
    else:
        back = "<p>Ya puedes cerrar esta ventana y volver a la app SITUR-SMART.</p>"
        script = ""
    if result == "exito":
        body = PAGE.format(
            icon="✅",
            title="¡Pago recibido!",
            message="Estamos confirmando tu reserva. Te llevamos a la app para ver tu voucher.",
            code=code, back=back, script=script,
        )
    else:
        body = PAGE.format(
            icon="↩️",
            title="Pago no completado",
            message="No se cobró nada. Tu cupo queda apartado unos minutos por si quieres intentarlo de nuevo.",
            code=code, back=back, script=script,
        )
    return HttpResponse(body)
