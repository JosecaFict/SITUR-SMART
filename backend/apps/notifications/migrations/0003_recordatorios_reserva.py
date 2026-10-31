import django.db.models.deletion
from django.db import migrations, models


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS recordatorio_reserva_enviado (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_reserva  BIGINT NOT NULL REFERENCES reserva(id) ON DELETE CASCADE,
    tipo        VARCHAR(40) NOT NULL,
    enviado_en  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_recordatorio_reserva_tipo UNIQUE (id_reserva, tipo)
);
CREATE INDEX IF NOT EXISTS idx_recordatorio_reserva_enviado
    ON recordatorio_reserva_enviado (enviado_en DESC);
"""


def create_table(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(CREATE_TABLE)


def drop_table(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TABLE IF EXISTS recordatorio_reserva_enviado;")


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0005_booking_billing_data"),
        ("notifications", "0002_dispositivo_push"),
    ]

    operations = [
        migrations.RunPython(create_table, drop_table),
        migrations.CreateModel(
            name="BookingReminderDelivery",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("kind", models.CharField(db_column="tipo", max_length=40)),
                ("sent_at", models.DateTimeField(auto_now_add=True, db_column="enviado_en")),
                (
                    "booking",
                    models.ForeignKey(
                        db_column="id_reserva",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reminder_deliveries",
                        to="bookings.booking",
                    ),
                ),
            ],
            options={
                "db_table": "recordatorio_reserva_enviado",
                "managed": False,
                "constraints": [
                    models.UniqueConstraint(
                        fields=("booking", "kind"),
                        name="uq_recordatorio_reserva_tipo",
                    )
                ],
            },
        ),
    ]
