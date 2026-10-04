from django.db import migrations, models


ADD_ACTIVE_COLUMNS = """
ALTER TABLE pais
    ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE ciudad
    ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_pais_activo_nombre
    ON pais (activo, nombre);
CREATE INDEX IF NOT EXISTS idx_ciudad_pais_activo_nombre
    ON ciudad (id_pais, activo, nombre);
"""


def apply_location_status(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(ADD_ACTIVE_COLUMNS)
        cursor.execute("SELECT COUNT(*) FROM pais WHERE activo")
        countries = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM ciudad WHERE activo")
        cities = cursor.fetchone()[0]
        print(f"  ubicaciones activas: {countries} países | {cities} ciudades")


def revert_location_status(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS idx_ciudad_pais_activo_nombre")
        cursor.execute("DROP INDEX IF EXISTS idx_pais_activo_nombre")
        cursor.execute("ALTER TABLE ciudad DROP COLUMN IF EXISTS activo")
        cursor.execute("ALTER TABLE pais DROP COLUMN IF EXISTS activo")


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0004_plan_limites")]

    operations = [
        migrations.RunPython(apply_location_status, revert_location_status),
        migrations.AddField(
            model_name="country",
            name="active",
            field=models.BooleanField(db_column="activo", default=True),
        ),
        migrations.AddField(
            model_name="city",
            name="active",
            field=models.BooleanField(db_column="activo", default=True),
        ),
    ]
