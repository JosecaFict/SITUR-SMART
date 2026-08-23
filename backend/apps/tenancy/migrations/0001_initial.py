from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Tenant',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('city_id', models.BigIntegerField(blank=True, db_column='id_ciudad', null=True)),
                ('legal_name', models.CharField(db_column='razon_social', max_length=180)),
                ('trade_name', models.CharField(db_column='nombre_comercial', max_length=180)),
                ('subdomain', models.CharField(db_column='subdominio', max_length=80, unique=True)),
                ('tax_id', models.CharField(blank=True, db_column='nit', max_length=30, null=True, unique=True)),
                ('contact_email', models.EmailField(blank=True, db_column='email_contacto', max_length=254, null=True)),
                ('phone', models.CharField(blank=True, db_column='telefono', max_length=30, null=True)),
                ('status', models.CharField(choices=[('PENDIENTE', 'Pendiente'), ('ACTIVO', 'Activo'), ('INACTIVO', 'Inactivo'), ('SUSPENDIDO', 'Suspendido')], db_column='estado', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='creado_en')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='actualizado_en')),
            ],
            options={
                'db_table': 'tenant',
                'ordering': ('trade_name',),
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='UserTenant',
            fields=[
                ('pk', models.CompositePrimaryKey('user', 'tenant', blank=True, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('ACTIVO', 'Activo'), ('INACTIVO', 'Inactivo'), ('INVITADO', 'Invitado')], db_column='estado', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='creado_en')),
                ('tenant', models.ForeignKey(db_column='id_tenant', on_delete=django.db.models.deletion.DO_NOTHING, related_name='memberships', to='tenancy.tenant')),
                ('user', models.ForeignKey(db_column='id_usuario', on_delete=django.db.models.deletion.DO_NOTHING, related_name='tenant_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'usuario_tenant',
                'managed': False,
            },
        ),
    ]
