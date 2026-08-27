from django.conf import settings
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenancy', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('action', models.CharField(db_column='accion', max_length=50)),
                ('entity', models.CharField(db_column='entidad', max_length=100)),
                ('entity_id', models.CharField(blank=True, max_length=100, null=True)),
                ('previous_data', models.JSONField(blank=True, db_column='datos_anteriores', null=True)),
                ('new_data', models.JSONField(blank=True, db_column='datos_nuevos', null=True)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('request_id', models.CharField(blank=True, max_length=100, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='creado_en')),
                ('tenant', models.ForeignKey(blank=True, db_column='id_tenant', null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='tenancy.tenant')),
                ('user', models.ForeignKey(blank=True, db_column='id_usuario', null=True, on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'bitacora',
                'ordering': ('-created_at',),
                'managed': False,
            },
        ),
    ]
