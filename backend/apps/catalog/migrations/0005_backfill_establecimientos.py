from django.db import migrations

# Los productos de tipo HOTEL creados antes del modulo de hospedaje no tienen
# ficha de establecimiento: no admiten habitaciones y el Marketplace de
# hospedaje no los ve. Se les crea una ficha minima (tipo HOTEL, sin direccion
# ni estrellas) para que la empresa pueda completarla desde el panel.
#
# No se toca producto_turistico: ni el precio_base ni el estado. Un hotel
# heredado conserva su precio aunque ya no se muestre, y la consulta publica lo
# reporta sin precio "desde" hasta que tenga su primera habitacion publicada.
#
# Las habitaciones heredadas no se pueden reparar aqui: no hay forma de deducir
# a que hotel pertenecen. Siguen existiendo como productos y quedan fuera de
# /marketplace/habitaciones/ hasta que se registren de nuevo bajo su
# establecimiento.
BACKFILL = """
INSERT INTO establecimiento_hospedaje (id_producto, id_tenant, id_tipo_hospedaje, servicios)
SELECT p.id,
       p.id_tenant,
       (SELECT id FROM tipo_hospedaje WHERE codigo = 'HOTEL'),
       '[]'::JSONB
  FROM producto_turistico p
  JOIN tipo_producto tp ON tp.id = p.id_tipo_producto
 WHERE tp.codigo = 'HOTEL'
   AND NOT EXISTS (
       SELECT 1 FROM establecimiento_hospedaje e WHERE e.id_producto = p.id
   );
"""


def backfill_establishments(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(BACKFILL)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0004_hospedaje")]

    operations = [
        # Sin reverso: las fichas creadas aqui son indistinguibles de las que
        # cargue la empresa despues, y borrarlas en un rollback perderia datos
        # suyos. Volver atras de 0004 elimina la tabla completa de todos modos.
        migrations.RunPython(backfill_establishments, migrations.RunPython.noop),
    ]
