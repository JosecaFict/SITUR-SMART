import apps.accounts.managers
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=255, unique=True)),
                ('password', models.TextField(db_column='password_hash')),
                ('first_names', models.CharField(db_column='nombres', max_length=120)),
                ('last_names', models.CharField(db_column='apellidos', max_length=120)),
                ('phone', models.CharField(blank=True, db_column='telefono', max_length=30, null=True)),
                ('status', models.CharField(choices=[('PENDIENTE', 'Pendiente'), ('ACTIVO', 'Activo'), ('INACTIVO', 'Inactivo'), ('BLOQUEADO', 'Bloqueado')], db_column='estado', max_length=20)),
                ('email_verified_at', models.DateTimeField(blank=True, db_column='email_verificado_en', null=True)),
                ('last_login', models.DateTimeField(blank=True, db_column='ultimo_acceso_en', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='creado_en')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='actualizado_en')),
            ],
            options={
                'db_table': 'usuario',
                'ordering': ('email',),
                'managed': False,
            },
            managers=[
                ('objects', apps.accounts.managers.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='PasswordResetToken',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('token_hash', models.TextField(unique=True)),
                ('expires_at', models.DateTimeField(db_column='expira_en')),
                ('used_at', models.DateTimeField(blank=True, db_column='usado_en', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='creado_en')),
                ('user', models.ForeignKey(db_column='id_usuario', on_delete=django.db.models.deletion.DO_NOTHING, to='accounts.user')),
            ],
            options={
                'db_table': 'token_recuperacion',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='UserSession',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('refresh_token_hash', models.TextField(unique=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(db_column='expira_en')),
                ('revoked_at', models.DateTimeField(blank=True, db_column='revocada_en', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='creada_en')),
                ('user', models.ForeignKey(db_column='id_usuario', on_delete=django.db.models.deletion.DO_NOTHING, related_name='sessions', to='accounts.user')),
            ],
            options={
                'db_table': 'sesion_usuario',
                'managed': False,
            },
        ),
    ]
