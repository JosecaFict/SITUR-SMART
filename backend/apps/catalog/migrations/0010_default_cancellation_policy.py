from django.db import migrations


FORWARDS = r"""
INSERT INTO politica_cancelacion (id_tenant, nombre, reembolsable)
SELECT t.id, 'Política estándar SITUR-SMART', TRUE
FROM tenant t
WHERE NOT EXISTS (
    SELECT 1
    FROM politica_cancelacion pc
    WHERE pc.id_tenant = t.id
      AND pc.nombre = 'Política estándar SITUR-SMART'
);

INSERT INTO regla_penalizacion (
    id_politica, dias_antes_min, dias_antes_max, porcentaje_penalizacion
)
SELECT pc.id, regla.dias_min, regla.dias_max, regla.porcentaje
FROM politica_cancelacion pc
CROSS JOIN (
    VALUES
        (0, 0, 100.00::NUMERIC(5,2)),
        (1, 2, 50.00::NUMERIC(5,2)),
        (3, 6, 25.00::NUMERIC(5,2)),
        (7, NULL::INTEGER, 0.00::NUMERIC(5,2))
) AS regla(dias_min, dias_max, porcentaje)
WHERE pc.nombre = 'Política estándar SITUR-SMART'
  AND NOT EXISTS (
      SELECT 1
      FROM regla_penalizacion rp
      WHERE rp.id_politica = pc.id
        AND rp.dias_antes_min = regla.dias_min
        AND rp.dias_antes_max IS NOT DISTINCT FROM regla.dias_max
  );

UPDATE producto_turistico producto
SET id_politica_cancelacion = politica.id
FROM politica_cancelacion politica
WHERE politica.id_tenant = producto.id_tenant
  AND politica.nombre = 'Política estándar SITUR-SMART'
  AND producto.id_politica_cancelacion IS NULL;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0009_cancellationpolicy_penaltyrule"),
    ]

    operations = [
        # Solo completa faltantes; el reverso no borra condiciones comerciales
        # ni desasocia productos que ya pudieron generar reservas.
        migrations.RunSQL(FORWARDS, reverse_sql=migrations.RunSQL.noop),
    ]
