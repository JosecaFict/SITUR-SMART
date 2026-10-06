
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("bookings", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('amount', models.DecimalField(db_column='monto', decimal_places=2, max_digits=12)),
                ('method', models.CharField(db_column='metodo', max_length=30)),
                ('status', models.CharField(db_column='estado', default='PENDIENTE', max_length=20)),
                ('provider', models.CharField(db_column='proveedor', default='SIMULADO', max_length=60)),
                ('reference', models.CharField(db_column='referencia', max_length=150, null=True)),
                ('idempotency_key', models.CharField(db_column='idempotency_key', max_length=100, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='creado_en')),
                ('processed_at', models.DateTimeField(db_column='procesado_en', null=True)),
            ],
            options={
                'db_table': 'pago',
                'managed': False,
            },
        ),
    ]
