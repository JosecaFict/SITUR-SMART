from django.db import migrations, models

# Mismo SQL que database/migrations/019_publicacion_programada.sql, idempotente.
APPLY = """
ALTER TABLE producto_turistico ADD COLUMN IF NOT EXISTS publicar_en TIMESTAMPTZ;
ALTER TABLE producto_turistico ADD COLUMN IF NOT EXISTS retirar_en TIMESTAMPTZ;
ALTER TABLE producto_turistico ADD COLUMN IF NOT EXISTS publicado_automaticamente_en TIMESTAMPTZ;

-- El cron busca lo que toca publicar o retirar: solo las filas programadas.
CREATE INDEX IF NOT EXISTS idx_producto_publicar_en ON producto_turistico (publicar_en) WHERE publicar_en IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_producto_retirar_en ON producto_turistico (retirar_en) WHERE retirar_en IS NOT NULL;
"""

REVERT = """
DROP INDEX IF EXISTS idx_producto_retirar_en;
DROP INDEX IF EXISTS idx_producto_publicar_en;
ALTER TABLE producto_turistico DROP COLUMN IF EXISTS publicado_automaticamente_en;
ALTER TABLE producto_turistico DROP COLUMN IF EXISTS retirar_en;
ALTER TABLE producto_turistico DROP COLUMN IF EXISTS publicar_en;
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
    dependencies = [("catalog", "0007_hospedaje_coordenadas")]

    operations = [
        migrations.RunPython(apply, revert),
        migrations.AddField(
            model_name="tourismproduct",
            name="publish_at",
            field=models.DateTimeField(db_column="publicar_en", null=True, blank=True),
        ),
        migrations.AddField(
            model_name="tourismproduct",
            name="unpublish_at",
            field=models.DateTimeField(db_column="retirar_en", null=True, blank=True),
        ),
        migrations.AddField(
            model_name="tourismproduct",
            name="auto_published_at",
            field=models.DateTimeField(db_column="publicado_automaticamente_en", null=True, blank=True),
        ),
    ]
