import logging

from django.http import HttpResponse
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings import services as bookings

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
        if event["type"] in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            if session.get("payment_status") in ("paid", "no_payment_required"):
                bookings.confirm_paid_session(session["id"])
        elif event["type"] in ("checkout.session.expired", "checkout.session.async_payment_failed"):
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
</style></head><body><main>
<div class="icono">{icon}</div><h1>{title}</h1><p>{message}</p>
<p class="codigo">{code}</p>
<p>Ya puedes cerrar esta ventana y volver a la app SITUR-SMART.</p>
</main></body></html>"""


@csrf_exempt
def stripe_return(request):
    """Pagina a la que Stripe devuelve al turista. No confirma nada: eso lo
    hace el webhook o la conciliacion al abrir la reserva en la app."""
    code = escape(request.GET.get("reserva", ""))[:60]
    if request.GET.get("resultado") == "exito":
        body = PAGE.format(
            icon="✅",
            title="¡Pago recibido!",
            message="Estamos confirmando tu reserva. En la app la verás en Mis viajes.",
            code=code,
        )
    else:
        body = PAGE.format(
            icon="↩️",
            title="Pago no completado",
            message="No se cobró nada. Tu cupo queda apartado unos minutos por si quieres intentarlo de nuevo.",
            code=code,
        )
    return HttpResponse(body)
