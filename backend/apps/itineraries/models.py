from django.conf import settings
from django.db import models


class Itinerary(models.Model):
    """Plan de un viaje del turista: un rango de dias con actividades."""

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_column="id_usuario",
        on_delete=models.CASCADE,
        related_name="itineraries",
    )
    name = models.CharField(db_column="nombre", max_length=120)
    city = models.ForeignKey(
        "tenancy.City",
        db_column="id_ciudad",
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    start_date = models.DateField(db_column="fecha_inicio")
    end_date = models.DateField(db_column="fecha_fin")
    notes = models.TextField(db_column="notas", null=True)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="actualizado_en", auto_now=True)

    class Meta:
        managed = False
        db_table = "itinerario"
        ordering = ("-start_date", "-id")


class ItineraryActivity(models.Model):
    """Algo que hacer un dia del viaje: un producto del Marketplace o algo libre."""

    id = models.BigAutoField(primary_key=True)
    itinerary = models.ForeignKey(
        Itinerary,
        db_column="id_itinerario",
        on_delete=models.CASCADE,
        related_name="activities",
    )
    date = models.DateField(db_column="fecha")
    time = models.TimeField(db_column="hora", null=True)
    product = models.ForeignKey(
        "catalog.TourismProduct",
        db_column="id_producto",
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    title = models.CharField(db_column="titulo", max_length=150)
    note = models.TextField(db_column="nota", null=True)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "itinerario_actividad"
        ordering = ("date", "time", "id")
