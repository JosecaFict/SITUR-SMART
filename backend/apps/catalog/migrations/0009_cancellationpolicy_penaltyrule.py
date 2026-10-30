from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0008_publicacion_programada"),
    ]

    operations = [
        migrations.CreateModel(
            name="CancellationPolicy",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(db_column="nombre", max_length=120)),
                ("refundable", models.BooleanField(db_column="reembolsable", default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_column="creado_en")),
            ],
            options={
                "db_table": "politica_cancelacion",
                "managed": False,
                "ordering": ("name", "id"),
            },
        ),
        migrations.CreateModel(
            name="PenaltyRule",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("minimum_days", models.PositiveIntegerField(db_column="dias_antes_min")),
                ("maximum_days", models.PositiveIntegerField(db_column="dias_antes_max", null=True)),
                (
                    "penalty_percentage",
                    models.DecimalField(
                        db_column="porcentaje_penalizacion", decimal_places=2, max_digits=5
                    ),
                ),
            ],
            options={
                "db_table": "regla_penalizacion",
                "managed": False,
                "ordering": ("minimum_days", "maximum_days", "id"),
            },
        ),
    ]
