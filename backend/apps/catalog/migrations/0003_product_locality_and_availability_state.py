import django.db.models.deletion
from django.db import migrations, models


def add_product_locality(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "ALTER TABLE producto_turistico ADD COLUMN IF NOT EXISTS localidad VARCHAR(180)"
    )


def remove_product_locality(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("ALTER TABLE producto_turistico DROP COLUMN IF EXISTS localidad")


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_seed_bolivia_cities")]

    operations = [
        migrations.RunPython(add_product_locality, remove_product_locality),
        migrations.AddField(
            model_name="tourismproduct",
            name="locality",
            field=models.CharField(
                blank=True, db_column="localidad", max_length=180, null=True
            ),
        ),
        migrations.CreateModel(
            name="Availability",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("start", models.DateTimeField(db_column="inicio")),
                ("end", models.DateTimeField(db_column="fin")),
                ("total_capacity", models.PositiveIntegerField(db_column="cupo_total")),
                ("closed", models.BooleanField(db_column="cerrado", default=False)),
                (
                    "product",
                    models.ForeignKey(
                        db_column="id_producto",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="availabilities",
                        to="catalog.tourismproduct",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="id_tenant",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "disponibilidad", "managed": False},
        ),
    ]
