import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# Mismo DDL que database/migrations/012_dispositivos_push.sql, en forma
# idempotente: el deploy de Railway solo corre `migrate`.
CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS dispositivo_push (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario      BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    token           VARCHAR(512) NOT NULL,
    plataforma      VARCHAR(20) NOT NULL DEFAULT 'ANDROID',
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_dispositivo_push_token UNIQUE (token),
    CONSTRAINT chk_dispositivo_push_plataforma CHECK (plataforma IN ('ANDROID', 'IOS'))
);

CREATE INDEX IF NOT EXISTS idx_dispositivo_push_usuario ON dispositivo_push (id_usuario);
"""

DROP_TABLE = "DROP TABLE IF EXISTS dispositivo_push;"


def create_table(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(CREATE_TABLE)


def drop_table(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_TABLE)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_table, drop_table),
        migrations.CreateModel(
            name="PushDevice",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("token", models.CharField(max_length=512, unique=True)),
                ("platform", models.CharField(db_column="plataforma", default="ANDROID", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                ("updated_at", models.DateTimeField(auto_now=True, db_column="actualizado_en")),
                (
                    "user",
                    models.ForeignKey(
                        db_column="id_usuario",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="push_devices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "dispositivo_push",
                "managed": False,
            },
        ),
    ]
