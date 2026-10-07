"""Endpoints de reservas para la empresa (X-Tenant-ID). Ver company.py."""

from datetime import date

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.rbac.views import tenant_id_from_request

from . import company, receipt
from .serializers import BookingSerializer
from .services import OCCUPYING_STATES


class CompanyBookingSerializer(BookingSerializer):
    """La reserva con el contacto del cliente y la llegada, para quien la vende."""

    cliente = serializers.SerializerMethodField()
    llegada = serializers.SerializerMethodField()
    comprobante_url = serializers.SerializerMethodField()

    class Meta(BookingSerializer.Meta):
        fields = (*BookingSerializer.Meta.fields, "cliente", "llegada", "comprobante_url")

    def get_cliente(self, booking) -> dict:
        user = booking.order.customer.user
        return {"nombre": user.get_full_name(), "email": user.email, "telefono": user.phone}

    def get_llegada(self, booking) -> dict | None:
        if not booking.checked_in_at:
            return None
        return {
            "en": serializers.DateTimeField().to_representation(booking.checked_in_at),
            "por": booking.checked_in_by.get_full_name() if booking.checked_in_by_id else None,
        }

    def get_comprobante_url(self, booking) -> str | None:
        return receipt.receipt_url(booking) if booking.status in OCCUPYING_STATES else None


class CompanyBookingPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _date(params, key: str) -> date | None:
    raw = params.get(key)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError({key: "Usa el formato AAAA-MM-DD."}) from exc


class CompanyBookingListView(APIView):
    """Reservas de la empresa, con filtros y los totales de arriba."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=CompanyBookingSerializer(many=True))
    def get(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        params = request.query_params
        product = params.get("producto_id")
        filters = {
            "desde": _date(params, "desde"),
            "hasta": _date(params, "hasta"),
            "estado": params.get("estado", "").strip(),
            "producto_id": int(product) if product and product.isdigit() else None,
            "buscar": params.get("buscar", ""),
            "llegadas_hoy": params.get("llegadas") == "hoy",
        }
        bookings = company.list_bookings(actor=request.user, tenant_id=tenant_id, filters=filters)
        paginator = CompanyBookingPagination()
        page = paginator.paginate_queryset(bookings, request, view=self)
        response = paginator.get_paginated_response(CompanyBookingSerializer(page, many=True).data)
        response.data["resumen"] = company.summary(actor=request.user, tenant_id=tenant_id)
        return response


class CompanyBookingDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=CompanyBookingSerializer)
    def get(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        booking = company.get_booking(actor=request.user, tenant_id=tenant_id, booking_id=pk)
        return Response(CompanyBookingSerializer(booking).data)


class VoucherLookupSerializer(serializers.Serializer):
    codigo = serializers.CharField(max_length=2000, trim_whitespace=True)


class VoucherLookupView(APIView):
    """Busca la reserva por su codigo o por el contenido del QR y dice si puede marcarse la llegada."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=VoucherLookupSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = VoucherLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = company.lookup_voucher(
            actor=request.user, tenant_id=tenant_id, value=serializer.validated_data["codigo"]
        )
        return Response({
            "reserva": CompanyBookingSerializer(result["reserva"]).data,
            "puede_marcar_llegada": result["puede_marcar_llegada"],
            "motivo": result["motivo"],
        })


class CheckInView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses=CompanyBookingSerializer)
    def post(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        booking = company.check_in(actor=request.user, tenant_id=tenant_id, booking_id=pk, request=request)
        return Response(CompanyBookingSerializer(booking).data)


class ReportCustomerSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=2000, trim_whitespace=True)


class ReportCustomerView(APIView):
    """Avisa a la plataforma de un problema con el cliente de esta reserva."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=ReportCustomerSerializer, responses={201: None})
    def post(self, request, pk):
        tenant_id = tenant_id_from_request(request, required=True)
        serializer = ReportCustomerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company.report_customer(
            actor=request.user, tenant_id=tenant_id, booking_id=pk,
            reason=serializer.validated_data["motivo"], request=request,
        )
        return Response({"detail": "Le avisamos a SITUR-SMART. Gracias por reportarlo."}, status=201)
