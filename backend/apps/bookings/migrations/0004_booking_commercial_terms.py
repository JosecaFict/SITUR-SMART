from django.db import migrations, models


APPLY = r"""
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS monto_original NUMERIC(12,2);
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS monto_descuento NUMERIC(12,2);
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS monto_final NUMERIC(12,2);
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS politica_cancelacion_snapshot JSONB;
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS politica_aceptada_en TIMESTAMPTZ;

WITH importes AS (
    SELECT rd.id_reserva, SUM(rd.cantidad_personas * rd.precio_unitario)::NUMERIC(12,2) AS total
    FROM reserva_detalle rd
    GROUP BY rd.id_reserva
)
UPDATE reserva r
SET monto_original = COALESCE(r.monto_original, importes.total),
    monto_descuento = COALESCE(r.monto_descuento, 0),
    monto_final = COALESCE(r.monto_final, importes.total)
FROM importes
WHERE r.id = importes.id_reserva;

WITH primer_producto AS (
    SELECT DISTINCT ON (rd.id_reserva)
        rd.id_reserva,
        d.id_producto
    FROM reserva_detalle rd
    JOIN disponibilidad d ON d.id = rd.id_disponibilidad
    ORDER BY rd.id_reserva, d.inicio, rd.id
), snapshots AS (
    SELECT primer_producto.id_reserva,
    jsonb_build_object(
        'policy_id', pc.id,
        'name', pc.nombre,
        'refundable', pc.reembolsable,
        'source', 'LEGACY_BACKFILL',
        'rules', COALESCE(
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'rule_id', rp.id,
                        'minimum_days', rp.dias_antes_min,
                        'maximum_days', rp.dias_antes_max,
                        'penalty_percentage', rp.porcentaje_penalizacion::TEXT
                    )
                    ORDER BY rp.dias_antes_min, rp.id
                )
                FROM regla_penalizacion rp
                WHERE rp.id_politica = pc.id
            ),
            '[]'::JSONB
        )
    ) AS snapshot
    FROM primer_producto
    JOIN producto_turistico pt ON pt.id = primer_producto.id_producto
    JOIN politica_cancelacion pc ON pc.id = pt.id_politica_cancelacion
)
UPDATE reserva r
SET politica_cancelacion_snapshot = snapshots.snapshot
FROM snapshots
WHERE snapshots.id_reserva = r.id
  AND r.politica_cancelacion_snapshot IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_reserva_importes_comerciales'
    ) THEN
        ALTER TABLE reserva ADD CONSTRAINT chk_reserva_importes_comerciales CHECK (
            (monto_original IS NULL AND monto_descuento IS NULL AND monto_final IS NULL)
            OR (
                monto_original >= 0
                AND monto_descuento >= 0
                AND monto_final >= 0
                AND monto_descuento <= monto_original
                AND monto_final = monto_original - monto_descuento
            )
        );
    END IF;
END $$;
"""


REVERT = r"""
ALTER TABLE reserva DROP CONSTRAINT IF EXISTS chk_reserva_importes_comerciales;
ALTER TABLE reserva DROP COLUMN IF EXISTS politica_aceptada_en;
ALTER TABLE reserva DROP COLUMN IF EXISTS politica_cancelacion_snapshot;
ALTER TABLE reserva DROP COLUMN IF EXISTS monto_final;
ALTER TABLE reserva DROP COLUMN IF EXISTS monto_descuento;
ALTER TABLE reserva DROP COLUMN IF EXISTS monto_original;
"""


def apply(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(APPLY)


def revert(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(REVERT)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0010_default_cancellation_policy"),
        ("bookings", "0003_cancellation"),
    ]

    operations = [
        migrations.RunPython(apply, revert),
        migrations.AddField(
            model_name="booking",
            name="original_amount",
            field=models.DecimalField(
                db_column="monto_original", decimal_places=2, max_digits=12, null=True
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="discount_amount",
            field=models.DecimalField(
                db_column="monto_descuento", decimal_places=2, max_digits=12, null=True
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="final_amount",
            field=models.DecimalField(
                db_column="monto_final", decimal_places=2, max_digits=12, null=True
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="cancellation_policy_snapshot",
            field=models.JSONField(db_column="politica_cancelacion_snapshot", null=True),
        ),
        migrations.AddField(
            model_name="booking",
            name="policy_accepted_at",
            field=models.DateTimeField(db_column="politica_aceptada_en", null=True),
        ),
    ]
