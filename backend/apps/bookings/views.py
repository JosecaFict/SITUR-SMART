from django.urls import reverse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
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
    """Pagina a la que Stripe devuelve al turista al terminar o abandonar."""
    url = request.build_absolute_uri(reverse("stripe-return"))
    return f"{url}?resultado={result}&reserva={{CODIGO}}"


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
