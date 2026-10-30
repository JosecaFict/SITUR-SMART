from django.db import migrations, models
from typing_extensions import ClassVar

SQL = """
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS razon_social_facturacion VARCHAR(180);
ALTER TABLE reserva ADD COLUMN IF NOT EXISTS nit_facturacion VARCHAR(40);
"""

REVERSE = """
ALTER TABLE reserva DROP COLUMN IF EXISTS nit_facturacion;
ALTER TABLE reserva DROP COLUMN IF EXISTS razon_social_facturacion;
"""


class Migration(migrations.Migration):
    dependencies: ClassVar = [("bookings", "0004_booking_commercial_terms")]

    operations: ClassVar = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunSQL(SQL, REVERSE)],
            state_operations=[
                migrations.AddField(
                    model_name="booking", name="billing_name",
                    field=models.CharField(db_column="razon_social_facturacion", max_length=180, null=True),
                ),
                migrations.AddField(
                    model_name="booking", name="billing_tax_id",
                    field=models.CharField(db_column="nit_facturacion", max_length=40, null=True),
                ),
            ],
        )
    ]
