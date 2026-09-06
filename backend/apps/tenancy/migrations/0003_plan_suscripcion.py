import django.db.models.deletion
from django.db import migrations, models


def seed_default_plans(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        INSERT INTO plan (id_moneda, codigo, nombre, precio_mensual, max_usuarios, max_productos, porcentaje_comision, activo)
        SELECT m.id, plan_data.codigo, plan_data.nombre, plan_data.precio_mensual,
               plan_data.max_usuarios, plan_data.max_productos, plan_data.porcentaje_comision, TRUE
          FROM moneda m
         CROSS JOIN (VALUES
            ('BASICO', 'Básico', 149.00, 3, 15, 8.00),
            ('PROFESIONAL', 'Profesional', 349.00, 10, 60, 5.00),
            ('EMPRESARIAL', 'Empresarial', 799.00, 999999, 999999, 3.00)
        ) AS plan_data(codigo, nombre, precio_mensual, max_usuarios, max_productos, porcentaje_comision)
         WHERE m.codigo_iso = 'BOB'
        ON CONFLICT (codigo) DO NOTHING
        """
    )


def remove_default_plans(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        DELETE FROM plan
         WHERE codigo IN ('BASICO', 'PROFESIONAL', 'EMPRESARIAL')
           AND NOT EXISTS (SELECT 1 FROM suscripcion WHERE id_plan = plan.id)
        """
    )


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0002_catalog_model_state"),
        ("catalog", "0001_catalog_api"),
    ]

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("code", models.CharField(db_column="codigo", max_length=50, unique=True)),
                ("name", models.CharField(db_column="nombre", max_length=100, unique=True)),
                (
                    "monthly_price",
                    models.DecimalField(db_column="precio_mensual", decimal_places=2, max_digits=12),
                ),
                ("max_users", models.PositiveIntegerField(db_column="max_usuarios")),
                ("max_products", models.PositiveIntegerField(db_column="max_productos")),
                (
                    "commission_percentage",
                    models.DecimalField(
                        db_column="porcentaje_comision", decimal_places=2, default=0, max_digits=5
                    ),
                ),
                ("active", models.BooleanField(db_column="activo", default=True)),
                (
                    "currency",
                    models.ForeignKey(
                        db_column="id_moneda",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="plans",
                        to="catalog.currency",
                    ),
                ),
            ],
            options={"db_table": "plan", "ordering": ("monthly_price",), "managed": False},
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("start_date", models.DateField(db_column="fecha_inicio")),
                ("end_date", models.DateField(blank=True, db_column="fecha_fin", null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ACTIVA", "Activa"),
                            ("VENCIDA", "Vencida"),
                            ("CANCELADA", "Cancelada"),
                            ("SUSPENDIDA", "Suspendida"),
                        ],
                        db_column="estado",
                        default="ACTIVA",
                        max_length=20,
                    ),
                ),
                (
                    "auto_renew",
                    models.BooleanField(db_column="renovacion_automatica", default=False),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
                (
                    "plan",
                    models.ForeignKey(
                        db_column="id_plan",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="subscriptions",
                        to="tenancy.plan",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="id_tenant",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="subscriptions",
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "suscripcion", "ordering": ("-created_at",), "managed": False},
        ),
        migrations.RunPython(seed_default_plans, remove_default_plans),
    ]
