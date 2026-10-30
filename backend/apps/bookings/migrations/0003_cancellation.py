from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0002_llegada_y_reportes"),
        ("catalog", "0009_cancellationpolicy_penaltyrule"),
    ]

    operations = [
        migrations.CreateModel(
            name="Cancellation",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("reason", models.TextField(db_column="motivo", null=True)),
                ("advance_days", models.PositiveIntegerField(db_column="dias_anticipacion")),
                (
                    "applied_percentage",
                    models.DecimalField(
                        db_column="porcentaje_aplicado", decimal_places=2, default=0, max_digits=5
                    ),
                ),
                (
                    "penalty_amount",
                    models.DecimalField(
                        db_column="monto_penalizacion", decimal_places=2, default=0, max_digits=12
                    ),
                ),
                (
                    "refund_amount",
                    models.DecimalField(
                        db_column="monto_reembolso", decimal_places=2, default=0, max_digits=12
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
            ],
            options={
                "db_table": "cancelacion",
                "managed": False,
            },
        ),
    ]
