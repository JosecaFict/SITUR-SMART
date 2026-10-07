from django.conf import settings
from django.core import signing
from django.http import Http404, HttpResponse
from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import receipt, services
from .models import Booking
from .serializers import BookingRequestSerializer, BookingSerializer, QuoteSerializer


class CheckoutUrlSerializer(serializers.Serializer):
    checkout_url = serializers.URLField()


def _request_args(request) -> dict:
    serializer = BookingRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    return {
        "product_id": data["producto_id"],
        "start": data["fecha_inicio"],
        "end": data.get("fecha_fin"),
        "quantity": data["cantidad"],
        "guests": data.get("huespedes"),
    }


def _return_url(request, result: str) -> str:
    """Pagina a la que Stripe devuelve al turista al terminar o abandonar.

    Desde la app: la pagina del backend que reabre la app. Desde la web
    (``?origen=web``): directo a Mis viajes de la web.
    """
    if request.query_params.get("origen") == "web":
        outcome = "exito" if result == "exito" else "cancelado"
        return f"{settings.WEB_APP_URL.rstrip('/')}/mis-viajes/{{ID}}?pago={outcome}"
    url = request.build_absolute_uri(reverse("stripe-return"))
    return f"{url}?resultado={result}&reserva={{CODIGO}}&id={{ID}}"


class QuoteView(APIView):
    """Precio y cupo de un pedido, sin apartar nada."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=BookingRequestSerializer, responses=QuoteSerializer)
    def post(self, request):
        quote = services.build_quote(**_request_args(request))
        return Response(QuoteSerializer.from_quote(quote, services.availability(quote)))


class BookingListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=BookingSerializer(many=True))
    def get(self, request):
        bookings = services.list_customer_bookings(user=request.user)
        return Response(BookingSerializer(bookings, many=True).data)

    @extend_schema(
        request=BookingRequestSerializer,
        responses={201: BookingSerializer},
        parameters=[
            OpenApiParameter(
                "Idempotency-Key",
                str,
                OpenApiParameter.HEADER,
                required=False,
                description="Repetir la misma clave devuelve la reserva ya creada.",
            )
        ],
    )
    def post(self, request):
        created = services.create_booking(
            user=request.user,
            success_url=_return_url(request, "exito"),
            cancel_url=_return_url(request, "cancelado"),
            idempotency_key=request.headers.get("Idempotency-Key"),
            **_request_args(request),
        )
        booking = services.get_customer_booking(user=request.user, booking_id=created.booking.id)
        data = BookingSerializer(booking).data
        data["checkout_url"] = created.checkout_url
        return Response(data, status=status.HTTP_201_CREATED)


class BookingDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=BookingSerializer)
    def get(self, request, pk):
        booking = services.sync(services.get_customer_booking(user=request.user, booking_id=pk))
        booking = services.get_customer_booking(user=request.user, booking_id=booking.id)
        return Response(BookingSerializer(booking).data)


class BookingPayView(APIView):
    """Enlace de Stripe para retomar el pago de una reserva pendiente."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses=CheckoutUrlSerializer)
    def post(self, request, pk):
        return Response({"checkout_url": services.checkout_url(user=request.user, booking_id=pk)})


class BookingCancelView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses=BookingSerializer)
    def post(self, request, pk):
        services.cancel_booking(user=request.user, booking_id=pk)
        booking = services.get_customer_booking(user=request.user, booking_id=pk)
        return Response(BookingSerializer(booking).data)


class BookingReceiptLinkView(APIView):
    """Enlace firmado al comprobante PDF de una reserva pagada.

    La app lo abre en el navegador del celular: el PDF se baja sin mandar la
    sesion del turista.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request, pk):
        booking = services.get_customer_booking(user=request.user, booking_id=pk)
        if booking.status not in services.OCCUPYING_STATES:
            raise ValidationError("El comprobante está disponible cuando la reserva está pagada.")
        return Response({"url": receipt.receipt_url(booking)})


def receipt_pdf(request, token: str):
    """El PDF del comprobante, por enlace firmado (correo o app)."""
    try:
        booking_id = receipt.read_receipt_token(token)
    except signing.BadSignature:
        raise Http404("El enlace del comprobante no es válido o venció.") from None
    booking = Booking.objects.select_related("order__customer__user", "tenant", "currency").filter(
        id=booking_id, status__in=services.OCCUPYING_STATES
    ).first()
    if booking is None:
        raise Http404("Comprobante no disponible.")
    response = HttpResponse(receipt.build_receipt_pdf(booking), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="comprobante-{booking.code}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response
