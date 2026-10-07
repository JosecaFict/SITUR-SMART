from django.db import migrations

# Mismo SQL que database/migrations/016_permiso_clientes.sql, idempotente.
APPLY = """
INSERT INTO permiso (codigo, modulo, nombre)
VALUES ('CLIENTES_GESTIONAR', 'Usuarios', 'Administrar cuentas de turistas')
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO rol_permiso (id_rol, id_permiso)
SELECT r.id, p.id
  FROM rol r
  JOIN permiso p ON p.codigo = 'CLIENTES_GESTIONAR'
 WHERE r.codigo = 'SUPER_ADMIN' AND r.ambito = 'GLOBAL'
ON CONFLICT DO NOTHING;
"""

REVERT = """
DELETE FROM rol_permiso WHERE id_permiso IN (SELECT id FROM permiso WHERE codigo = 'CLIENTES_GESTIONAR');
DELETE FROM permiso WHERE codigo = 'CLIENTES_GESTIONAR';
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
    dependencies = [("rbac", "0001_initial")]

    operations = [migrations.RunPython(apply, revert)]
