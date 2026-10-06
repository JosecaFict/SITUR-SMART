from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.catalog.models import ROOM_PRODUCT_CODE

from .models import Booking, BookingState
from .services import OCCUPYING_STATES, voucher_token


class BookingRequestSerializer(serializers.Serializer):
    """Lo que el turista pide. Igual para cotizar y para reservar."""

    producto_id = serializers.IntegerField(min_value=1)
    fecha_inicio = serializers.DateField()
    # Solo en habitaciones: el dia de salida (la ultima noche es la anterior).
    fecha_fin = serializers.DateField(required=False, allow_null=True)
    # Habitaciones en un hospedaje; personas en lo demas.
    cantidad = serializers.IntegerField(min_value=1, max_value=500)
    huespedes = serializers.IntegerField(min_value=1, max_value=500, required=False, allow_null=True)


class QuoteSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField()
    fecha_inicio = serializers.DateField()
    fecha_fin = serializers.DateField()
    noches = serializers.IntegerField(allow_null=True)
    cantidad = serializers.IntegerField()
    huespedes = serializers.IntegerField(allow_null=True)
    precio_unitario = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    moneda_codigo = serializers.CharField()
    moneda_simbolo = serializers.CharField()
    disponibles = serializers.IntegerField()
    disponible = serializers.BooleanField()

    @staticmethod
    def from_quote(quote, remaining: int) -> dict:
        product = quote.product
        return {
            "producto_id": product.id,
            "fecha_inicio": quote.start,
            "fecha_fin": quote.end,
            "noches": len(quote.days) if quote.is_room else None,
            "cantidad": quote.quantity,
            "huespedes": quote.guests,
            "precio_unitario": quote.unit_price,
            "total": quote.total,
            "moneda_codigo": product.currency.iso_code,
            "moneda_simbolo": product.currency.symbol,
            "disponibles": remaining,
            "disponible": remaining >= quote.quantity,
        }


class BookingSerializer(serializers.ModelSerializer):
    """Una reserva tal como la ve el turista en Mis viajes y en su voucher."""

    codigo = serializers.CharField(source="code")
    orden = serializers.CharField(source="order.code")
    estado = serializers.CharField(source="status")
    estado_nombre = serializers.SerializerMethodField()
    empresa = serializers.CharField(source="tenant.trade_name")
    moneda_codigo = serializers.CharField(source="currency.iso_code")
    moneda_simbolo = serializers.CharField(source="currency.symbol")
    huespedes = serializers.IntegerField(source="guests", allow_null=True)
    vence_en = serializers.SerializerMethodField()
    creado_en = serializers.DateTimeField(source="created_at")
    producto = serializers.SerializerMethodField()
    fechas = serializers.SerializerMethodField()
    importe = serializers.SerializerMethodField()
    pago = serializers.SerializerMethodField()
    qr = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = (
            "id", "codigo", "orden", "estado", "estado_nombre", "empresa", "producto",
            "fechas", "importe", "huespedes", "moneda_codigo", "moneda_simbolo",
            "pago", "vence_en", "qr", "creado_en",
        )

    @staticmethod
    def _details(booking):
        return list(booking.details.all())

    def get_estado_nombre(self, booking) -> str:
        return BookingState(booking.status).label

    def get_vence_en(self, booking) -> str | None:
        if booking.status != BookingState.CREATED or booking.expires_at is None:
            return None
        return serializers.DateTimeField().to_representation(booking.expires_at)

    @extend_schema_field(serializers.DictField())
    def get_producto(self, booking) -> dict | None:
        details = self._details(booking)
        if not details:
            return None
        product = details[0].slot.product
        is_room = product.product_type.code == ROOM_PRODUCT_CODE
        hotel = product.room.establishment if is_room else None
        return {
            "id": product.id,
            "nombre": product.name,
            "tipo_codigo": product.product_type.code,
            "tipo": product.product_type.name,
            "ciudad": product.city.name,
            "localidad": product.locality,
            "imagen_url": product.image_url or (hotel.product.image_url if hotel else None),
            "es_hospedaje": is_room,
            "hospedaje_id": hotel.id if hotel else None,
            "establecimiento": hotel.product.name if hotel else None,
        }

    @extend_schema_field(serializers.DictField())
    def get_fechas(self, booking) -> dict | None:
        details = self._details(booking)
        if not details:
            return None
        first = details[0].slot
        last = details[-1].slot
        is_room = first.product.product_type.code == ROOM_PRODUCT_CODE
        # Los cupos empiezan a medianoche de La Paz: la fecha local es el dia.
        local_first = timezone.localtime(first.start).date()
        local_last = timezone.localtime(last.start).date()
        return {
            "inicio": local_first.isoformat(),
            "fin": (local_last + timedelta(days=1)).isoformat() if is_room else local_first.isoformat(),
            "noches": len(details) if is_room else None,
        }

    @extend_schema_field(serializers.DictField())
    def get_importe(self, booking) -> dict:
        details = self._details(booking)
        if not details:
            return {"cantidad": 0, "unidad": "", "precio_unitario": None, "total": "0.00"}
        is_room = details[0].slot.product.product_type.code == ROOM_PRODUCT_CODE
        quantity = details[0].quantity
        total = sum((detail.quantity * detail.unit_price for detail in details), start=0)
        return {
            "cantidad": quantity,
            "unidad": ("habitación" if quantity == 1 else "habitaciones")
            if is_room
            else ("persona" if quantity == 1 else "personas"),
            "precio_unitario": str(details[0].unit_price),
            "total": f"{total:.2f}",
        }

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_pago(self, booking) -> dict | None:
        payments = list(booking.payments.all())
        if not payments:
            return None
        payment = payments[0]
        return {
            "estado": payment.status,
            "metodo": payment.method,
            "proveedor": payment.provider,
            "monto": str(payment.amount),
            "procesado_en": serializers.DateTimeField().to_representation(payment.processed_at)
            if payment.processed_at
            else None,
        }

    def get_qr(self, booking) -> str | None:
        """Solo una reserva pagada tiene voucher que mostrar."""
        if booking.status not in OCCUPYING_STATES:
            return None
        return voucher_token(booking)
