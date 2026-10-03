"""Pruebas de la migracion 0006, que reconcilia los hoteles heredados.

La migracion es un UPDATE en SQL crudo, asi que no se puede ejecutar contra
SQLite: las tablas no existen (``managed = False``) y el script esta guardado
para PostgreSQL. Lo que se verifica aqui es el contrato del SQL -- que apunte a
las filas correctas y solo a esas -- analizando la sentencia, mas el guardado de
no ejecutarse en otro motor.

La ejecucion real queda cubierta por el deploy y se comprueba despues contra la
base, como se hizo con 0004 y 0005.
"""

import re
from importlib import import_module

from django.test import SimpleTestCase

# El nombre del modulo empieza con digito, asi que no admite un import normal.
reconciliation = import_module(
    "apps.catalog.migrations.0006_reconciliar_hoteles_publicados"
)


def _normalize(sql: str) -> str:
    """Colapsa los espacios para poder buscar frases sin pelear con el formato."""
    return re.sub(r"\s+", " ", sql).strip().upper()


class ReconciliationSqlTests(SimpleTestCase):
    SQL = _normalize(reconciliation.DEMOTE_INCOMPLETE_HOTELS)

    def test_only_demotes_to_draft(self):
        """Lo unico que cambia es el estado, y solo hacia BORRADOR."""
        self.assertIn("SET ESTADO = 'BORRADOR'", self.SQL)
        self.assertEqual(self.SQL.count("UPDATE"), 1)
        for forbidden in ("DELETE", "DROP", "TRUNCATE", "ALTER", "INSERT"):
            self.assertNotIn(forbidden, self.SQL)

    def test_only_touches_currently_published_rows(self):
        self.assertIn("WHERE P.ESTADO = 'PUBLICADO'", self.SQL)

    def test_only_touches_hotels(self):
        self.assertIn("TP.CODIGO = 'HOTEL'", self.SQL)

    def test_only_touches_products_that_have_a_lodging_record(self):
        self.assertIn("FROM ESTABLECIMIENTO_HOSPEDAJE E WHERE E.ID_PRODUCTO = P.ID", self.SQL)

    def test_never_touches_a_hotel_with_a_publishable_room(self):
        """El NOT EXISTS es la garantia de que un hotel valido no se toca."""
        self.assertIn("NOT EXISTS", self.SQL)
        self.assertIn("HP.ESTADO = 'PUBLICADO'", self.SQL)
        self.assertIn("HP.PRECIO_BASE > 0", self.SQL)

    def test_a_published_room_without_price_does_not_save_the_hotel(self):
        """Las dos condiciones van juntas con AND, no con OR."""
        habitacion = self.SQL.split("NOT EXISTS")[1]
        self.assertIn("HP.ESTADO = 'PUBLICADO' AND HP.PRECIO_BASE > 0", habitacion)

    def test_is_idempotent_by_construction(self):
        """Tras correrla, las filas afectadas ya no cumplen el WHERE."""
        self.assertIn("P.ESTADO = 'PUBLICADO'", self.SQL)
        self.assertIn("SET ESTADO = 'BORRADOR'", self.SQL)


class ReconciliationGuardTests(SimpleTestCase):
    class _FakeSchemaEditor:
        def __init__(self, vendor):
            self.connection = type("conn", (), {"vendor": vendor})()
            self.executed = False

        def cursor(self):  # pragma: no cover - no deberia alcanzarse en sqlite
            self.executed = True
            raise AssertionError("no debe abrir cursor en un motor que no sea postgresql")

    def test_does_nothing_outside_postgresql(self):
        editor = self._FakeSchemaEditor("sqlite")

        reconciliation.demote_incomplete_hotels(None, editor)

        self.assertFalse(editor.executed)

    def test_migration_has_no_reverse_that_republishes(self):
        """Volver atras no debe reintroducir el estado invalido."""
        from django.db import migrations

        operation = reconciliation.Migration.operations[0]
        self.assertIs(operation.reverse_code, migrations.RunPython.noop)
        self.assertIs(operation.code, reconciliation.demote_incomplete_hotels)

    def test_depends_on_the_backfill(self):
        self.assertIn(
            ("catalog", "0005_backfill_establecimientos"),
            reconciliation.Migration.dependencies,
        )
