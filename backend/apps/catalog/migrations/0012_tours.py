from pathlib import Path
from typing import ClassVar

import django.db.models.deletion
from django.db import migrations, models

# El DDL es el de database/migrations/022_tours.sql, que ya es idempotente
# (IF NOT EXISTS y consulta a pg_constraint). Se lee del archivo en vez de
# copiarlo para que el script y la migracion no puedan quedar distintos; solo
# se quitan BEGIN y COMMIT porque la migracion ya corre en su transaccion.
SQL_FILE = Path(__file__).resolve().parents[3] / "database" / "migrations" / "022_tours.sql"

DROP_TOURS = """
DROP INDEX IF EXISTS idx_disponibilidad_guia;
ALTER TABLE disponibilidad DROP CONSTRAINT IF EXISTS fk_disponibilidad_guia_tenant;
ALTER TABLE disponibilidad DROP COLUMN IF EXISTS id_guia;
DROP TABLE IF EXISTS guia;
DROP TABLE IF EXISTS parada_tour;
DROP TABLE IF EXISTS detalle_tour;
"""


def _tours_sql() -> str:
    lines = SQL_FILE.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if line.strip() not in ("BEGIN;", "COMMIT;"))


def create_tour_tables(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(_tours_sql())


def drop_tour_tables(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_TOURS)


class Migration(migrations.Migration):
    dependencies: ClassVar = [
        ("catalog", "0011_merge_cancelaciones_resenas"),
        ("tenancy", "0006_suscripciones_vigencia"),
    ]

    # Los modelos son managed = False: CreateModel y AddField no emiten DDL,
    # solo dejan el estado de Django igual a la base.
    operations: ClassVar = [
        migrations.RunPython(create_tour_tables, drop_tour_tables),
        migrations.CreateModel(
            name="TourDetail",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("duration_minutes", models.PositiveIntegerField(blank=True, db_column="duracion_minutos", null=True)),
                ("language", models.CharField(blank=True, db_column="idioma", max_length=80, null=True)),
                (
                    "difficulty",
                    models.CharField(
                        blank=True,
                        choices=[("BAJA", "Baja"), ("MEDIA", "Media"), ("ALTA", "Alta")],
                        db_column="dificultad",
                        max_length=10,
                        null=True,
                    ),
                ),
                ("minimum_age", models.PositiveSmallIntegerField(blank=True, db_column="edad_minima", null=True)),
                ("meeting_point", models.CharField(blank=True, db_column="punto_encuentro", max_length=250, null=True)),
                ("latitude", models.DecimalField(blank=True, db_column="latitud", decimal_places=6, max_digits=9, null=True)),
                ("longitude", models.DecimalField(blank=True, db_column="longitud", decimal_places=6, max_digits=9, null=True)),
                ("includes", models.JSONField(blank=True, db_column="incluye", default=list)),
                ("excludes", models.JSONField(blank=True, db_column="no_incluye", default=list)),
                ("requirements", models.TextField(blank=True, db_column="requisitos", null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                ("updated_at", models.DateTimeField(auto_now=True, db_column="actualizado_en")),
                (
                    "product",
                    models.OneToOneField(
                        db_column="id_producto",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="tour",
                        to="catalog.tourismproduct",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="id_tenant",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="tours",
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "detalle_tour", "ordering": ("id",), "managed": False},
        ),
        migrations.CreateModel(
            name="TourStop",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("order", models.PositiveSmallIntegerField(db_column="orden")),
                ("name", models.CharField(db_column="nombre", max_length=150)),
                ("description", models.TextField(blank=True, db_column="descripcion", null=True)),
                ("duration_minutes", models.PositiveIntegerField(blank=True, db_column="duracion_minutos", null=True)),
                (
                    "product",
                    models.ForeignKey(
                        db_column="id_producto",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="stops",
                        to="catalog.tourismproduct",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="id_tenant",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "parada_tour", "ordering": ("order", "id"), "managed": False},
        ),
        migrations.CreateModel(
            name="Guide",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("names", models.CharField(db_column="nombres", max_length=150)),
                ("phone", models.CharField(blank=True, db_column="telefono", max_length=30, null=True)),
                ("languages", models.JSONField(blank=True, db_column="idiomas", default=list)),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVO", "Activo"), ("INACTIVO", "Inactivo")],
                        db_column="estado",
                        default="ACTIVO",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                ("updated_at", models.DateTimeField(auto_now=True, db_column="actualizado_en")),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="id_tenant",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="guides",
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "guia", "ordering": ("names", "id"), "managed": False},
        ),
        migrations.AddField(
            model_name="availability",
            name="guide",
            field=models.ForeignKey(
                blank=True,
                db_column="id_guia",
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="departures",
                to="catalog.guide",
            ),
        ),
    ]
