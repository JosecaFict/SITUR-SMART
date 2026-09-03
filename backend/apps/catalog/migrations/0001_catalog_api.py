import django.db.models.deletion
from django.db import migrations, models


def add_catalog_fields(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "ALTER TABLE producto_turistico ADD COLUMN IF NOT EXISTS imagen_url VARCHAR(500)"
    )
    schema_editor.execute(
        """
        INSERT INTO tipo_producto (codigo, nombre)
        VALUES ('RESTAURANTE', 'Restaurante'), ('PAQUETE', 'Paquete turístico')
        ON CONFLICT (codigo) DO NOTHING
        """
    )


def remove_catalog_fields(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        DELETE FROM tipo_producto
        WHERE codigo IN ('RESTAURANTE', 'PAQUETE')
          AND NOT EXISTS (
            SELECT 1 FROM producto_turistico
            WHERE id_tipo_producto = tipo_producto.id
          )
        """
    )
    schema_editor.execute("ALTER TABLE producto_turistico DROP COLUMN IF EXISTS imagen_url")


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0002_catalog_model_state")]

    operations = [
        migrations.RunPython(add_catalog_fields, remove_catalog_fields),
        migrations.CreateModel(
            name="Currency", fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("iso_code", models.CharField(db_column="codigo_iso", max_length=3, unique=True)),
                ("name", models.CharField(db_column="nombre", max_length=80)),
                ("symbol", models.CharField(db_column="simbolo", max_length=10)),
                ("decimals", models.SmallIntegerField(db_column="decimales", default=2)),
            ], options={"db_table": "moneda", "ordering": ("iso_code",), "managed": False},
        ),
        migrations.CreateModel(
            name="ProductType", fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("code", models.CharField(db_column="codigo", max_length=50, unique=True)),
                ("name", models.CharField(db_column="nombre", max_length=120, unique=True)),
            ], options={"db_table": "tipo_producto", "ordering": ("name",), "managed": False},
        ),
        migrations.CreateModel(
            name="TourismProduct", fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("cancellation_policy_id", models.BigIntegerField(blank=True, db_column="id_politica_cancelacion", null=True)),
                ("code", models.CharField(db_column="codigo", max_length=60)),
                ("name", models.CharField(db_column="nombre", max_length=180)),
                ("description", models.TextField(blank=True, db_column="descripcion", null=True)),
                ("base_price", models.DecimalField(db_column="precio_base", decimal_places=2, max_digits=12)),
                ("max_capacity", models.PositiveIntegerField(db_column="capacidad_maxima")),
                ("status", models.CharField(choices=[("BORRADOR", "Borrador"), ("PUBLICADO", "Publicado"), ("INACTIVO", "Inactivo")], db_column="estado", max_length=20)),
                ("image_url", models.CharField(blank=True, db_column="imagen_url", max_length=500, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                ("updated_at", models.DateTimeField(auto_now=True, db_column="actualizado_en")),
                ("city", models.ForeignKey(db_column="id_ciudad", on_delete=django.db.models.deletion.DO_NOTHING, related_name="products", to="tenancy.city")),
                ("currency", models.ForeignKey(db_column="id_moneda", on_delete=django.db.models.deletion.DO_NOTHING, related_name="products", to="catalog.currency")),
                ("product_type", models.ForeignKey(db_column="id_tipo_producto", on_delete=django.db.models.deletion.DO_NOTHING, related_name="products", to="catalog.producttype")),
                ("tenant", models.ForeignKey(db_column="id_tenant", on_delete=django.db.models.deletion.DO_NOTHING, related_name="products", to="tenancy.tenant")),
            ], options={"db_table": "producto_turistico", "ordering": ("-updated_at",), "managed": False, "unique_together": {("tenant", "code")}},
        ),
    ]
