import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# Mismo DDL que database/migrations/015_suscripciones_vigencia.sql, en forma
# idempotente: el deploy de Railway solo corre `migrate`.
APPLY = """
ALTER TABLE suscripcion ADD COLUMN IF NOT EXISTS ultimo_aviso_dias SMALLINT;

UPDATE suscripcion
   SET fecha_fin = (
       fecha_inicio + make_interval(months => paso * (
           floor((date_part('year', age(current_date, fecha_inicio)) * 12
                  + date_part('month', age(current_date, fecha_inicio))) / paso)::int + 1
       ))
   )::date
  FROM (SELECT id AS id_s,
               CASE WHEN COALESCE(periodicidad_contratada, 'MENSUAL') = 'ANUAL' THEN 12 ELSE 1 END AS paso
          FROM suscripcion) p
 WHERE p.id_s = suscripcion.id
   AND estado = 'ACTIVA'
   AND fecha_fin IS NULL;

CREATE TABLE IF NOT EXISTS pago_suscripcion (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_tenant           BIGINT NOT NULL REFERENCES tenant(id) ON DELETE RESTRICT,
    id_plan             BIGINT NOT NULL REFERENCES plan(id) ON DELETE RESTRICT,
    id_suscripcion      BIGINT REFERENCES suscripcion(id) ON DELETE SET NULL,
    id_usuario_pagador  BIGINT REFERENCES usuario(id) ON DELETE SET NULL,
    id_moneda           BIGINT NOT NULL REFERENCES moneda(id) ON DELETE RESTRICT,
    monto               NUMERIC(12,2) NOT NULL,
    estado              VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
    proveedor           VARCHAR(60) NOT NULL DEFAULT 'STRIPE',
    referencia          VARCHAR(150),
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    procesado_en        TIMESTAMPTZ,

    CONSTRAINT uq_pago_suscripcion_referencia UNIQUE (proveedor, referencia),
    CONSTRAINT chk_pago_suscripcion_monto CHECK (monto > 0),
    CONSTRAINT chk_pago_suscripcion_estado CHECK (estado IN ('PENDIENTE', 'APROBADO', 'ANULADO'))
);

CREATE INDEX IF NOT EXISTS idx_pago_suscripcion_tenant ON pago_suscripcion (id_tenant, creado_en DESC);
"""

REVERT = """
DROP TABLE IF EXISTS pago_suscripcion;
ALTER TABLE suscripcion DROP COLUMN IF EXISTS ultimo_aviso_dias;
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
        ("catalog", "0007_hospedaje_coordenadas"),
        ("tenancy", "0005_ubicaciones_activas"),
    ]

    operations = [
        migrations.RunPython(apply, revert),
        migrations.AddField(
            model_name="subscription",
            name="last_notice_days",
            field=models.SmallIntegerField(db_column="ultimo_aviso_dias", null=True, blank=True),
        ),
        migrations.CreateModel(
            name="SubscriptionPayment",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("amount", models.DecimalField(db_column="monto", decimal_places=2, max_digits=12)),
                ("status", models.CharField(db_column="estado", default="PENDIENTE", max_length=20)),
                ("provider", models.CharField(db_column="proveedor", default="STRIPE", max_length=60)),
                ("reference", models.CharField(db_column="referencia", max_length=150, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                ("processed_at", models.DateTimeField(db_column="procesado_en", null=True)),
                (
                    "currency",
                    models.ForeignKey(
                        db_column="id_moneda",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="catalog.currency",
                    ),
                ),
                (
                    "payer",
                    models.ForeignKey(
                        db_column="id_usuario_pagador",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        db_column="id_plan",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="tenancy.plan",
                    ),
                ),
                (
                    "subscription",
                    models.ForeignKey(
                        db_column="id_suscripcion",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payments",
                        to="tenancy.subscription",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="id_tenant",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="subscription_payments",
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "pago_suscripcion", "ordering": ("-created_at", "-id"), "managed": False},
        ),
    ]
