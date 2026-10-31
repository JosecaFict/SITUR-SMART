import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# Mismo DDL que database/migrations/020_resenas_producto.sql. Las tablas
# heredadas son managed=False: migrate debe crear esta tabla en PostgreSQL,
# y tambien poder registrar su estado si el script SQL se ejecuto antes.
CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS resena_producto (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_usuario      BIGINT NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    id_producto     BIGINT NOT NULL REFERENCES producto_turistico(id) ON DELETE CASCADE,
    calificacion    SMALLINT NOT NULL,
    comentario      TEXT NOT NULL,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_resena_usuario_producto UNIQUE (id_usuario, id_producto),
    CONSTRAINT chk_resena_calificacion CHECK (calificacion BETWEEN 1 AND 5),
    CONSTRAINT chk_resena_comentario CHECK (length(btrim(comentario)) > 0)
);
CREATE INDEX IF NOT EXISTS idx_resena_producto_fecha
    ON resena_producto (id_producto, creado_en DESC, id DESC);
"""


def create_table(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREATE_TABLE)


def drop_table(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TABLE IF EXISTS resena_producto")


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012 - declaracion de Migration de Django
        ("catalog", "0008_publicacion_programada"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [  # noqa: RUF012 - declaracion de Migration de Django
        migrations.RunPython(create_table, drop_table),
        migrations.CreateModel(
            name="ProductReview",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("rating", models.SmallIntegerField(db_column="calificacion")),
                ("comment", models.TextField(db_column="comentario")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                ("updated_at", models.DateTimeField(auto_now=True, db_column="actualizado_en")),
                ("user", models.ForeignKey(
                    db_column="id_usuario", on_delete=django.db.models.deletion.CASCADE,
                    related_name="product_reviews", to=settings.AUTH_USER_MODEL,
                )),
                ("product", models.ForeignKey(
                    db_column="id_producto", on_delete=django.db.models.deletion.CASCADE,
                    related_name="reviews", to="catalog.tourismproduct",
                )),
            ],
            options={
                "db_table": "resena_producto",
                "ordering": ("-created_at", "-id"),
                "managed": False,
                "constraints": [
                    models.UniqueConstraint(fields=("user", "product"), name="uq_resena_usuario_producto"),
                    models.CheckConstraint(
                        condition=models.Q(rating__gte=1, rating__lte=5),
                        name="chk_resena_calificacion",
                    ),
                ],
                "indexes": [
                    models.Index(fields=("product", "-created_at", "-id"), name="idx_resena_producto_fecha"),
                ],
            },
        ),
    ]
