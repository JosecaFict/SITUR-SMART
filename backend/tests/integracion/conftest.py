"""Base desechable de PostgreSQL para las pruebas de integracion.

Se arma igual que una instalacion nueva: los scripts de database/migrations en
orden y despues ``migrate``, que sobre esas tablas solo registra estado y
aplica lo idempotente. Asi se prueba el mismo esquema que corre en Railway,
con sus triggers, CHECK y FK compuestas.

En la suite normal (SQLite) estos archivos ni se recolectan.
"""

from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import connections

from apps.bookings import events
from apps.notifications import push
from apps.payments import gateway

from .datos import WEBHOOK_SECRET

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


class StripeFalso:
    def __init__(self):
        self.sessions: dict[str, dict] = {}
        self.created: list[dict] = []
        self.fail = False

    def create_checkout_session(self, **kwargs):
        if self.fail:
            raise gateway.PaymentUnavailable()
        session_id = f"cs_test_{len(self.created) + 1}"
        self.created.append(kwargs)
        self.sessions[session_id] = {"status": "open", "payment_status": "unpaid"}
        return self._session(session_id)

    def retrieve_session(self, session_id):
        return self._session(session_id) if session_id in self.sessions else None

    def expire_session(self, session_id):
        if self.sessions.get(session_id, {}).get("status") == "open":
            self.sessions[session_id]["status"] = "expired"

    def pay(self, session_id):
        self.sessions[session_id] = {"status": "complete", "payment_status": "paid"}

    def _session(self, session_id):
        data = self.sessions[session_id]
        return gateway.CheckoutSession(
            id=session_id,
            url=f"https://checkout.stripe.test/{session_id}",
            status=data["status"],
            payment_status=data["payment_status"],
        )


@pytest.fixture
def stripe(monkeypatch, settings):
    fake = StripeFalso()
    settings.STRIPE_SECRET_KEY = "sk_test_pruebas"
    settings.STRIPE_WEBHOOK_SECRET = WEBHOOK_SECRET
    monkeypatch.setattr(gateway, "create_checkout_session", fake.create_checkout_session)
    monkeypatch.setattr(gateway, "retrieve_session", fake.retrieve_session)
    monkeypatch.setattr(gateway, "expire_session", fake.expire_session)
    return fake


@pytest.fixture
def firebase(monkeypatch):
    """Firebase falso: anota cada push. ``rechazos`` mapea token -> codigo de error de FCM."""
    falso = SimpleNamespace(enviados=[], rechazos={})

    def enviar(message):
        falso.enviados.append(message["message"])
        return falso.rechazos.get(message["message"]["token"])

    monkeypatch.setattr(push, "is_configured", lambda: True)
    monkeypatch.setattr(push, "send_one", enviar)
    monkeypatch.setattr(events, "send_email", lambda **kwargs: True)
    return falso
