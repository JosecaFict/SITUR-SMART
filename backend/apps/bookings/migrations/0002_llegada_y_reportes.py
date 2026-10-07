import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# Mismo DDL que database/migrations/017_reservas_empresa.sql, idempotente.
APPLY = """
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS llegada_en TIMESTAMPTZ;
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS id_llegada_validada_por BIGINT REFERENCES usuario(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS reporte_cliente (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_tenant           BIGINT NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    id_cliente          BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    id_reserva          BIGINT REFERENCES reserva(id) ON DELETE SET NULL,
    id_reportado_por    BIGINT REFERENCES usuario(id) ON DELETE SET NULL,
    motivo              TEXT NOT NULL,
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_reporte_cliente_motivo CHECK (length(btrim(motivo)) >= 5)
);

CREATE INDEX IF NOT EXISTS idx_reporte_cliente_cliente ON reporte_cliente (id_cliente, creado_en DESC);
"""

REVERT = """
DROP TABLE IF EXISTS reporte_cliente;
ALTER TABLE reserva DROP COLUMN IF EXISTS id_llegada_validada_por;
ALTER TABLE reserva DROP COLUMN IF EXISTS llegada_en;
"""


def apply(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(APPLY)


def revert(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(REVERT)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("bookings", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(apply, revert),
        migrations.AddField(
            model_name="booking",
            name="checked_in_at",
            field=models.DateTimeField(db_column="llegada_en", null=True),
        ),
        migrations.AddField(
            model_name="booking",
            name="checked_in_by",
            field=models.ForeignKey(
                db_column="id_llegada_validada_por",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name="CustomerReport",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("reason", models.TextField(db_column="motivo")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                (
                    "booking",
                    models.ForeignKey(
                        db_column="id_reserva", null=True, on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+", to="bookings.booking",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        db_column="id_cliente", on_delete=django.db.models.deletion.CASCADE,
                        related_name="reports_received", to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reported_by",
                    models.ForeignKey(
                        db_column="id_reportado_por", null=True, on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+", to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="id_tenant", on_delete=django.db.models.deletion.CASCADE,
                        related_name="+", to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "reporte_cliente", "ordering": ("-created_at", "-id"), "managed": False},
        ),
    ]
