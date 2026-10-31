from django.utils import timezone
from rest_framework import serializers

from apps.tenancy.models import City


class PackageWriteSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=120, trim_whitespace=True)
    ciudad_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    fecha_inicio = serializers.DateField()
    fecha_fin = serializers.DateField()
    personas = serializers.IntegerField(min_value=1, max_value=100)

    def validate_nombre(self, value):
        if not value.strip():
            raise serializers.ValidationError("Escribe un nombre para el paquete.")
        return value

    def validate_ciudad_id(self, value):
        if value is not None and not City.objects.filter(id=value, active=True).exists():
            raise serializers.ValidationError("Destino no encontrado.")
        return value

    def validate(self, attrs):
        start = attrs.get("fecha_inicio", getattr(self.instance, "start_date", None))
        end = attrs.get("fecha_fin", getattr(self.instance, "end_date", None))
        if start and start < timezone.localdate():
            raise serializers.ValidationError({"fecha_inicio": "Elige una fecha desde hoy en adelante."})
        if start and end and end < start:
            raise serializers.ValidationError({"fecha_fin": "Debe ser igual o posterior al inicio."})
        return attrs


class ComponentWriteSerializer(serializers.Serializer):
    componente_id = serializers.IntegerField(min_value=1, required=False)
    producto_id = serializers.IntegerField(min_value=1)
    fecha_inicio = serializers.DateField()
    fecha_fin = serializers.DateField(required=False, allow_null=True)
    cantidad = serializers.IntegerField(min_value=1, max_value=100)
    huespedes = serializers.IntegerField(min_value=1, max_value=100, required=False, allow_null=True)
    salida_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def as_values(self):
        data = self.validated_data
        mapping = {"producto_id": "product_id", "fecha_inicio": "start_date",
                   "fecha_fin": "end_date", "cantidad": "quantity", "huespedes": "guests",
                   "salida_id": "departure_id"}
        return {mapping[key]: value for key, value in data.items() if key in mapping}


class CatalogQuerySerializer(serializers.Serializer):
    ciudad = serializers.IntegerField(min_value=1, required=False)
    tipo = serializers.CharField(max_length=50, required=False)
    buscar = serializers.CharField(max_length=180, required=False)
    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=50, required=False)
