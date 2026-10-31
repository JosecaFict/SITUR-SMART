from decimal import Decimal

from rest_framework import serializers

from .models import Promotion


class ComponentWriteSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField(source="product_id", min_value=1)
    fecha_inicio = serializers.DateField(source="start_date")
    fecha_fin = serializers.DateField(
        source="end_date", required=False, allow_null=True
    )
    cantidad = serializers.IntegerField(source="quantity", min_value=1, max_value=500)
    huespedes = serializers.IntegerField(
        source="guests", min_value=1, max_value=500, required=False, allow_null=True
    )
    salida_id = serializers.IntegerField(
        source="departure_id", min_value=1, required=False, allow_null=True
    )


class PromotionWriteSerializer(serializers.Serializer):
    modalidad = serializers.ChoiceField(source="mode", choices=Promotion.Mode.choices)
    producto_id = serializers.IntegerField(
        source="product_id", min_value=1, required=False, allow_null=True
    )
    nombre = serializers.CharField(source="name", max_length=200)
    descripcion = serializers.CharField(
        source="description", required=False, allow_blank=True, max_length=10000
    )
    porcentaje_descuento = serializers.DecimalField(
        source="percentage",
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("99.99"),
    )
    inicio = serializers.DateTimeField(source="starts_at")
    fin = serializers.DateTimeField(source="ends_at")
    componentes = ComponentWriteSerializer(
        source="components", many=True, required=False, max_length=20
    )


class EligibleQuerySerializer(serializers.Serializer):
    modalidad = serializers.ChoiceField(
        choices=Promotion.Mode.choices, default=Promotion.Mode.EXISTING
    )


class PublicQuerySerializer(serializers.Serializer):
    fecha = serializers.DateField(required=False)
    cantidad = serializers.IntegerField(min_value=1, max_value=500, default=1)


class EvaluationSerializer(serializers.Serializer):
    valida = serializers.BooleanField()
    advertencias = serializers.ListField(child=serializers.CharField())
    componentes = serializers.ListField(child=serializers.DictField())
    precio_original = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    precio_final = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    monto_descuento = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    moneda_codigo = serializers.CharField(allow_null=True)
    moneda_simbolo = serializers.CharField(allow_null=True)
    imagen_url = serializers.CharField(allow_null=True)
    requiere_revalidacion = serializers.BooleanField()


class PromotionReadSerializer(EvaluationSerializer):
    id = serializers.IntegerField()
    empresa_id = serializers.IntegerField()
    empresa = serializers.CharField()
    modalidad = serializers.ChoiceField(choices=Promotion.Mode.choices)
    producto_id = serializers.IntegerField(allow_null=True)
    nombre = serializers.CharField()
    descripcion = serializers.CharField()
    porcentaje_descuento = serializers.DecimalField(max_digits=5, decimal_places=2)
    inicio = serializers.DateTimeField()
    fin = serializers.DateTimeField()
    estado = serializers.ChoiceField(
        choices=["BORRADOR", "PROGRAMADA", "VIGENTE", "DESACTIVADA", "VENCIDA"]
    )
    estado_administrativo = serializers.ChoiceField(choices=Promotion.Status.choices)
    publicado = serializers.BooleanField()
    admite_reservas = serializers.BooleanField()
    reservable = serializers.BooleanField()
    disponible = serializers.BooleanField(allow_null=True)
    cupos_restantes = serializers.IntegerField(allow_null=True)
    motivo_no_reservable = serializers.CharField(allow_null=True)
    requiere_fecha = serializers.BooleanField()
    cotizacion = serializers.DictField(required=False)
    creado_en = serializers.DateTimeField()
    actualizado_en = serializers.DateTimeField()


class PromotionPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PromotionReadSerializer(many=True)
