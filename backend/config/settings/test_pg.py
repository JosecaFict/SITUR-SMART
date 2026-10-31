"""Pruebas de integracion contra PostgreSQL real.

La suite normal corre en SQLite y no tiene las tablas (los modelos son
``managed = False``). Reservas, cupos y pagos dependen de bloqueos de fila,
triggers y columnas generadas que solo existen en PostgreSQL, asi que se
prueban aqui:

    pytest --ds=config.settings.test_pg tests/integracion

Usa el servidor de ``.env`` pero nunca su base: ``tests/integracion/conftest.py``
crea una base nueva con los scripts de database/migrations y las migraciones
de Django. ``SITUR_TEST_DB_NAME`` permite elegir otro nombre sin borrar una
base de pruebas preexistente.
"""

import os
from uuid import uuid4

from .base import *  # noqa: F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DATABASES["default"]["TEST"] = {  # noqa: F405
    "NAME": os.getenv("SITUR_TEST_DB_NAME") or f"situr_smart_pruebas_{uuid4().hex[:8]}"
}
CORREOS_EN_SEGUNDO_PLANO = False
PUSH_EN_SEGUNDO_PLANO = False
