"""Garantías PostgreSQL sin extensiones ni cambios en tablas históricas.

Los rangos nativos soportan GiST: no requiere instalar btree_gist.
SQLite se utiliza solo para pruebas unitarias sin el esquema SQL histórico.
"""

from django.db import migrations


def add_constraints(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        ALTER TABLE promocion_comercial
        ADD CONSTRAINT promo_producto_empresa_fk
        FOREIGN KEY (product_id, tenant_id) REFERENCES producto_turistico (id, id_tenant);
        ALTER TABLE promocion_comercial
        ADD CONSTRAINT promo_vigencias_no_superpuestas
        EXCLUDE USING gist (
            int8range(product_id, product_id, '[]') WITH &&,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        ) WHERE (mode = 'EXISTENTE' AND administrative_status = 'HABILITADA');
    """)


def remove_constraints(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        ALTER TABLE promocion_comercial DROP CONSTRAINT promo_vigencias_no_superpuestas;
        ALTER TABLE promocion_comercial DROP CONSTRAINT promo_producto_empresa_fk;
    """)


class Migration(migrations.Migration):
    dependencies = [("promotions", "0001_initial")]
    operations = [migrations.RunPython(add_constraints, remove_constraints)]
