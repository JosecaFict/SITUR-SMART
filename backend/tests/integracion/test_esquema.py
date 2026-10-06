import pytest
from django.db import connection

pytestmark = pytest.mark.django_db


def test_la_base_de_pruebas_tiene_el_esquema_completo():
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        assert cursor.fetchone()[0] == "situr_smart_pruebas"
        for table in ("orden_reserva", "reserva_detalle", "pago", "establecimiento_hospedaje"):
            cursor.execute("SELECT to_regclass(%s)", [table])
            assert cursor.fetchone()[0] == table
