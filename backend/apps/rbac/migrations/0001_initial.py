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
            name='Permission',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('code', models.CharField(db_column='codigo', max_length=100, unique=True)),
                ('module', models.CharField(db_column='modulo', max_length=80)),
                ('name', models.CharField(db_column='nombre', max_length=150)),
            ],
            options={
                'db_table': 'permiso',
                'ordering': ('module', 'code'),
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('code', models.CharField(db_column='codigo', max_length=60)),
                ('name', models.CharField(db_column='nombre', max_length=120)),
                ('scope', models.CharField(choices=[('GLOBAL', 'Global'), ('TENANT', 'Tenant')], db_column='ambito', max_length=20)),
                ('is_system', models.BooleanField(db_column='es_sistema')),
                ('tenant', models.ForeignKey(blank=True, db_column='id_tenant', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='roles', to='tenancy.tenant')),
            ],
            options={
                'db_table': 'rol',
                'ordering': ('scope', 'code'),
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='RolePermission',
            fields=[
                ('pk', models.CompositePrimaryKey('role', 'permission', blank=True, editable=False, primary_key=True, serialize=False)),
                ('permission', models.ForeignKey(db_column='id_permiso', on_delete=django.db.models.deletion.DO_NOTHING, related_name='permission_roles', to='rbac.permission')),
                ('role', models.ForeignKey(db_column='id_rol', on_delete=django.db.models.deletion.DO_NOTHING, related_name='role_permissions', to='rbac.role')),
            ],
            options={
                'db_table': 'rol_permiso',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='UserRole',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('assigned_at', models.DateTimeField(auto_now_add=True, db_column='asignado_en')),
                ('role', models.ForeignKey(db_column='id_rol', on_delete=django.db.models.deletion.DO_NOTHING, related_name='assignments', to='rbac.role')),
                ('tenant', models.ForeignKey(blank=True, db_column='id_tenant', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='role_assignments', to='tenancy.tenant')),
                ('user', models.ForeignKey(db_column='id_usuario', on_delete=django.db.models.deletion.DO_NOTHING, related_name='user_roles', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'usuario_rol',
                'managed': False,
            },
        ),
    ]
