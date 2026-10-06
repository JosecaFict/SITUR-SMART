from typing import ClassVar

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.catalog.serializers import ProductSerializer

from .models import Itinerary, ItineraryActivity

# --- Entrada ----------------------------------------------------------------------


class ItineraryInputSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=120, trim_whitespace=True)
    ciudad_id = serializers.IntegerField(required=False, allow_null=True)
    inicio = serializers.DateField()
    fin = serializers.DateField()
    notas = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=2000)

    # nombre de la API -> nombre del servicio
    FIELDS: ClassVar[dict[str, str]] = {"nombre": "name", "ciudad_id": "city_id", "inicio": "start", "fin": "end", "notas": "notes"}

    def as_kwargs(self) -> dict:
        return {self.FIELDS[key]: value for key, value in self.validated_data.items()}


class ActivityInputSerializer(serializers.Serializer):
    fecha = serializers.DateField()
    hora = serializers.TimeField(required=False, allow_null=True)
    producto_id = serializers.IntegerField(required=False, allow_null=True)
    titulo = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=150)
    nota = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=1000)

    FIELDS: ClassVar[dict[str, str]] = {"fecha": "day", "hora": "at", "producto_id": "product_id", "titulo": "title", "nota": "note"}

    def as_kwargs(self) -> dict:
        return {self.FIELDS[key]: value for key, value in self.validated_data.items()}


class ActivityUpdateSerializer(ActivityInputSerializer):
    producto_id = None
    FIELDS: ClassVar[dict[str, str]] = {"fecha": "day", "hora": "at", "titulo": "title", "nota": "note"}


# --- Salida -----------------------------------------------------------------------


class ItinerarySummarySerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="name")
    ciudad_id = serializers.IntegerField(source="city_id", allow_null=True)
    ciudad = serializers.CharField(source="city.name", allow_null=True, default=None)
    inicio = serializers.DateField(source="start_date")
    fin = serializers.DateField(source="end_date")
    notas = serializers.CharField(source="notes", allow_null=True)
    dias = serializers.SerializerMethodField()
    actividades = serializers.SerializerMethodField()

    class Meta:
        model = Itinerary
        fields = ("id", "nombre", "ciudad_id", "ciudad", "inicio", "fin", "notas", "dias", "actividades")

    def get_dias(self, itinerary) -> int:
        return (itinerary.end_date - itinerary.start_date).days + 1

    def get_actividades(self, itinerary) -> int:
        count = getattr(itinerary, "activity_count", None)
        return count if count is not None else itinerary.activities.count()


class ActivitySerializer(serializers.ModelSerializer):
    tipo = serializers.SerializerMethodField()
    fecha = serializers.DateField(source="date")
    hora = serializers.TimeField(source="time", allow_null=True, format="%H:%M")
    titulo = serializers.CharField(source="title")
    nota = serializers.CharField(source="note", allow_null=True)
    producto = serializers.SerializerMethodField()

    class Meta:
        model = ItineraryActivity
        fields = ("id", "tipo", "fecha", "hora", "titulo", "nota", "producto")

    def get_tipo(self, activity) -> str:
        return "PRODUCTO" if activity.product_id else "LIBRE"

    @extend_schema_field(ProductSerializer(allow_null=True))
    def get_producto(self, activity) -> dict | None:
        product = getattr(activity, "visible_product", None)
        return ProductSerializer(product).data if product else None


def _booking_entry(entry) -> dict:
    booking = entry.booking
    product = entry.summary["producto"] or {}
    return {
        "tipo": "RESERVA",
        "reserva_id": booking.id,
        "codigo": booking.code,
        "momento": entry.moment,
        "titulo": product.get("establecimiento") or product.get("nombre") or booking.code,
        "producto": entry.summary["producto"],
        "fechas": entry.summary["fechas"],
    }


class ItineraryDetailSerializer(ItinerarySummarySerializer):
    """El itinerario con sus dias: reservas pagadas y actividades de cada uno."""

    agenda = serializers.SerializerMethodField()

    class Meta(ItinerarySummarySerializer.Meta):
        fields = (*ItinerarySummarySerializer.Meta.fields, "agenda")

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_agenda(self, itinerary) -> list[dict]:
        days = self.context["days"]
        return [
            {
                "fecha": day.date.isoformat(),
                "reservas": [_booking_entry(entry) for entry in day.bookings],
                "actividades": ActivitySerializer(day.activities, many=True).data,
            }
            for day in days
        ]

    def get_actividades(self, itinerary) -> int:
        return sum(len(day.activities) for day in self.context["days"])
