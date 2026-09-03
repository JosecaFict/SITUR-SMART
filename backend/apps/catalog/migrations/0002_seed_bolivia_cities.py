from django.db import migrations


def seed_bolivia_cities(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        INSERT INTO ciudad (id_pais, nombre, latitud, longitud, zona_horaria)
        SELECT p.id, city.nombre, city.latitud, city.longitud, 'America/La_Paz'
        FROM pais p
        CROSS JOIN (VALUES
            ('Santa Cruz de la Sierra', -17.783333, -63.182222),
            ('La Paz', -16.500000, -68.150000),
            ('Cochabamba', -17.393500, -66.157000),
            ('Sucre', -19.033320, -65.262740),
            ('Uyuni', -20.460350, -66.825320),
            ('Samaipata', -18.180050, -63.875520),
            ('Rurrenabaque', -14.441250, -67.527810),
            ('Copacabana', -16.165510, -69.086280),
            ('Potosí', -19.583610, -65.753060)
        ) AS city(nombre, latitud, longitud)
        WHERE p.codigo_iso = 'BOL'
        ON CONFLICT (id_pais, nombre) DO NOTHING
        """
    )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_catalog_api")]

    operations = [migrations.RunPython(seed_bolivia_cities, migrations.RunPython.noop)]
