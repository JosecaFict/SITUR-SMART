from django.db import migrations

# Los hoteles que existian antes del modulo de Hospedaje conservaron el estado
# que tenian. 0005 les creo su ficha, pero ninguno tiene habitaciones: quedaron
# PUBLICADO sin una sola habitacion publicada con precio, que es justo lo que la
# regla del modulo prohibe. "Palacio del sal" de ToursBo es uno de esos casos.
#
# Se los pasa a BORRADOR para que la empresa los complete y los publique de
# nuevo cuando tengan su primera habitacion.
#
# Dos aclaraciones sobre el alcance:
#
# 1. No hace falta distinguir un hotel heredado de uno nuevo. Un hotel creado
#    por /api/v1/hospedajes/ no puede estar publicado sin habitacion ofertable,
#    porque el servicio lo impide: la condicion de abajo solo puede ser cierta
#    para los heredados.
#
# 2. Un hotel que ya tenga una habitacion publicada con precio mayor a 0 nunca
#    se toca, por el NOT EXISTS.
#
# Esto repara el dato una vez. Que el estado no se vuelva a dar en el
# Marketplace lo garantiza aparte services._publishable_room_exists(), que lo
# exige en cada consulta publica: despublicar la ultima habitacion de un hotel
# publicado lo deja igual fuera de la oferta.
DEMOTE_INCOMPLETE_HOTELS = """
UPDATE producto_turistico p
   SET estado = 'BORRADOR'
 WHERE p.estado = 'PUBLICADO'
   AND EXISTS (
       SELECT 1 FROM tipo_producto tp
        WHERE tp.id = p.id_tipo_producto AND tp.codigo = 'HOTEL'
   )
   AND EXISTS (
       SELECT 1 FROM establecimiento_hospedaje e WHERE e.id_producto = p.id
   )
   AND NOT EXISTS (
       SELECT 1
         FROM habitacion h
         JOIN establecimiento_hospedaje e ON e.id = h.id_establecimiento
         JOIN producto_turistico hp ON hp.id = h.id_producto
        WHERE e.id_producto = p.id
          AND hp.estado = 'PUBLICADO'
          AND hp.precio_base > 0
   );
"""


def demote_incomplete_hotels(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(DEMOTE_INCOMPLETE_HOTELS)
        # Queda en el log del deploy cuantos hoteles se reconciliaron.
        print(f"  Hoteles incompletos pasados a BORRADOR: {cursor.rowcount}")


class Migration(migrations.Migration):
    dependencies = [("catalog", "0005_backfill_establecimientos")]

    operations = [
        # Sin reverso: volver a publicarlos reintroduciria el estado invalido, y
        # no hay registro de cuales estaban publicados antes. Es idempotente, asi
        # que repetirla no cambia nada.
        migrations.RunPython(demote_incomplete_hotels, migrations.RunPython.noop),
    ]
