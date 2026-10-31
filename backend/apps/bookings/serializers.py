from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.catalog.departures import is_legacy_daily
from apps.catalog.models import ROOM_PRODUCT_CODE

from .models import Booking, BookingState
from .services import OCCUPYING_STATES, voucher_token


class BookingRequestSerializer(serializers.Serializer):
    """Lo que el turista pide. Igual para cotizar y para reservar."""

    producto_id = serializers.IntegerField(min_value=1)
    # Con la salida basta (su dia es la fecha). Sin ella, en un tour se usa la
    # primera salida con cupo de esa fecha: asi sigue funcionando la app movil.
    fecha_inicio = serializers.DateField(required=False)
    salida_id = serializers.IntegerField(min_value=1, required=False)
    # Solo en habitaciones: el dia de salida (la ultima noche es la anterior).
    fecha_fin = serializers.DateField(required=False, allow_null=True)
    # Habitaciones en un hospedaje; personas en lo demas.
    cantidad = serializers.IntegerField(min_value=1, max_value=500)
    huespedes = serializers.IntegerField(min_value=1, max_value=500, required=False, allow_null=True)
    politica_cancelacion_id = serializers.IntegerField(min_value=1, required=False)
    acepta_politica_cancelacion = serializers.BooleanField(required=False)
    razon_social_facturacion = serializers.CharField(max_length=180, required=False, allow_blank=True)
    nit_facturacion = serializers.CharField(max_length=40, required=False, allow_blank=True)
    promocion_id = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if "fecha_inicio" not in attrs and "salida_id" not in attrs:
            raise serializers.ValidationError({"fecha_inicio": "Indica la fecha o la salida."})
        return attrs


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
    politica_cancelacion = serializers.DictField(allow_null=True)
    salida_id = serializers.IntegerField(allow_null=True)
    inicio = serializers.DateTimeField(allow_null=True)
    fin = serializers.DateTimeField(allow_null=True)
    promocion = serializers.DictField(allow_null=True)

    @staticmethod
    def from_quote(quote, remaining: int) -> dict:
        product = quote.product
        policy = product.cancellation_policy
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
            "politica_cancelacion": {
                "id": policy.id,
                "nombre": policy.name,
                "reembolsable": policy.refundable,
                "reglas": [
                    {
                        "dias_antes_min": rule.minimum_days,
                        "dias_antes_max": rule.maximum_days,
                        "porcentaje_penalizacion": str(rule.penalty_percentage),
                    }
                    for rule in policy.rules.order_by("minimum_days", "maximum_days", "id")
                ],
            }
            if policy
            else None,
            "salida_id": quote.slot.id if quote.slot else None,
            "inicio": quote.slot.start if quote.slot else None,
            "fin": quote.slot.end if quote.slot else None,
            "promocion": quote.promotion_discount.data(quote.quantity) if quote.promotion_discount else None,
        }


class CancellationQuoteSerializer(serializers.Serializer):
    """Cotizacion de solo lectura previa a cancelar una reserva pagada."""

    reserva_id = serializers.IntegerField(source="booking_id")
    politica_id = serializers.IntegerField(source="policy_id")
    politica = serializers.CharField(source="policy_name")
    regla_id = serializers.IntegerField(source="rule_id", allow_null=True)
    dias_anticipacion = serializers.IntegerField(source="advance_days")
    monto_pagado = serializers.DecimalField(source="paid_amount", max_digits=12, decimal_places=2)
    porcentaje_penalizacion = serializers.DecimalField(
        source="penalty_percentage", max_digits=5, decimal_places=2
    )
    monto_penalizacion = serializers.DecimalField(
        source="penalty_amount", max_digits=12, decimal_places=2
    )
    monto_reembolso = serializers.DecimalField(
        source="refund_amount", max_digits=12, decimal_places=2
    )


class PaidCancellationRequestSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class PaidCancellationResultSerializer(serializers.Serializer):
    cancelacion_id = serializers.IntegerField()
    reserva_id = serializers.IntegerField()
    estado_reserva = serializers.CharField()
    dias_anticipacion = serializers.IntegerField()
    porcentaje_penalizacion = serializers.DecimalField(max_digits=5, decimal_places=2)
    monto_penalizacion = serializers.DecimalField(max_digits=12, decimal_places=2)
    monto_reembolso = serializers.DecimalField(max_digits=12, decimal_places=2)
    reembolso = serializers.DictField(allow_null=True)


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
    politica_cancelacion = serializers.JSONField(source="cancellation_policy_snapshot", allow_null=True)
    politica_aceptada_en = serializers.DateTimeField(source="policy_accepted_at", allow_null=True)
    datos_facturacion = serializers.SerializerMethodField()
    salida = serializers.SerializerMethodField()
    promocion = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = (
            "id", "codigo", "orden", "estado", "estado_nombre", "empresa", "producto",
            "fechas", "importe", "huespedes", "moneda_codigo", "moneda_simbolo",
            "pago", "politica_cancelacion", "politica_aceptada_en", "datos_facturacion",
            "vence_en", "qr", "salida", "creado_en", "promocion",
        )

    @staticmethod
    def _details(booking):
        return list(booking.details.all())

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_promocion(self, booking):
        snapshot = getattr(booking, "promotion_snapshot", None)
        if snapshot is None:
            return None
        return {"id": snapshot.promotion_id, "nombre": snapshot.name,
                "porcentaje_descuento": str(snapshot.percentage),
                "precio_original": str(snapshot.original_unit_price), "precio_final": str(snapshot.final_unit_price),
                "total_original": str(snapshot.original_total), "descuento_total": str(snapshot.discount_amount),
                "total": str(snapshot.total), "inicio": snapshot.starts_at, "fin": snapshot.ends_at}

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

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_salida(self, booking) -> dict | None:
        details = self._details(booking)
        if not details or is_legacy_daily(details[0].slot):
            return None
        slot = details[0].slot
        return {"id": slot.id, "inicio": serializers.DateTimeField().to_representation(slot.start),
                "fin": serializers.DateTimeField().to_representation(slot.end)}

    @extend_schema_field(serializers.DictField())
    def get_importe(self, booking) -> dict:
        details = self._details(booking)
        if not details:
            return {"cantidad": 0, "unidad": "", "precio_unitario": None, "total": "0.00"}
        is_room = details[0].slot.product.product_type.code == ROOM_PRODUCT_CODE
        quantity = details[0].quantity
        calculated = sum((detail.quantity * detail.unit_price for detail in details), start=0)
        original = booking.original_amount if booking.original_amount is not None else calculated
        discount = booking.discount_amount if booking.discount_amount is not None else 0
        total = booking.final_amount if booking.final_amount is not None else calculated
        return {
            "cantidad": quantity,
            "unidad": ("habitación" if quantity == 1 else "habitaciones")
            if is_room
            else ("persona" if quantity == 1 else "personas"),
            "precio_unitario": str(details[0].unit_price),
            "precio_original": f"{original:.2f}",
            "descuento": f"{discount:.2f}",
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
            "referencia": payment.reference,
            "monto": str(payment.amount),
            "procesado_en": serializers.DateTimeField().to_representation(payment.processed_at)
            if payment.processed_at
            else None,
        }

    def get_datos_facturacion(self, booking) -> dict | None:
        if not booking.billing_name and not booking.billing_tax_id:
            return None
        return {"razon_social": booking.billing_name, "nit": booking.billing_tax_id}

    def get_qr(self, booking) -> str | None:
        """Solo una reserva pagada tiene voucher que mostrar."""
        if booking.status not in OCCUPYING_STATES:
            return None
        return voucher_token(booking)
