import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# Mismo DDL que database/migrations/014_respaldos_automaticos.sql, en forma
# idempotente: el deploy de Railway solo corre `migrate`.
CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS programacion_respaldo (
    id                  SMALLINT PRIMARY KEY DEFAULT 1,
    frecuencia          VARCHAR(20) NOT NULL DEFAULT 'SEMANAL',
    ultima_ejecucion    TIMESTAMPTZ,
    actualizado_en      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    id_actualizado_por  BIGINT REFERENCES usuario(id) ON DELETE SET NULL,

    CONSTRAINT chk_programacion_respaldo_unica CHECK (id = 1),
    CONSTRAINT chk_programacion_respaldo_frecuencia
        CHECK (frecuencia IN ('DESACTIVADA', 'CADA_3_DIAS', 'SEMANAL'))
);

INSERT INTO programacion_respaldo (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS copia_seguridad (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    archivo         VARCHAR(120) NOT NULL,
    id_almacen      VARCHAR(255) NOT NULL,
    tamano_bytes    BIGINT NOT NULL,
    sha256          CHAR(64) NOT NULL,
    origen          VARCHAR(20) NOT NULL,
    id_solicitada_por BIGINT REFERENCES usuario(id) ON DELETE SET NULL,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_copia_seguridad_almacen UNIQUE (id_almacen),
    CONSTRAINT chk_copia_seguridad_origen CHECK (origen IN ('PROGRAMADA', 'A_PEDIDO'))
);

CREATE INDEX IF NOT EXISTS idx_copia_seguridad_creado ON copia_seguridad (creado_en DESC);
"""

DROP_TABLES = "DROP TABLE IF EXISTS copia_seguridad; DROP TABLE IF EXISTS programacion_respaldo;"


def create_tables(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(CREATE_TABLES)


def drop_tables(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_TABLES)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(create_tables, drop_tables),
        migrations.CreateModel(
            name="BackupSchedule",
            fields=[
                ("id", models.SmallIntegerField(default=1, primary_key=True, serialize=False)),
                ("frequency", models.CharField(db_column="frecuencia", default="SEMANAL", max_length=20)),
                ("last_run", models.DateTimeField(db_column="ultima_ejecucion", null=True)),
                ("updated_at", models.DateTimeField(auto_now=True, db_column="actualizado_en")),
                (
                    "updated_by",
                    models.ForeignKey(
                        db_column="id_actualizado_por",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "programacion_respaldo", "managed": False},
        ),
        migrations.CreateModel(
            name="StoredBackup",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("filename", models.CharField(db_column="archivo", max_length=120)),
                ("storage_id", models.CharField(db_column="id_almacen", max_length=255, unique=True)),
                ("size", models.BigIntegerField(db_column="tamano_bytes")),
                ("sha256", models.CharField(max_length=64)),
                ("origin", models.CharField(db_column="origen", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                (
                    "requested_by",
                    models.ForeignKey(
                        db_column="id_solicitada_por",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "copia_seguridad", "ordering": ("-created_at", "-id"), "managed": False},
        ),
    ]
