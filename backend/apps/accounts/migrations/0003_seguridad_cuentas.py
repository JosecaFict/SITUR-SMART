import django.db.models.deletion
from django.db import migrations, models

# Mismo SQL que database/migrations/018_seguridad_cuentas.sql, idempotente.
APPLY = """
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS intentos_fallidos SMALLINT NOT NULL DEFAULT 0;
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS bloqueo_temporal_hasta TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS verificacion_correo (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario      BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    codigo_hash     TEXT NOT NULL,
    intentos        SMALLINT NOT NULL DEFAULT 0,
    expira_en       TIMESTAMPTZ NOT NULL,
    usado_en        TIMESTAMPTZ,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_verificacion_correo_usuario ON verificacion_correo (id_usuario, creado_en DESC);

-- Las cuentas que ya existian no se traban: se dan por verificadas.
UPDATE usuario SET email_verificado_en = COALESCE(email_verificado_en, creado_en)
 WHERE email_verificado_en IS NULL;
"""

REVERT = """
DROP TABLE IF EXISTS verificacion_correo;
ALTER TABLE usuario DROP COLUMN IF EXISTS bloqueo_temporal_hasta;
ALTER TABLE usuario DROP COLUMN IF EXISTS intentos_fallidos;
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
    dependencies = [("accounts", "0002_customerprofile")]

    operations = [
        migrations.RunPython(apply, revert),
        migrations.AddField(
            model_name="user",
            name="failed_logins",
            field=models.SmallIntegerField(db_column="intentos_fallidos", default=0),
        ),
        migrations.AddField(
            model_name="user",
            name="locked_until",
            field=models.DateTimeField(db_column="bloqueo_temporal_hasta", null=True, blank=True),
        ),
        migrations.CreateModel(
            name="EmailVerification",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("code_hash", models.TextField(db_column="codigo_hash")),
                ("attempts", models.SmallIntegerField(db_column="intentos", default=0)),
                ("expires_at", models.DateTimeField(db_column="expira_en")),
                ("used_at", models.DateTimeField(db_column="usado_en", null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                (
                    "user",
                    models.ForeignKey(
                        db_column="id_usuario", on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_verifications", to="accounts.user",
                    ),
                ),
            ],
            options={"db_table": "verificacion_correo", "managed": False},
        ),
    ]
