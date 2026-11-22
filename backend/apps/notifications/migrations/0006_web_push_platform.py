from django.db import migrations


def allow_web(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("ALTER TABLE dispositivo_push DROP CONSTRAINT IF EXISTS chk_dispositivo_push_plataforma")
        schema_editor.execute("""ALTER TABLE dispositivo_push ADD CONSTRAINT chk_dispositivo_push_plataforma
            CHECK (plataforma IN ('ANDROID', 'IOS', 'WEB'))""")


def remove_web(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DELETE FROM dispositivo_push WHERE plataforma = 'WEB'")
        schema_editor.execute("ALTER TABLE dispositivo_push DROP CONSTRAINT IF EXISTS chk_dispositivo_push_plataforma")
        schema_editor.execute("""ALTER TABLE dispositivo_push ADD CONSTRAINT chk_dispositivo_push_plataforma
            CHECK (plataforma IN ('ANDROID', 'IOS'))""")


class Migration(migrations.Migration):
    dependencies = [("notifications", "0005_communications_permission")]
    operations = [migrations.RunPython(allow_web, remove_web)]
