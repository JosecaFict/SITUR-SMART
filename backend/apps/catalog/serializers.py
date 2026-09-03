from rest_framework import serializers

from apps.tenancy.models import City

from .models import Currency, ProductType, TourismProduct


class ProductTypeSerializer(serializers.ModelSerializer):
    codigo = serializers.CharField(source="code")
    nombre = serializers.CharField(source="name")

    class Meta:
        model = ProductType
        fields = ("id", "codigo", "nombre")


class CurrencySerializer(serializers.ModelSerializer):
    codigo = serializers.CharField(source="iso_code")
    nombre = serializers.CharField(source="name")
    simbolo = serializers.CharField(source="symbol")

    class Meta:
        model = Currency
        fields = ("id", "codigo", "nombre", "simbolo")


class ProductSerializer(serializers.ModelSerializer):
    empresa_id = serializers.IntegerField(source="tenant_id")
    empresa = serializers.CharField(source="tenant.trade_name")
    tipo_codigo = serializers.CharField(source="product_type.code")
    tipo = serializers.CharField(source="product_type.name")
    ciudad_id = serializers.IntegerField(source="city_id")
    ciudad = serializers.CharField(source="city.name")
    pais_id = serializers.IntegerField(source="city.country_id")
    pais = serializers.CharField(source="city.country.name")
    moneda_codigo = serializers.CharField(source="currency.iso_code")
    moneda_simbolo = serializers.CharField(source="currency.symbol")
    codigo = serializers.CharField(source="code")
    nombre = serializers.CharField(source="name")
    descripcion = serializers.CharField(source="description", allow_null=True)
    localidad = serializers.CharField(source="locality", allow_null=True)
    precio_base = serializers.DecimalField(source="base_price", max_digits=12, decimal_places=2)
    capacidad_maxima = serializers.IntegerField(source="max_capacity")
    estado = serializers.CharField(source="status")
    imagen_url = serializers.CharField(source="image_url", allow_null=True)
    creado_en = serializers.DateTimeField(source="created_at")
    actualizado_en = serializers.DateTimeField(source="updated_at")

    class Meta:
        model = TourismProduct
        fields = (
            "id", "empresa_id", "empresa", "tipo_codigo", "tipo", "ciudad_id", "ciudad",
            "pais_id", "pais", "moneda_codigo", "moneda_simbolo", "codigo", "nombre",
            "descripcion", "localidad", "precio_base", "capacidad_maxima", "estado", "imagen_url",
            "creado_en", "actualizado_en",
        )


class ProductWriteSerializer(serializers.Serializer):
    tipo_codigo = serializers.CharField(max_length=50, required=False)
    ciudad_id = serializers.IntegerField(min_value=1, required=False)
    moneda_codigo = serializers.CharField(max_length=3, required=False)
    codigo = serializers.RegexField(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,59}$", required=False, allow_blank=True)
    nombre = serializers.CharField(max_length=180, required=False)
    descripcion = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    localidad = serializers.CharField(max_length=180, required=False, allow_blank=True, allow_null=True)
    precio_base = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    capacidad_maxima = serializers.IntegerField(min_value=1, required=False)
    estado = serializers.ChoiceField(choices=TourismProduct.Status.choices, required=False)
    imagen_url = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)

    def validate_tipo_codigo(self, value):
        code = value.upper()
        if not ProductType.objects.filter(code=code).exists():
            raise serializers.ValidationError("El tipo de producto no existe.")
        return code

    def validate_ciudad_id(self, value):
        if not City.objects.filter(id=value).exists():
            raise serializers.ValidationError("La ciudad no existe.")
        return value

    def validate_moneda_codigo(self, value):
        code = value.upper()
        if not Currency.objects.filter(iso_code=code).exists():
            raise serializers.ValidationError("La moneda no existe.")
        return code

    def validate(self, attrs):
        if not self.partial:
            required = ("tipo_codigo", "ciudad_id", "moneda_codigo", "nombre", "precio_base", "capacidad_maxima")
            missing = [field for field in required if field not in attrs]
            if missing:
                raise serializers.ValidationError({field: "Este campo es obligatorio." for field in missing})
        return attrs
