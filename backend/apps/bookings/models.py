"""Ordenes y reservas sobre las tablas de 001_initial_schema.sql.

Una orden es global al turista y agrupa reservas; cada reserva es de una sola
empresa y una sola moneda. Hoy cada orden lleva una reserva (se reserva un
producto a la vez), pero el modelo ya admite el carrito multiempresa.
"""

from django.conf import settings
from django.db import models


class BookingState(models.TextChoices):
    CREATED = "CREADA", "Pendiente de pago"
    PARTIAL = "PAGO_PARCIAL", "Pago parcial"
    CONFIRMED = "CONFIRMADA", "Confirmada"
    CANCELLED = "CANCELADA", "Cancelada"
    EXPIRED = "EXPIRADA_LIBERADA", "Expirada"
    COMPLETED = "COMPLETADA", "Completada"


class OrderState(models.TextChoices):
    CREATED = "CREADA", "Pendiente de pago"
    PARTIAL = "PAGO_PARCIAL", "Pago parcial"
    CONFIRMED = "CONFIRMADA", "Confirmada"
    CANCELLED = "CANCELADA", "Cancelada"
    EXPIRED = "EXPIRADA", "Expirada"
    COMPLETED = "COMPLETADA", "Completada"


class Order(models.Model):
    id = models.BigAutoField(primary_key=True)
    customer = models.ForeignKey(
        "accounts.CustomerProfile",
        db_column="id_cliente",
        on_delete=models.DO_NOTHING,
        related_name="orders",
    )
    code = models.CharField(db_column="codigo", max_length=60, unique=True)
    status = models.CharField(db_column="estado", max_length=25, default=OrderState.CREATED)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="actualizado_en", auto_now=True)

    class Meta:
        managed = False
        db_table = "orden_reserva"


class Booking(models.Model):
    id = models.BigAutoField(primary_key=True)
    order = models.ForeignKey(
        Order, db_column="id_orden", on_delete=models.DO_NOTHING, related_name="bookings"
    )
    tenant = models.ForeignKey(
        "tenancy.Tenant", db_column="id_tenant", on_delete=models.DO_NOTHING, related_name="bookings"
    )
    currency = models.ForeignKey(
        "catalog.Currency", db_column="id_moneda", on_delete=models.DO_NOTHING, related_name="+"
    )
    code = models.CharField(db_column="codigo_reserva", max_length=60)
    status = models.CharField(db_column="estado", max_length=25, default=BookingState.CREATED)
    expires_at = models.DateTimeField(db_column="fecha_expiracion", null=True)
    guests = models.PositiveIntegerField(db_column="huespedes", null=True)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)
    updated_at = models.DateTimeField(db_column="actualizado_en", auto_now=True)

    class Meta:
        managed = False
        db_table = "reserva"


class BookingDetail(models.Model):
    """Una linea por cupo: cada noche de una habitacion o el dia de un tour.

    ``quantity`` es la unidad del cupo: habitaciones en un hospedaje, personas
    en lo demas. ``subtotal`` lo calcula PostgreSQL (columna generada).
    """

    id = models.BigAutoField(primary_key=True)
    booking = models.ForeignKey(
        Booking, db_column="id_reserva", on_delete=models.DO_NOTHING, related_name="details"
    )
    tenant = models.ForeignKey(
        "tenancy.Tenant", db_column="id_tenant", on_delete=models.DO_NOTHING, related_name="+"
    )
    slot = models.ForeignKey(
        "catalog.Availability",
        db_column="id_disponibilidad",
        on_delete=models.DO_NOTHING,
        related_name="booking_details",
    )
    quantity = models.PositiveIntegerField(db_column="cantidad_personas")
    unit_price = models.DecimalField(db_column="precio_unitario", max_digits=12, decimal_places=2)
    subtotal = models.GeneratedField(
        expression=models.F("quantity") * models.F("unit_price"),
        output_field=models.DecimalField(max_digits=14, decimal_places=2),
        db_persist=True,
        db_column="subtotal",
    )

    class Meta:
        managed = False
        db_table = "reserva_detalle"


class InventoryLock(models.Model):
    """Cupo apartado mientras el turista paga. Vence solo con el tiempo."""

    class State(models.TextChoices):
        ACTIVE = "ACTIVO", "Activo"
        RELEASED = "LIBERADO", "Liberado"
        CONSUMED = "CONSUMIDO", "Consumido"
        EXPIRED = "EXPIRADO", "Expirado"

    id = models.BigAutoField(primary_key=True)
    slot = models.ForeignKey(
        "catalog.Availability", db_column="id_disponibilidad", on_delete=models.DO_NOTHING, related_name="locks"
    )
    booking = models.ForeignKey(
        Booking, db_column="id_reserva", on_delete=models.DO_NOTHING, related_name="locks"
    )
    tenant = models.ForeignKey(
        "tenancy.Tenant", db_column="id_tenant", on_delete=models.DO_NOTHING, related_name="+"
    )
    quantity = models.PositiveIntegerField(db_column="cantidad")
    expires_at = models.DateTimeField(db_column="fecha_expiracion")
    status = models.CharField(db_column="estado", max_length=20, default=State.ACTIVE)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "bloqueo_inventario"


class BookingStatusHistory(models.Model):
    id = models.BigAutoField(primary_key=True)
    booking = models.ForeignKey(
        Booking, db_column="id_reserva", on_delete=models.DO_NOTHING, related_name="history"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, db_column="id_usuario", on_delete=models.DO_NOTHING, null=True, related_name="+"
    )
    previous_status = models.CharField(db_column="estado_anterior", max_length=25, null=True)
    new_status = models.CharField(db_column="estado_nuevo", max_length=25)
    reason = models.TextField(db_column="motivo", null=True)
    created_at = models.DateTimeField(db_column="creado_en", auto_now_add=True)

    class Meta:
        managed = False
        db_table = "historial_estado_reserva"
