from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.tenancy.models import City

from .models import (
    AVAILABLE_LODGING_TYPE_CODES,
    LODGING_PRODUCT_CODES,
    UNSUPPORTED_LODGING_TYPE_MESSAGE,
    Currency,
    LodgingEstablishment,
    LodgingType,
    ProductType,
    Room,
    TourismProduct,
)


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
    precio_desde = serializers.SerializerMethodField()
    hospedaje_id = serializers.SerializerMethodField()
    establecimiento = serializers.SerializerMethodField()

    class Meta:
        model = TourismProduct
        fields = (
            "id", "empresa_id", "empresa", "tipo_codigo", "tipo", "ciudad_id", "ciudad",
            "pais_id", "pais", "moneda_codigo", "moneda_simbolo", "codigo", "nombre",
            "descripcion", "localidad", "precio_base", "precio_desde", "capacidad_maxima",
            "estado", "imagen_url", "hospedaje_id", "establecimiento",
            "creado_en", "actualizado_en",
        )

    @staticmethod
    def _room(product):
        """La fila de habitacion, o None si el producto no es una.

        El acceso a un OneToOne inverso ausente levanta DoesNotExist en lugar de
        devolver None, de ahi el try.
        """
        try:
            return product.room
        except ObjectDoesNotExist:
            return None

    @staticmethod
    def _lodging(product):
        """La ficha de establecimiento, o None si el producto no es un hotel."""
        try:
            return product.lodging
        except ObjectDoesNotExist:
            return None

    @extend_schema_field(
        serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    )
    def get_precio_desde(self, product) -> str | None:
        """Precio de la habitacion publicada mas economica, solo en hoteles.

        Depende de la anotacion de ``services.with_lodging_from_price``, que
        aplican las vistas publicas. Donde no se aplica, o donde el producto no
        es un hospedaje, el campo es nulo. Nunca es 0: la anotacion descarta los
        precios no positivos.
        """
        value = getattr(product, "from_price", None)
        return None if value is None else str(value)

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_hospedaje_id(self, product) -> int | None:
        """Establecimiento cuyo detalle corresponde abrir.

        En un hotel es su propia ficha; en una habitacion, la del hotel que la
        aloja. Es el id de ``establecimiento_hospedaje``, no el del producto: son
        numeraciones distintas y confundirlas abre el hospedaje equivocado.
        """
        if lodging := self._lodging(product):
            return lodging.id
        room = self._room(product)
        return room.establishment_id if room else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_establecimiento(self, product) -> str | None:
        """Hotel al que pertenece la habitacion. Nulo en cualquier otro producto.

        Permite que la tarjeta de una habitacion en la categoria "Todos" nombre
        su establecimiento sin consultar el endpoint de hospedaje.
        """
        room = self._room(product)
        return room.establishment.product.name if room else None


class MarketplaceQuerySerializer(serializers.Serializer):
    pais = serializers.IntegerField(min_value=1, required=False)
    ciudad = serializers.IntegerField(min_value=1, required=False)
    localidad = serializers.CharField(max_length=180, required=False, allow_blank=False)
    tipo = serializers.CharField(max_length=50, required=False, allow_blank=False)
    fecha = serializers.DateField(required=False)
    buscar = serializers.CharField(max_length=180, required=False, allow_blank=False)
    precio_min = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False
    )
    precio_max = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False
    )
    orden = serializers.ChoiceField(
        choices=("recientes", "precio_asc", "precio_desc", "nombre"),
        default="recientes",
        required=False,
    )
    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=50, required=False)

    def validate(self, attrs):
        minimum = attrs.get("precio_min")
        maximum = attrs.get("precio_max")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise serializers.ValidationError(
                {"precio_max": "Debe ser mayor o igual que el precio mínimo."}
            )
        return attrs


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
        if code in LODGING_PRODUCT_CODES:
            raise serializers.ValidationError(
                "Los hospedajes y sus habitaciones se registran en /api/v1/hospedajes/, "
                "donde quedan vinculados a un establecimiento."
            )
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


# ============================================================
# HOSPEDAJE
# ============================================================


class LodgingTypeSerializer(serializers.ModelSerializer):
    codigo = serializers.CharField(source="code")
    nombre = serializers.CharField(source="name")

    class Meta:
        model = LodgingType
        fields = ("id", "codigo", "nombre")


class LodgingSerializer(serializers.ModelSerializer):
    """Establecimiento con los datos comunes resueltos desde su producto."""

    producto_id = serializers.IntegerField(source="product_id")
    empresa_id = serializers.IntegerField(source="tenant_id")
    empresa = serializers.CharField(source="tenant.trade_name")
    tipo_hospedaje_codigo = serializers.CharField(source="lodging_type.code")
    tipo_hospedaje = serializers.CharField(source="lodging_type.name")
    nombre = serializers.CharField(source="product.name")
    descripcion = serializers.CharField(source="product.description", allow_null=True)
    ciudad_id = serializers.IntegerField(source="product.city_id")
    ciudad = serializers.CharField(source="product.city.name")
    pais_id = serializers.IntegerField(source="product.city.country_id")
    pais = serializers.CharField(source="product.city.country.name")
    localidad = serializers.CharField(source="product.locality", allow_null=True)
    moneda_codigo = serializers.CharField(source="product.currency.iso_code")
    moneda_simbolo = serializers.CharField(source="product.currency.symbol")
    capacidad_maxima = serializers.IntegerField(source="product.max_capacity")
    estado = serializers.CharField(source="product.status")
    imagen_url = serializers.CharField(source="product.image_url", allow_null=True)
    direccion = serializers.CharField(source="address", allow_null=True)
    categoria_estrellas = serializers.IntegerField(source="star_rating", allow_null=True)
    hora_check_in = serializers.TimeField(source="check_in", allow_null=True)
    hora_check_out = serializers.TimeField(source="check_out", allow_null=True)
    servicios = serializers.JSONField(source="services")
    # Anotaciones de services.with_from_price. precio_desde es nulo cuando el
    # hotel todavia no tiene ninguna habitacion que mostrar.
    precio_desde = serializers.DecimalField(
        source="from_price", max_digits=12, decimal_places=2, allow_null=True
    )
    total_habitaciones = serializers.IntegerField(source="rooms_count")
    creado_en = serializers.DateTimeField(source="created_at")
    actualizado_en = serializers.DateTimeField(source="updated_at")

    class Meta:
        model = LodgingEstablishment
        fields = (
            "id", "producto_id", "empresa_id", "empresa", "tipo_hospedaje_codigo",
            "tipo_hospedaje", "nombre", "descripcion", "ciudad_id", "ciudad", "pais_id",
            "pais", "localidad", "moneda_codigo", "moneda_simbolo", "capacidad_maxima",
            "estado", "imagen_url", "direccion", "categoria_estrellas", "hora_check_in",
            "hora_check_out", "servicios", "precio_desde", "total_habitaciones",
            "creado_en", "actualizado_en",
        )


class RoomSerializer(serializers.ModelSerializer):
    """Habitacion con su establecimiento, empresa y ubicacion heredada."""

    producto_id = serializers.IntegerField(source="product_id")
    establecimiento_id = serializers.IntegerField(source="establishment_id")
    establecimiento = serializers.CharField(source="establishment.product.name")
    empresa_id = serializers.IntegerField(source="tenant_id")
    empresa = serializers.CharField(source="product.tenant.trade_name")
    nombre = serializers.CharField(source="product.name")
    descripcion = serializers.CharField(source="product.description", allow_null=True)
    ciudad_id = serializers.IntegerField(source="product.city_id")
    ciudad = serializers.CharField(source="product.city.name")
    pais_id = serializers.IntegerField(source="product.city.country_id")
    pais = serializers.CharField(source="product.city.country.name")
    localidad = serializers.CharField(source="product.locality", allow_null=True)
    moneda_codigo = serializers.CharField(source="product.currency.iso_code")
    moneda_simbolo = serializers.CharField(source="product.currency.symbol")
    precio_noche = serializers.DecimalField(
        source="product.base_price", max_digits=12, decimal_places=2
    )
    capacidad_maxima = serializers.IntegerField(source="product.max_capacity")
    capacidad_adultos = serializers.IntegerField(source="adults_capacity")
    capacidad_ninos = serializers.IntegerField(source="children_capacity")
    cantidad_habitaciones = serializers.IntegerField(source="quantity")
    tipo_cama = serializers.CharField(source="bed_type", allow_null=True)
    incluye_desayuno = serializers.BooleanField(source="includes_breakfast")
    estado = serializers.CharField(source="product.status")
    imagen_url = serializers.CharField(source="product.image_url", allow_null=True)
    creado_en = serializers.DateTimeField(source="created_at")
    actualizado_en = serializers.DateTimeField(source="updated_at")

    class Meta:
        model = Room
        fields = (
            "id", "producto_id", "establecimiento_id", "establecimiento", "empresa_id",
            "empresa", "nombre", "descripcion", "ciudad_id", "ciudad", "pais_id", "pais",
            "localidad", "moneda_codigo", "moneda_simbolo", "precio_noche",
            "capacidad_maxima", "capacidad_adultos", "capacidad_ninos",
            "cantidad_habitaciones", "tipo_cama", "incluye_desayuno", "estado",
            "imagen_url", "creado_en", "actualizado_en",
        )


class LodgingWriteSerializer(serializers.Serializer):
    """Alta y edicion de un establecimiento.

    No acepta ``precio_base``: el precio de un hotel se deriva de su habitacion
    publicada mas economica.
    """

    tipo_hospedaje_codigo = serializers.CharField(max_length=50, required=False)
    nombre = serializers.CharField(max_length=180, required=False)
    descripcion = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ciudad_id = serializers.IntegerField(min_value=1, required=False)
    localidad = serializers.CharField(max_length=180, required=False, allow_blank=True, allow_null=True)
    moneda_codigo = serializers.CharField(max_length=3, required=False)
    capacidad_maxima = serializers.IntegerField(min_value=1, required=False)
    estado = serializers.ChoiceField(choices=TourismProduct.Status.choices, required=False)
    imagen_url = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)
    codigo = serializers.RegexField(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,59}$", required=False, allow_blank=True)
    direccion = serializers.CharField(max_length=250, required=False, allow_blank=True, allow_null=True)
    categoria_estrellas = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    hora_check_in = serializers.TimeField(required=False, allow_null=True)
    hora_check_out = serializers.TimeField(required=False, allow_null=True)
    servicios = serializers.ListField(
        child=serializers.CharField(max_length=80), required=False, allow_empty=True
    )

    def validate_tipo_hospedaje_codigo(self, value):
        code = value.upper()
        if not LodgingType.objects.filter(code=code).exists():
            raise serializers.ValidationError("El tipo de hospedaje no existe.")
        # Se comprueba despues de la existencia para distinguir "no existe" de
        # "existe pero todavia no esta habilitado", que son dos errores distintos
        # para quien consume la API.
        if code not in AVAILABLE_LODGING_TYPE_CODES:
            raise serializers.ValidationError(UNSUPPORTED_LODGING_TYPE_MESSAGE)
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
            required = ("nombre", "ciudad_id", "moneda_codigo", "capacidad_maxima")
            missing = [field for field in required if field not in attrs]
            if missing:
                raise serializers.ValidationError(
                    {field: "Este campo es obligatorio." for field in missing}
                )
        return attrs


class RoomWriteSerializer(serializers.Serializer):
    """Alta y edicion de un tipo de habitacion.

    No acepta ``ciudad_id`` ni ``localidad``: la ubicacion la hereda del
    establecimiento, para que una habitacion no pueda publicarse en otra ciudad
    que su hotel. ``moneda_codigo`` es opcional y por omision toma la del hotel.
    """

    nombre = serializers.CharField(max_length=180, required=False)
    descripcion = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    moneda_codigo = serializers.CharField(max_length=3, required=False)
    precio_base = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    capacidad_maxima = serializers.IntegerField(min_value=1, required=False)
    estado = serializers.ChoiceField(choices=TourismProduct.Status.choices, required=False)
    imagen_url = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)
    codigo = serializers.RegexField(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,59}$", required=False, allow_blank=True)
    cantidad_habitaciones = serializers.IntegerField(min_value=1, required=False)
    capacidad_adultos = serializers.IntegerField(min_value=1, required=False)
    capacidad_ninos = serializers.IntegerField(min_value=0, required=False)
    tipo_cama = serializers.CharField(max_length=60, required=False, allow_blank=True, allow_null=True)
    incluye_desayuno = serializers.BooleanField(required=False)

    def validate_moneda_codigo(self, value):
        code = value.upper()
        if not Currency.objects.filter(iso_code=code).exists():
            raise serializers.ValidationError("La moneda no existe.")
        return code

    def validate(self, attrs):
        if not self.partial:
            required = ("nombre", "precio_base", "capacidad_maxima")
            missing = [field for field in required if field not in attrs]
            if missing:
                raise serializers.ValidationError(
                    {field: "Este campo es obligatorio." for field in missing}
                )
        return attrs


class _HospedajeQuerySerializer(serializers.Serializer):
    """Filtros comunes a las consultas publicas de hospedaje."""

    pais = serializers.IntegerField(min_value=1, required=False)
    ciudad = serializers.IntegerField(min_value=1, required=False)
    localidad = serializers.CharField(max_length=180, required=False, allow_blank=False)
    buscar = serializers.CharField(max_length=180, required=False, allow_blank=False)
    precio_min = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    precio_max = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    orden = serializers.ChoiceField(
        choices=("recientes", "precio_asc", "precio_desc", "nombre"),
        default="recientes",
        required=False,
    )
    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=50, required=False)

    def validate(self, attrs):
        minimum = attrs.get("precio_min")
        maximum = attrs.get("precio_max")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise serializers.ValidationError(
                {"precio_max": "Debe ser mayor o igual que el precio mínimo."}
            )
        return attrs


class PublicLodgingQuerySerializer(_HospedajeQuerySerializer):
    """El precio filtrado y ordenado es el "desde" del establecimiento."""

    estrellas = serializers.IntegerField(min_value=1, max_value=5, required=False)
    tipo_hospedaje = serializers.CharField(max_length=50, required=False, allow_blank=False)


class PublicRoomQuerySerializer(_HospedajeQuerySerializer):
    hospedaje = serializers.IntegerField(min_value=1, required=False)
    huespedes = serializers.IntegerField(min_value=1, required=False)
