import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# Mismo DDL que database/migrations/013_itinerarios.sql, en forma idempotente:
# el deploy de Railway solo corre `migrate`.
CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS itinerario (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario      BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    nombre          VARCHAR(120) NOT NULL,
    id_ciudad       BIGINT REFERENCES ciudad(id) ON DELETE SET NULL,
    fecha_inicio    DATE NOT NULL,
    fecha_fin       DATE NOT NULL,
    notas           TEXT,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_itinerario_nombre CHECK (length(btrim(nombre)) > 0),
    CONSTRAINT chk_itinerario_fechas CHECK (fecha_fin >= fecha_inicio),
    CONSTRAINT chk_itinerario_duracion CHECK (fecha_fin - fecha_inicio < 60)
);

CREATE INDEX IF NOT EXISTS idx_itinerario_usuario_inicio
    ON itinerario (id_usuario, fecha_inicio DESC);

CREATE TABLE IF NOT EXISTS itinerario_actividad (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_itinerario   BIGINT NOT NULL REFERENCES itinerario(id) ON DELETE CASCADE,
    fecha           DATE NOT NULL,
    hora            TIME,
    id_producto     BIGINT REFERENCES producto_turistico(id) ON DELETE SET NULL,
    titulo          VARCHAR(150) NOT NULL,
    nota            TEXT,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_itinerario_actividad_titulo CHECK (length(btrim(titulo)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_itinerario_actividad_dia
    ON itinerario_actividad (id_itinerario, fecha, hora);
"""

DROP_TABLES = "DROP TABLE IF EXISTS itinerario_actividad; DROP TABLE IF EXISTS itinerario;"


def create_tables(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(CREATE_TABLES)


def drop_tables(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_TABLES)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0007_hospedaje_coordenadas"),
        ("tenancy", "0005_ubicaciones_activas"),
    ]

    operations = [
        migrations.RunPython(create_tables, drop_tables),
        migrations.CreateModel(
            name="Itinerary",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(db_column="nombre", max_length=120)),
                ("start_date", models.DateField(db_column="fecha_inicio")),
                ("end_date", models.DateField(db_column="fecha_fin")),
                ("notes", models.TextField(db_column="notas", null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                ("updated_at", models.DateTimeField(auto_now=True, db_column="actualizado_en")),
                (
                    "city",
                    models.ForeignKey(
                        db_column="id_ciudad",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="tenancy.city",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        db_column="id_usuario",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="itineraries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "itinerario",
                "ordering": ("-start_date", "-id"),
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="ItineraryActivity",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("date", models.DateField(db_column="fecha")),
                ("time", models.TimeField(db_column="hora", null=True)),
                ("title", models.CharField(db_column="titulo", max_length=150)),
                ("note", models.TextField(db_column="nota", null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                (
                    "itinerary",
                    models.ForeignKey(
                        db_column="id_itinerario",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activities",
                        to="itineraries.itinerary",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        db_column="id_producto",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="catalog.tourismproduct",
                    ),
                ),
            ],
            options={
                "db_table": "itinerario_actividad",
                "ordering": ("date", "time", "id"),
                "managed": False,
            },
        ),
    ]
