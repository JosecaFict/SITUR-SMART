from django.db import migrations, models


def enable_future_deliveries(apps, schema_editor):
    # No reenviar publicaciones anteriores: solo borradores y envíos futuros.
    communication = apps.get_model("notifications", "Communication")
    communication.objects.using(schema_editor.connection.alias).filter(
        state__in=("BORRADOR", "PROGRAMADA"), email_enabled=False,
    ).update(email_enabled=True)


class Migration(migrations.Migration):
    dependencies = [("notifications", "0009_communication_email_enabled_communicationemail")]

    operations = [
        migrations.AlterField(
            model_name="communication", name="email_enabled", field=models.BooleanField(default=True),
        ),
        migrations.RunPython(enable_future_deliveries, migrations.RunPython.noop),
    ]
