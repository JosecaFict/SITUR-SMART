import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# Mismo DDL que database/migrations/011_notificaciones.sql, en forma
# idempotente: el deploy de Railway solo corre `migrate`.
CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS notificacion (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario      BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    tipo            VARCHAR(40) NOT NULL,
    titulo          VARCHAR(150) NOT NULL,
    mensaje         TEXT NOT NULL,
    datos           JSONB NOT NULL DEFAULT '{}'::JSONB,
    leida_en        TIMESTAMPTZ,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_notificacion_datos CHECK (jsonb_typeof(datos) = 'object')
);

-- La bandeja se lee por usuario, de la mas nueva a la mas vieja.
CREATE INDEX IF NOT EXISTS idx_notificacion_usuario_creado
    ON notificacion (id_usuario, creado_en DESC);
-- El contador de no leidas se consulta seguido y solo mira esas filas.
CREATE INDEX IF NOT EXISTS idx_notificacion_no_leidas
    ON notificacion (id_usuario) WHERE leida_en IS NULL;
"""

DROP_TABLE = "DROP TABLE IF EXISTS notificacion;"


def create_table(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(CREATE_TABLE)


def drop_table(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_TABLE)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0002_customerprofile"),
    ]

    operations = [
        migrations.RunPython(create_table, drop_table),
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("kind", models.CharField(db_column="tipo", max_length=40)),
                ("title", models.CharField(db_column="titulo", max_length=150)),
                ("message", models.TextField(db_column="mensaje")),
                ("data", models.JSONField(db_column="datos", default=dict)),
                ("read_at", models.DateTimeField(db_column="leida_en", null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                (
                    "user",
                    models.ForeignKey(
                        db_column="id_usuario",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "notificacion",
                "ordering": ("-created_at", "-id"),
                "managed": False,
            },
        ),
    ]
