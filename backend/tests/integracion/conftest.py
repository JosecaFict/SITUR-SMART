"""Base desechable de PostgreSQL para las pruebas de integracion.

Se arma igual que una instalacion nueva: los scripts de database/migrations en
orden y despues ``migrate``, que sobre esas tablas solo registra estado y
aplica lo idempotente. Asi se prueba el mismo esquema que corre en Railway,
con sus triggers, CHECK y FK compuestas.

En la suite normal (SQLite) estos archivos ni se recolectan.
"""

from pathlib import Path

import psycopg
import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import connections

if settings.DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    collect_ignore_glob = ["test_*.py"]

SQL_DIR = Path(settings.BASE_DIR) / "database" / "migrations"


def _admin_connection(db: dict) -> psycopg.Connection:
    return psycopg.connect(
        dbname="postgres",
        user=db["USER"],
        password=db["PASSWORD"],
        host=db["HOST"],
        port=db["PORT"],
        autocommit=True,
    )


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    db = settings.DATABASES["default"]
    test_name = db["TEST"]["NAME"]
    with django_db_blocker.unblock():
        connections.close_all()
        with _admin_connection(db) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{test_name}" WITH (FORCE)')
            admin.execute(f'CREATE DATABASE "{test_name}"')

        for alias in connections:
            connections[alias].settings_dict["NAME"] = test_name
        db["NAME"] = test_name

        with psycopg.connect(
            dbname=test_name,
            user=db["USER"],
            password=db["PASSWORD"],
            host=db["HOST"],
            port=db["PORT"],
            autocommit=True,
        ) as conn:
            for script in sorted(SQL_DIR.glob("*.sql")):
                conn.execute(script.read_text(encoding="utf-8"))

        call_command("migrate", verbosity=0, interactive=False)
        # Datos de Bolivia: empresas, hoteles con habitaciones, tours y turistas.
        call_command(
            "createsituradmin",
            email="superadmin@situr.com.bo",
            nombres="Super",
            apellidos="Admin",
            password="Admin123*",
            verbosity=0,
        )
        call_command("seed_bolivia", verbosity=0)
    yield
