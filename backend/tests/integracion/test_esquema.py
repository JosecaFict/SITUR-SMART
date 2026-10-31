import pytest
from django.conf import settings
from django.db import connection

pytestmark = pytest.mark.django_db


def test_la_base_de_pruebas_tiene_el_esquema_completo():
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        expected = settings.DATABASES["default"]["TEST"]["NAME"]
        assert expected.startswith("situr_smart_pruebas")
        assert cursor.fetchone()[0] == expected
        for table in ("orden_reserva", "reserva_detalle", "pago", "establecimiento_hospedaje"):
            cursor.execute("SELECT to_regclass(%s)", [table])
            assert cursor.fetchone()[0] == table
