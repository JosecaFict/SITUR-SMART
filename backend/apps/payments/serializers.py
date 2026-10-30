from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    reserva_id = serializers.IntegerField(source="booking_id")
    reserva = serializers.CharField(source="booking.code")
    estado_reserva = serializers.CharField(source="booking.status")
    empresa_id = serializers.IntegerField(source="booking.tenant_id")
    empresa = serializers.CharField(source="booking.tenant.trade_name")
    cliente = serializers.SerializerMethodField()
    producto = serializers.SerializerMethodField()
    moneda = serializers.CharField(source="currency.iso_code")
    simbolo = serializers.CharField(source="currency.symbol")
    reembolsos = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            "id", "reserva_id", "reserva", "estado_reserva", "empresa_id", "empresa",
            "cliente", "producto", "moneda", "simbolo", "amount", "method", "status",
            "provider", "created_at", "processed_at", "reembolsos",
        )

    def get_cliente(self, payment) -> dict:
        user = payment.booking.order.customer.user
        return {"nombre": user.get_full_name(), "email": user.email}

    def get_producto(self, payment) -> dict | None:
        details = list(payment.booking.details.all())
        if not details:
            return None
        product = details[0].slot.product
        return {"id": product.id, "nombre": product.name, "tipo": product.product_type.name}

    def get_reembolsos(self, payment) -> list[dict]:
        return [
            {
                "id": refund.id,
                "estado": refund.status,
                "monto": str(refund.amount),
                "motivo": refund.reason,
                "referencia": refund.provider_reference,
                "solicitado_en": serializers.DateTimeField().to_representation(refund.requested_at),
                "procesado_en": serializers.DateTimeField().to_representation(refund.processed_at)
                if refund.processed_at else None,
                "motivo_fallo": refund.failure_reason,
            }
            for refund in payment.refunds.all()
        ]
