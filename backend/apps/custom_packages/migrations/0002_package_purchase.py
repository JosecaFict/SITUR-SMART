import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0005_booking_billing_data"),
        ("catalog", "0011_merge_cancelaciones_resenas"),
        ("custom_packages", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PackagePurchase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("CREADA", "Pendiente de pago"), ("CONFIRMADA", "Confirmada"), ("CANCELADA", "Cancelada"), ("EXPIRADA", "Expirada"), ("REEMBOLSADA", "Reembolsada")], default="CREADA", max_length=20)),
                ("original_amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("discount_amount", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("final_amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("provider", models.CharField(default="STRIPE", max_length=60)),
                ("provider_reference", models.CharField(blank=True, max_length=150, null=True)),
                ("idempotency_key", models.CharField(max_length=100, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("currency", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="catalog.currency")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="package_purchase", to="bookings.order")),
                ("package", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="purchase", to="custom_packages.custompackage")),
            ],
            options={"db_table": "compra_paquete_personalizado"},
        ),
        migrations.AddConstraint(
            model_name="packagepurchase",
            constraint=models.UniqueConstraint(condition=models.Q(("provider_reference__isnull", False)), fields=("provider", "provider_reference"), name="uq_compra_paquete_proveedor_referencia"),
        ),
        migrations.CreateModel(
            name="PackagePurchaseAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("original_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("discount_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("final_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("booking", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="package_allocation", to="bookings.booking")),
                ("purchase", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="allocations", to="custom_packages.packagepurchase")),
            ],
            options={"db_table": "compra_paquete_asignacion"},
        ),
        migrations.AddConstraint(model_name="packagepurchaseallocation", constraint=models.CheckConstraint(condition=models.Q(("original_amount__gte", 0)), name="chk_asignacion_importe_original")),
        migrations.AddConstraint(model_name="packagepurchaseallocation", constraint=models.CheckConstraint(condition=models.Q(("discount_amount__gte", 0)), name="chk_asignacion_descuento")),
        migrations.AddConstraint(model_name="packagepurchaseallocation", constraint=models.CheckConstraint(condition=models.Q(("final_amount__gt", 0)), name="chk_asignacion_importe_final")),
    ]
