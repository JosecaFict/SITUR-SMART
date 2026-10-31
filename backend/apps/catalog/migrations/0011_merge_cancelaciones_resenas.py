"""Une las dos ramas 0009 ya desplegadas sin repetir ni renombrar migraciones."""

from typing import ClassVar

from django.db import migrations


class Migration(migrations.Migration):
    dependencies: ClassVar = [
        ("catalog", "0010_default_cancellation_policy"),
        ("catalog", "0009_resenas_producto"),
    ]

    operations: ClassVar = []
