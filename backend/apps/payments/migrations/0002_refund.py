from django.conf import settings
from django.db import migrations, models


APPLY = r"""
CREATE TABLE IF NOT EXISTS reembolso (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_pago                 BIGINT NOT NULL REFERENCES pago(id) ON DELETE RESTRICT,
    id_cancelacion          BIGINT NOT NULL REFERENCES cancelacion(id) ON DELETE RESTRICT,
    id_moneda               BIGINT NOT NULL REFERENCES moneda(id) ON DELETE RESTRICT,
    monto                   NUMERIC(12,2) NOT NULL,
    estado                  VARCHAR(20) NOT NULL DEFAULT 'SOLICITADO',
    motivo                  TEXT,
    proveedor               VARCHAR(60) NOT NULL DEFAULT 'STRIPE',
    referencia_proveedor    VARCHAR(150),
    idempotency_key         VARCHAR(100) NOT NULL UNIQUE,
    id_solicitado_por       BIGINT NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
    solicitado_en           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    procesado_en            TIMESTAMPTZ,
    motivo_fallo            TEXT,

    CONSTRAINT uq_reembolso_proveedor_referencia UNIQUE (proveedor, referencia_proveedor),
    CONSTRAINT chk_reembolso_monto CHECK (monto > 0),
    CONSTRAINT chk_reembolso_estado CHECK (
        estado IN ('SOLICITADO', 'PROCESANDO', 'COMPLETADO', 'FALLIDO', 'CANCELADO')
    )
);

CREATE INDEX IF NOT EXISTS idx_reembolso_pago ON reembolso (id_pago, solicitado_en DESC);
CREATE INDEX IF NOT EXISTS idx_reembolso_estado ON reembolso (estado, solicitado_en);

CREATE OR REPLACE FUNCTION fn_validar_reembolso()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_reserva_pago BIGINT;
    v_reserva_cancelacion BIGINT;
    v_moneda_pago BIGINT;
    v_estado_pago VARCHAR(20);
    v_monto_pago NUMERIC(12,2);
    v_total_reembolsado NUMERIC(12,2);
BEGIN
    SELECT id_reserva, id_moneda, estado, monto
    INTO v_reserva_pago, v_moneda_pago, v_estado_pago, v_monto_pago
    FROM pago WHERE id = NEW.id_pago;

    SELECT id_reserva INTO v_reserva_cancelacion
    FROM cancelacion WHERE id = NEW.id_cancelacion;

    IF v_reserva_pago <> v_reserva_cancelacion THEN
        RAISE EXCEPTION 'El pago y la cancelacion pertenecen a reservas diferentes';
    END IF;
    IF v_moneda_pago <> NEW.id_moneda THEN
        RAISE EXCEPTION 'La moneda del reembolso debe coincidir con la del pago';
    END IF;
    IF v_estado_pago <> 'APROBADO' THEN
        RAISE EXCEPTION 'Solo se puede reembolsar un pago aprobado';
    END IF;

    SELECT COALESCE(SUM(monto), 0) INTO v_total_reembolsado
    FROM reembolso
    WHERE id_pago = NEW.id_pago
      AND estado NOT IN ('FALLIDO', 'CANCELADO')
      AND id <> COALESCE(NEW.id, 0);

    IF NEW.estado NOT IN ('FALLIDO', 'CANCELADO')
       AND v_total_reembolsado + NEW.monto > v_monto_pago THEN
        RAISE EXCEPTION 'El total reembolsado no puede superar el monto pagado';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validar_reembolso ON reembolso;
CREATE TRIGGER trg_validar_reembolso
BEFORE INSERT OR UPDATE OF id_pago, id_cancelacion, id_moneda, monto, estado ON reembolso
FOR EACH ROW EXECUTE FUNCTION fn_validar_reembolso();
"""


REVERT = r"""
DROP TRIGGER IF EXISTS trg_validar_reembolso ON reembolso;
DROP FUNCTION IF EXISTS fn_validar_reembolso();
DROP TABLE IF EXISTS reembolso;
"""


def apply(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(APPLY)


def revert(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(REVERT)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("bookings", "0004_booking_commercial_terms"),
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(apply, revert),
        migrations.CreateModel(
            name="Refund",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("amount", models.DecimalField(db_column="monto", decimal_places=2, max_digits=12)),
                ("status", models.CharField(db_column="estado", default="SOLICITADO", max_length=20)),
                ("reason", models.TextField(db_column="motivo", null=True)),
                ("provider", models.CharField(db_column="proveedor", default="STRIPE", max_length=60)),
                ("provider_reference", models.CharField(db_column="referencia_proveedor", max_length=150, null=True)),
                ("idempotency_key", models.CharField(db_column="idempotency_key", max_length=100, unique=True)),
                ("requested_at", models.DateTimeField(auto_now_add=True, db_column="solicitado_en")),
                ("processed_at", models.DateTimeField(db_column="procesado_en", null=True)),
                ("failure_reason", models.TextField(db_column="motivo_fallo", null=True)),
            ],
            options={"db_table": "reembolso", "managed": False, "ordering": ("-requested_at", "-id")},
        ),
    ]
