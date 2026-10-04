from django.db import migrations, models

# Mismo DDL que database/migrations/008_hospedaje_coordenadas.sql, en forma
# idempotente: el deploy de Railway solo corre `migrate`, y la migracion tiene
# que poder aplicarse tanto sobre una base donde el script se ejecuto a mano
# como sobre una que nunca lo vio.
#
# ADD COLUMN si admite IF NOT EXISTS; ADD CONSTRAINT no, asi que se consulta
# pg_constraint antes de cada uno.
ADD_COORDINATES = """
ALTER TABLE establecimiento_hospedaje
    ADD COLUMN IF NOT EXISTS latitud  NUMERIC(9,6),
    ADD COLUMN IF NOT EXISTS longitud NUMERIC(9,6);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_establecimiento_latitud'
    ) THEN
        ALTER TABLE establecimiento_hospedaje ADD CONSTRAINT chk_establecimiento_latitud
            CHECK (latitud IS NULL OR latitud BETWEEN -90 AND 90);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_establecimiento_longitud'
    ) THEN
        ALTER TABLE establecimiento_hospedaje ADD CONSTRAINT chk_establecimiento_longitud
            CHECK (longitud IS NULL OR longitud BETWEEN -180 AND 180);
    END IF;

    -- Las dos juntas o ninguna: media coordenada no ubica nada. La regla se
    -- repite en el serializer para dar un 400 con mensaje, pero vive aqui para
    -- que tambien la respeten un comando de gestion, un shell o SQL externo.
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_establecimiento_coordenadas'
    ) THEN
        ALTER TABLE establecimiento_hospedaje ADD CONSTRAINT chk_establecimiento_coordenadas
            CHECK ((latitud IS NULL) = (longitud IS NULL));
    END IF;
END $$;
"""

DROP_COORDINATES = """
ALTER TABLE establecimiento_hospedaje
    DROP CONSTRAINT IF EXISTS chk_establecimiento_coordenadas,
    DROP CONSTRAINT IF EXISTS chk_establecimiento_longitud,
    DROP CONSTRAINT IF EXISTS chk_establecimiento_latitud;

ALTER TABLE establecimiento_hospedaje
    DROP COLUMN IF EXISTS longitud,
    DROP COLUMN IF EXISTS latitud;
"""


def add_coordinates(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(ADD_COORDINATES)


def drop_coordinates(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_COORDINATES)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0006_reconciliar_hoteles_publicados")]

    # Los AddField no emiten DDL: LodgingEstablishment es managed = False. Estan
    # para que el estado de Django coincida con la base y `makemigrations
    # --check` no vuelva a detectar los campos como nuevos.
    operations = [
        migrations.RunPython(add_coordinates, drop_coordinates),
        migrations.AddField(
            model_name="lodgingestablishment",
            name="latitude",
            field=models.DecimalField(
                blank=True, db_column="latitud", decimal_places=6, max_digits=9, null=True
            ),
        ),
        migrations.AddField(
            model_name="lodgingestablishment",
            name="longitude",
            field=models.DecimalField(
                blank=True, db_column="longitud", decimal_places=6, max_digits=9, null=True
            ),
        ),
    ]
