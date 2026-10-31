"""Formatos de la API de tours, salidas y guias (CU20)."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.tenancy.models import City

from .models import (
    TOUR_PRODUCT_CODES,
    Availability,
    Currency,
    Guide,
    TourDetail,
    TourismProduct,
    TourStop,
)
from .serializers import CoordinateField, check_coordinate_pair

# --- Paradas -------------------------------------------------------------------


class TourStopSerializer(serializers.ModelSerializer):
    orden = serializers.IntegerField(source="order")
    nombre = serializers.CharField(source="name")
    descripcion = serializers.CharField(source="description", allow_null=True)
    duracion_minutos = serializers.IntegerField(source="duration_minutes", allow_null=True)

    class Meta:
        model = TourStop
        fields = ("id", "orden", "nombre", "descripcion", "duracion_minutos")


class TourStopWriteSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=150)
    descripcion = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    duracion_minutos = serializers.IntegerField(min_value=1, max_value=10080, required=False, allow_null=True)


class TourStopsWriteSerializer(serializers.Serializer):
    paradas = TourStopWriteSerializer(many=True, allow_empty=True)


# --- Tour ----------------------------------------------------------------------


class TourDetailSerializer(serializers.ModelSerializer):
    duracion_minutos = serializers.IntegerField(source="duration_minutes", allow_null=True)
    duracion = serializers.CharField(source="readable_duration", allow_null=True)
    idioma = serializers.CharField(source="language", allow_null=True)
    dificultad = serializers.CharField(source="difficulty", allow_null=True)
    edad_minima = serializers.IntegerField(source="minimum_age", allow_null=True)
    punto_encuentro = serializers.CharField(source="meeting_point", allow_null=True)
    latitud = serializers.DecimalField(source="latitude", max_digits=9, decimal_places=6, allow_null=True)
    longitud = serializers.DecimalField(source="longitude", max_digits=9, decimal_places=6, allow_null=True)
    incluye = serializers.ListField(source="includes", child=serializers.CharField())
    no_incluye = serializers.ListField(source="excludes", child=serializers.CharField())
    requisitos = serializers.CharField(source="requirements", allow_null=True)

    class Meta:
        model = TourDetail
        fields = (
            "duracion_minutos", "duracion", "idioma", "dificultad", "edad_minima", "punto_encuentro",
            "latitud", "longitud", "incluye", "no_incluye", "requisitos",
        )


class TourSerializer(serializers.ModelSerializer):
    """Un tour con su ficha, su recorrido y el resumen de sus proximas salidas."""

    empresa_id = serializers.IntegerField(source="tenant_id")
    empresa = serializers.CharField(source="tenant.trade_name")
    tipo_codigo = serializers.CharField(source="product_type.code")
    tipo = serializers.CharField(source="product_type.name")
    codigo = serializers.CharField(source="code")
    nombre = serializers.CharField(source="name")
    descripcion = serializers.CharField(source="description", allow_null=True)
    ciudad_id = serializers.IntegerField(source="city_id")
    ciudad = serializers.CharField(source="city.name")
    pais = serializers.CharField(source="city.country.name")
    localidad = serializers.CharField(source="locality", allow_null=True)
    moneda_codigo = serializers.CharField(source="currency.iso_code")
    moneda_simbolo = serializers.CharField(source="currency.symbol")
    precio_base = serializers.DecimalField(source="base_price", max_digits=12, decimal_places=2)
    capacidad_maxima = serializers.IntegerField(source="max_capacity")
    estado = serializers.CharField(source="status")
    imagen_url = serializers.CharField(source="image_url", allow_null=True)
    publicar_en = serializers.DateTimeField(source="publish_at", allow_null=True)
    retirar_en = serializers.DateTimeField(source="unpublish_at", allow_null=True)
    detalle = serializers.SerializerMethodField()
    paradas = TourStopSerializer(source="stops", many=True)
    salidas_proximas = serializers.IntegerField(source="upcoming_departures", default=0)
    proxima_salida = serializers.DateTimeField(source="next_departure", allow_null=True, default=None)
    aviso = serializers.SerializerMethodField()
    creado_en = serializers.DateTimeField(source="created_at")
    actualizado_en = serializers.DateTimeField(source="updated_at")

    class Meta:
        model = TourismProduct
        fields = (
            "id", "empresa_id", "empresa", "tipo_codigo", "tipo", "codigo", "nombre", "descripcion",
            "ciudad_id", "ciudad", "pais", "localidad", "moneda_codigo", "moneda_simbolo",
            "precio_base", "capacidad_maxima", "estado", "imagen_url", "publicar_en", "retirar_en",
            "detalle", "paradas", "salidas_proximas", "proxima_salida", "aviso", "creado_en", "actualizado_en",
        )

    @extend_schema_field(TourDetailSerializer(allow_null=True))
    def get_detalle(self, product) -> dict | None:
        """La ficha, o null en un tour del catalogo generico que todavia no la tiene."""
        detail = getattr(product, "tour", None) if hasattr(product, "tour") else None
        return TourDetailSerializer(detail).data if detail else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_aviso(self, product) -> str | None:
        return getattr(product, "notice", None)


class TourWriteSerializer(serializers.Serializer):
    """Alta y edicion de un tour con su ficha y, opcionalmente, su recorrido."""

    tipo_codigo = serializers.ChoiceField(choices=sorted(TOUR_PRODUCT_CODES), required=False)
    nombre = serializers.CharField(max_length=180, required=False)
    descripcion = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ciudad_id = serializers.IntegerField(min_value=1, required=False)
    localidad = serializers.CharField(max_length=180, required=False, allow_blank=True, allow_null=True)
    moneda_codigo = serializers.CharField(max_length=3, required=False)
    precio_base = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)
    capacidad_maxima = serializers.IntegerField(min_value=1, max_value=500, required=False)
    estado = serializers.ChoiceField(choices=TourismProduct.Status.choices, required=False)
    imagen_url = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)
    codigo = serializers.RegexField(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,59}$", required=False, allow_blank=True)
    duracion_minutos = serializers.IntegerField(min_value=1, max_value=10080, required=False, allow_null=True)
    idioma = serializers.CharField(max_length=80, required=False, allow_blank=True, allow_null=True)
    dificultad = serializers.ChoiceField(choices=TourDetail.Difficulty.choices, required=False, allow_null=True)
    edad_minima = serializers.IntegerField(min_value=0, max_value=120, required=False, allow_null=True)
    punto_encuentro = serializers.CharField(max_length=250, required=False, allow_blank=True, allow_null=True)
    latitud = CoordinateField(limit="90", required=False, allow_null=True)
    longitud = CoordinateField(limit="180", required=False, allow_null=True)
    incluye = serializers.ListField(child=serializers.CharField(max_length=120), required=False, max_length=30)
    no_incluye = serializers.ListField(child=serializers.CharField(max_length=120), required=False, max_length=30)
    requisitos = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    paradas = TourStopWriteSerializer(many=True, required=False)

    def validate_ciudad_id(self, value):
        if not City.objects.filter(id=value, active=True, country__active=True).exists():
            raise serializers.ValidationError("La ciudad no existe o está inactiva.")
        return value

    def validate_moneda_codigo(self, value):
        code = value.upper()
        if not Currency.objects.filter(iso_code=code).exists():
            raise serializers.ValidationError("La moneda no existe.")
        return code

    def validate(self, attrs):
        if not self.partial:
            required = ("nombre", "ciudad_id", "moneda_codigo", "precio_base", "capacidad_maxima")
            missing = [field for field in required if field not in attrs]
            if missing:
                raise serializers.ValidationError({field: "Este campo es obligatorio." for field in missing})
        check_coordinate_pair(attrs)
        return attrs


# --- Salidas -------------------------------------------------------------------


class DepartureSerializer(serializers.ModelSerializer):
    tour_id = serializers.IntegerField(source="product_id")
    inicio = serializers.DateTimeField(source="start")
    fin = serializers.DateTimeField(source="end")
    cupo = serializers.IntegerField(source="total_capacity")
    reservados = serializers.SerializerMethodField()
    disponibles = serializers.SerializerMethodField()
    cerrada = serializers.BooleanField(source="closed")
    guia_id = serializers.IntegerField(source="guide_id", allow_null=True)
    guia = serializers.CharField(source="guide.names", allow_null=True, default=None)

    class Meta:
        model = Availability
        fields = ("id", "tour_id", "inicio", "fin", "cupo", "reservados", "disponibles", "cerrada", "guia_id", "guia")

    def get_reservados(self, departure) -> int:
        return getattr(departure, "booked", 0)

    def get_disponibles(self, departure) -> int:
        if departure.closed:
            return 0
        return max(departure.total_capacity - getattr(departure, "booked", 0), 0)


class PublicDepartureSerializer(DepartureSerializer):
    """Lo que ve el turista: sin el telefono ni el id del guia."""

    guia_idiomas = serializers.ListField(source="guide.languages", child=serializers.CharField(), allow_null=True, default=None)

    class Meta(DepartureSerializer.Meta):
        fields = ("id", "tour_id", "inicio", "fin", "disponibles", "guia", "guia_idiomas")


class DepartureWriteSerializer(serializers.Serializer):
    inicio = serializers.DateTimeField(required=False)
    fin = serializers.DateTimeField(required=False, allow_null=True)
    cupo = serializers.IntegerField(min_value=1, max_value=500, required=False)
    guia_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    cerrada = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not self.partial and "inicio" not in attrs:
            raise serializers.ValidationError({"inicio": "Este campo es obligatorio."})
        if self.partial and attrs.get("fin", "") is None:
            raise serializers.ValidationError({"fin": "La hora de fin no puede quedar vacía."})
        return attrs


class RecurringDepartureSerializer(serializers.Serializer):
    """Salidas repetidas: dias de la semana (0 = lunes ... 6 = domingo) en un rango."""

    dias_semana = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6), allow_empty=False, max_length=7
    )
    hora_inicio = serializers.TimeField()
    hora_fin = serializers.TimeField(required=False, allow_null=True)
    desde = serializers.DateField()
    hasta = serializers.DateField()
    cupo = serializers.IntegerField(min_value=1, max_value=500, required=False)
    guia_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class RecurringResultSerializer(serializers.Serializer):
    creadas = DepartureSerializer(many=True)
    omitidas = serializers.IntegerField()


class DepartureRangeQuerySerializer(serializers.Serializer):
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)


# --- Guias ---------------------------------------------------------------------


class GuideSerializer(serializers.ModelSerializer):
    nombres = serializers.CharField(source="names")
    telefono = serializers.CharField(source="phone", allow_null=True)
    idiomas = serializers.ListField(source="languages", child=serializers.CharField())
    estado = serializers.CharField(source="status")
    creado_en = serializers.DateTimeField(source="created_at")

    class Meta:
        model = Guide
        fields = ("id", "nombres", "telefono", "idiomas", "estado", "creado_en")


class GuideWriteSerializer(serializers.Serializer):
    nombres = serializers.CharField(max_length=150, required=False)
    telefono = serializers.RegexField(r"^[0-9+()\- ]{6,30}$", required=False, allow_blank=True, allow_null=True)
    idiomas = serializers.ListField(child=serializers.CharField(max_length=40), required=False, max_length=10)
    estado = serializers.ChoiceField(choices=Guide.Status.choices, required=False)

    def validate_nombres(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Escribe el nombre completo del guía.")
        return value

    def validate(self, attrs):
        if not self.partial and "nombres" not in attrs:
            raise serializers.ValidationError({"nombres": "Este campo es obligatorio."})
        return attrs
