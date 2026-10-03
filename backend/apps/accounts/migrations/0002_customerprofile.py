import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerProfile",
            fields=[
                (
                    "user",
                    models.OneToOneField(
                        db_column="id_usuario",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        primary_key=True,
                        related_name="customer_profile",
                        serialize=False,
                        to="accounts.user",
                    ),
                ),
                (
                    "document_type",
                    models.CharField(
                        blank=True,
                        db_column="tipo_documento",
                        max_length=30,
                        null=True,
                    ),
                ),
                (
                    "document_number",
                    models.CharField(
                        blank=True,
                        db_column="numero_documento",
                        max_length=50,
                        null=True,
                    ),
                ),
                (
                    "birth_date",
                    models.DateField(
                        blank=True,
                        db_column="fecha_nacimiento",
                        null=True,
                    ),
                ),
                (
                    "preferences",
                    models.JSONField(db_column="preferencias", default=dict),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_column="creado_en"),
                ),
            ],
            options={
                "db_table": "perfil_cliente",
                "managed": False,
            },
        ),
    ]
