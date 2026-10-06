import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# Mismo DDL que database/migrations/009_favoritos.sql, en forma idempotente:
# el deploy de Railway solo corre `migrate`, y la migracion tiene que poder
# aplicarse tanto sobre una base donde el script se ejecuto a mano como sobre
# una que nunca lo vio.
CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS favorito (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario      BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    id_producto     BIGINT NOT NULL REFERENCES producto_turistico(id) ON DELETE CASCADE,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_favorito_usuario_producto UNIQUE (id_usuario, id_producto)
);

CREATE INDEX IF NOT EXISTS idx_favorito_usuario_creado
    ON favorito (id_usuario, creado_en DESC);
"""

DROP_TABLE = "DROP TABLE IF EXISTS favorito;"


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
        ("catalog", "0007_hospedaje_coordenadas"),
    ]

    operations = [
        migrations.RunPython(create_table, drop_table),
        migrations.CreateModel(
            name="Favorite",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                (
                    "product",
                    models.ForeignKey(
                        db_column="id_producto",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="favorites",
                        to="catalog.tourismproduct",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        db_column="id_usuario",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="favorites",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "favorito",
                "ordering": ("-created_at", "-id"),
                "managed": False,
            },
        ),
    ]
