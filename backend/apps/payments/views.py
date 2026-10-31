import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings import services as bookings
from apps.bookings.models import BookingDetail
from apps.custom_packages import purchase as package_purchases
from apps.payments import refunds
from apps.rbac.views import tenant_id_from_request
from apps.tenancy import subscriptions

from . import gateway, reconciliation, services
from .models import Payment, ReconciliationIssue
from .serializers import PaymentSerializer

logger = logging.getLogger(__name__)


class PaymentPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CustomerPaymentListView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=PaymentSerializer(many=True))
    def get(self, request):
        queryset = services.customer_payments(user=request.user, params=request.query_params)
        paginator = PaymentPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(PaymentSerializer(page, many=True).data)


class CustomerPaymentDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=PaymentSerializer)
    def get(self, request, pk):
        payment = services.customer_payment(user=request.user, payment_id=pk)
        return Response(PaymentSerializer(payment).data)


class CompanyPaymentListView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=PaymentSerializer(many=True))
    def get(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        queryset = services.company_payments(
            actor=request.user, tenant_id=tenant_id, params=request.query_params
        )
        paginator = PaymentPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        response = paginator.get_paginated_response(PaymentSerializer(page, many=True).data)
        response.data["resumen"] = services.company_summary(
            actor=request.user, tenant_id=tenant_id, params=request.query_params
        )
        return response


class AdminPaymentListView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=PaymentSerializer(many=True))
    def get(self, request):
        queryset = services.global_payments(actor=request.user, params=request.query_params)
        paginator = PaymentPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        response = paginator.get_paginated_response(PaymentSerializer(page, many=True).data)
        response.data["resumen"] = services.payment_summary(queryset)
        return response


class ReconciliationIssueSerializer(serializers.ModelSerializer):
    empresa = serializers.CharField(source="tenant.trade_name")

    class Meta:
        model = ReconciliationIssue
        fields = (
            "id", "empresa", "resource_type", "resource_id", "kind",
            "local_status", "provider_status", "details", "resolved",
            "detected_at", "last_seen_at", "resolved_at",
        )


class AdminPaymentReconciliationView(APIView):
    permission_classes = (IsAuthenticated,)

    def _require_admin(self, request):
        if not request.user.is_staff:
            raise PermissionDenied("Solo el SuperAdministrador puede conciliar pagos.")

    @extend_schema(responses=ReconciliationIssueSerializer(many=True))
    def get(self, request):
        self._require_admin(request)
        queryset = ReconciliationIssue.objects.select_related("tenant")
        if request.query_params.get("resueltas") != "si":
            queryset = queryset.filter(resolved=False)
        return Response({
            "abiertas": ReconciliationIssue.objects.filter(resolved=False).count(),
            "resultados": ReconciliationIssueSerializer(queryset[:200], many=True).data,
        })

    @extend_schema(request=None, responses=serializers.DictField())
    def post(self, request):
        self._require_admin(request)
        return Response(reconciliation.run(force=True, actor=request.user))


class CompanyDepartureListView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=serializers.ListField(child=serializers.DictField()))
    def get(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        slots = services.upcoming_departures(actor=request.user, tenant_id=tenant_id)
        return Response([{
            "id": slot.id, "producto": slot.product.name, "inicio": slot.start,
            "fin": slot.end, "reservas_activas": slot.active_bookings,
        } for slot in slots])


class CompanyDepartureCancellationView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=serializers.DictField(), responses=serializers.DictField())
    def post(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = DepartureCancellationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # La consulta validada también impide cancelar una salida de otro tenant.
        slot = services.upcoming_departures(actor=request.user, tenant_id=tenant_id).filter(id=pk).first()
        if slot is None:
            raise ValidationError("Salida no encontrada o sin reservas activas.")
        booking_ids = list(
            BookingDetail.objects.filter(
                slot_id=pk, booking__tenant_id=tenant_id,
                booking__status__in=bookings.OCCUPYING_STATES,
                booking__checked_in_at__isnull=True,
            ).values_list("booking_id", flat=True).distinct()
        )
        base_key = request.headers.get("Idempotency-Key")
        if not base_key:
            raise ValidationError({"Idempotency-Key": "Envía una clave para evitar duplicados."})
        results = []
        for booking_id in booking_ids:
            try:
                _, refund = refunds.request_company_cancellation(
                    actor=request.user, tenant_id=tenant_id, booking_id=booking_id,
                    reason=serializer.validated_data["motivo"],
                    idempotency_key=f"salida:{pk}:{base_key}:{booking_id}", request=request,
                )
                results.append({"reserva_id": booking_id, "reembolso_id": refund.id, "estado": refund.status})
            except ValidationError as exc:
                results.append({"reserva_id": booking_id, "estado": "REQUIERE_REVISION", "error": exc.detail})
        return Response({
            "salida_id": pk, "total": len(results),
            "procesados": sum(item["estado"] != "REQUIERE_REVISION" for item in results),
            "requieren_revision": sum(item["estado"] == "REQUIERE_REVISION" for item in results),
            "resultados": results,
        })


class DepartureCancellationSerializer(serializers.Serializer):
    motivo = serializers.CharField(min_length=5, max_length=2000, trim_whitespace=True)


class ManualPaymentRequestSerializer(serializers.Serializer):
    reserva_id = serializers.IntegerField(min_value=1)
    metodo = serializers.ChoiceField(
        choices=(Payment.Method.CASH, Payment.Method.QR, Payment.Method.TRANSFER)
    )
    referencia = serializers.CharField(max_length=150, required=False, allow_blank=True)


class CompanyManualPaymentView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=ManualPaymentRequestSerializer, responses={201: PaymentSerializer})
    def post(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = ManualPaymentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = services.register_manual_payment(
            actor=request.user, tenant_id=tenant_id,
            booking_id=serializer.validated_data["reserva_id"],
            method=serializer.validated_data["metodo"],
            reference=serializer.validated_data.get("referencia"),
            idempotency_key=request.headers.get("Idempotency-Key", ""), request=request,
        )
        payment = services.base_queryset().get(id=payment.id)
        return Response(PaymentSerializer(payment).data, status=201)


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
        if event["type"] in ("refund.created", "refund.updated", "refund.failed"):
            refunds.handle_provider_event(session)
            return Response({"recibido": True})
        # La misma cuenta de Stripe cobra reservas y planes de empresa; la
        # metadata de la sesion dice cual es.
        is_plan = (session.get("metadata") or {}).get("tipo") == "SUSCRIPCION"
        is_package = (session.get("metadata") or {}).get("tipo") == "PAQUETE_PERSONALIZADO"
        if event["type"] in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            if session.get("payment_status") in ("paid", "no_payment_required"):
                if is_plan:
                    subscriptions.confirm_payment(session["id"])
                elif is_package:
                    package_purchases.confirm_purchase(session["id"])
                else:
                    bookings.confirm_paid_session(session["id"])
        elif event["type"] in ("checkout.session.expired", "checkout.session.async_payment_failed"):
            if is_plan:
                subscriptions.void_payment(session["id"])
            elif is_package:
                package_purchases.expire_session(session["id"])
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
