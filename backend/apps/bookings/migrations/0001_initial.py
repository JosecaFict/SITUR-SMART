import django.db.models.expressions
from django.db import migrations, models

# Mismo DDL que database/migrations/010_reservas.sql, en forma idempotente: el
# deploy de Railway solo corre `migrate`. Las tablas de ordenes, reservas,
# detalle, bloqueos, pagos e historial ya existen desde 001_initial_schema.sql;
# aqui solo se registra su estado y se agrega lo que les falta.
ADD_GUESTS_AND_INDEXES = """
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS huespedes INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_reserva_huespedes') THEN
        ALTER TABLE reserva ADD CONSTRAINT chk_reserva_huespedes
            CHECK (huespedes IS NULL OR huespedes > 0);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_reserva_detalle_disponibilidad ON reserva_detalle (id_disponibilidad);
CREATE INDEX IF NOT EXISTS idx_bloqueo_disponibilidad_activo
    ON bloqueo_inventario (id_disponibilidad) WHERE estado = 'ACTIVO';
CREATE INDEX IF NOT EXISTS idx_orden_cliente ON orden_reserva (id_cliente, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_pago_reserva ON pago (id_reserva);
"""

DROP_GUESTS_AND_INDEXES = """
DROP INDEX IF EXISTS idx_pago_reserva;
DROP INDEX IF EXISTS idx_orden_cliente;
DROP INDEX IF EXISTS idx_bloqueo_disponibilidad_activo;
DROP INDEX IF EXISTS idx_reserva_detalle_disponibilidad;
ALTER TABLE reserva DROP CONSTRAINT IF EXISTS chk_reserva_huespedes;
ALTER TABLE reserva DROP COLUMN IF EXISTS huespedes;
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(ADD_GUESTS_AND_INDEXES)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_GUESTS_AND_INDEXES)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0002_customerprofile"),
        ("catalog", "0007_hospedaje_coordenadas"),
        ("tenancy", "0005_ubicaciones_activas"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.CreateModel(
            name='Booking',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('code', models.CharField(db_column='codigo_reserva', max_length=60)),
                ('status', models.CharField(db_column='estado', default='CREADA', max_length=25)),
                ('expires_at', models.DateTimeField(db_column='fecha_expiracion', null=True)),
                ('guests', models.PositiveIntegerField(db_column='huespedes', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='creado_en')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='actualizado_en')),
            ],
            options={
                'db_table': 'reserva',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='BookingDetail',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('quantity', models.PositiveIntegerField(db_column='cantidad_personas')),
                ('unit_price', models.DecimalField(db_column='precio_unitario', decimal_places=2, max_digits=12)),
                ('subtotal', models.GeneratedField(db_column='subtotal', db_persist=True, expression=django.db.models.expressions.CombinedExpression(models.F('quantity'), '*', models.F('unit_price')), output_field=models.DecimalField(decimal_places=2, max_digits=14))),
            ],
            options={
                'db_table': 'reserva_detalle',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='BookingStatusHistory',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('previous_status', models.CharField(db_column='estado_anterior', max_length=25, null=True)),
                ('new_status', models.CharField(db_column='estado_nuevo', max_length=25)),
                ('reason', models.TextField(db_column='motivo', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='creado_en')),
            ],
            options={
                'db_table': 'historial_estado_reserva',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='InventoryLock',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('quantity', models.PositiveIntegerField(db_column='cantidad')),
                ('expires_at', models.DateTimeField(db_column='fecha_expiracion')),
                ('status', models.CharField(db_column='estado', default='ACTIVO', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='creado_en')),
            ],
            options={
                'db_table': 'bloqueo_inventario',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('code', models.CharField(db_column='codigo', max_length=60, unique=True)),
                ('status', models.CharField(db_column='estado', default='CREADA', max_length=25)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='creado_en')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='actualizado_en')),
            ],
            options={
                'db_table': 'orden_reserva',
                'managed': False,
            },
        ),
    ]
