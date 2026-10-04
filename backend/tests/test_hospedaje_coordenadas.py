"""Pruebas de la ubicacion exacta del establecimiento de hospedaje.

Tres capas, porque la regla del par vive en tres sitios a proposito: el
serializer la convierte en un 400 con mensaje, la capa de servicio la reaplica
para quien no pasa por HTTP, y PostgreSQL la impone con
``chk_establecimiento_coordenadas``. El CHECK no se puede ejercitar aqui --los
modelos son ``managed = False`` y la suite corre sobre SQLite-- asi que de el
solo se comprueba que el DDL de la migracion lo declare.
"""

from decimal import Decimal
from importlib import import_module
from typing import ClassVar
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.catalog.models import COORDINATE_PAIR_MESSAGE, LodgingEstablishment
from apps.catalog.serializers import (
    LodgingSerializer,
    LodgingWriteSerializer,
    RoomSerializer,
)
from apps.catalog.services import _LODGING_FIELDS, _normalize_coordinates
from apps.catalog.views import CompanyLodgingDetailView, PublicLodgingDetailView

from .test_hospedaje_vistas import (
    LODGING_ID,
    TENANT_ID,
    _ViewCase,
    fake_lodging,
    fake_room,
)

# El nombre del modulo empieza con un digito, asi que no se puede importar con
# `from ... import`.
migracion = import_module("apps.catalog.migrations.0007_hospedaje_coordenadas")

UYUNI = {"latitud": "-20.460350", "longitud": "-66.825320"}


def write(**data):
    """Valida un PATCH parcial, que es donde el par importa de verdad."""
    return LodgingWriteSerializer(data=data, partial=True)


class CoordinatePairSerializerTests(SimpleTestCase):
    """Ambas juntas, ambas en null, o ninguna. Nunca una sola."""

    def test_pair_is_accepted(self):
        serializer = write(**UYUNI)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["latitud"], Decimal("-20.460350"))
        self.assertEqual(serializer.validated_data["longitud"], Decimal("-66.825320"))

    def test_only_latitude_is_rejected(self):
        serializer = write(latitud="-20.460350")

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["longitud"], [COORDINATE_PAIR_MESSAGE])

    def test_only_longitude_is_rejected(self):
        serializer = write(longitud="-66.825320")

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["latitud"], [COORDINATE_PAIR_MESSAGE])

    def test_both_null_clears_the_location(self):
        serializer = write(latitud=None, longitud=None)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data["latitud"])
        self.assertIsNone(serializer.validated_data["longitud"])

    def test_half_a_pair_with_null_is_rejected(self):
        """Las dos claves presentes no bastan si solo una trae valor."""
        serializer = write(latitud="-20.460350", longitud=None)

        self.assertFalse(serializer.is_valid())
        self.assertEqual(serializer.errors["latitud"], [COORDINATE_PAIR_MESSAGE])

    def test_neither_coordinate_is_valid(self):
        """Un PATCH que no las menciona no tiene nada que validar."""
        serializer = write(nombre="Hotel Kachi Wasi")

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("latitud", serializer.validated_data)
        self.assertNotIn("longitud", serializer.validated_data)


class CoordinateRoundingTests(SimpleTestCase):
    """El GPS del navegador manda trece decimales y no puede ser un 400."""

    def test_gps_precision_is_rounded_not_rejected(self):
        serializer = write(latitud="-16.4956789123456", longitud="-68.1234564999")

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["latitud"], Decimal("-16.495679"))
        self.assertEqual(serializer.validated_data["longitud"], Decimal("-68.123456"))

    def test_rounding_is_half_away_from_zero(self):
        """ROUND_HALF_UP: el signo no cambia a donde cae el medio."""
        positiva = write(latitud="16.1234565", longitud="1.0")
        negativa = write(latitud="-16.1234565", longitud="-1.0")

        self.assertTrue(positiva.is_valid(), positiva.errors)
        self.assertTrue(negativa.is_valid(), negativa.errors)
        self.assertEqual(positiva.validated_data["latitud"], Decimal("16.123457"))
        self.assertEqual(negativa.validated_data["latitud"], Decimal("-16.123457"))

    def test_rounding_rescues_a_value_just_over_the_limit(self):
        """90.0000004 redondea a 90 exacto, que si entra en el rango."""
        serializer = write(latitud="90.0000004", longitud="180.0000004")

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["latitud"], Decimal("90.000000"))
        self.assertEqual(serializer.validated_data["longitud"], Decimal("180.000000"))

    def test_rounding_can_also_push_a_value_out_of_range(self):
        """Y 90.0000005 redondea a 90.000001, que ya no entra.

        Es la contraparte honesta de la prueba anterior: el redondeo se aplica
        antes del rango, asi que puede salvar un valor o condenarlo. Lo que
        importa es que la columna NUMERIC(9,6) nunca reciba algo que su CHECK
        rechace.
        """
        serializer = write(latitud="90.0000005", longitud="0.0")

        self.assertFalse(serializer.is_valid())
        self.assertIn("latitud", serializer.errors)


class CoordinateRangeTests(SimpleTestCase):
    """Latitud en [-90, 90], longitud en [-180, 180]."""

    def test_limits_are_inclusive(self):
        for latitud, longitud in (("90", "180"), ("-90", "-180"), ("0", "0")):
            with self.subTest(latitud=latitud, longitud=longitud):
                serializer = write(latitud=latitud, longitud=longitud)

                self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_latitude_out_of_range_is_rejected(self):
        for latitud in ("90.1", "-90.1", "91", "-1000"):
            with self.subTest(latitud=latitud):
                serializer = write(latitud=latitud, longitud="0")

                self.assertFalse(serializer.is_valid())
                self.assertIn("latitud", serializer.errors)

    def test_longitude_out_of_range_is_rejected(self):
        for longitud in ("180.1", "-180.1", "181", "-1000"):
            with self.subTest(longitud=longitud):
                serializer = write(latitud="0", longitud=longitud)

                self.assertFalse(serializer.is_valid())
                self.assertIn("longitud", serializer.errors)

    def test_an_absurd_value_fails_by_range_not_by_digits(self):
        """El mensaje tiene que describir el problema real.

        Si ``max_digits`` fuera 9 como la columna, 1234.5 se quejaria de tener
        demasiados digitos, que no es lo que le pasa.
        """
        serializer = write(latitud="1234.5", longitud="0")

        self.assertFalse(serializer.is_valid())
        self.assertNotIn("digits", str(serializer.errors["latitud"]).lower())
        self.assertNotIn("dígitos", str(serializer.errors["latitud"]).lower())

    def test_text_is_not_a_coordinate(self):
        serializer = write(latitud="aqui nomas", longitud="0")

        self.assertFalse(serializer.is_valid())
        self.assertIn("latitud", serializer.errors)


class CoordinateServiceGuardTests(SimpleTestCase):
    """La misma regla para quien no pasa por un serializer.

    Trabaja sobre los nombres ya traducidos por ``_split_specifics``, que es el
    diccionario que termina en ``setattr`` o en ``objects.create``.
    """

    def test_lodging_fields_map_both_coordinates(self):
        self.assertEqual(_LODGING_FIELDS["latitud"], "latitude")
        self.assertEqual(_LODGING_FIELDS["longitud"], "longitude")

    def test_pair_is_rounded_in_place(self):
        specifics = {"latitude": "-16.4956789123", "longitude": Decimal("-68.1234564")}

        _normalize_coordinates(specifics)

        self.assertEqual(specifics["latitude"], Decimal("-16.495679"))
        self.assertEqual(specifics["longitude"], Decimal("-68.123456"))

    def test_only_one_coordinate_is_rejected(self):
        with self.assertRaises(ValidationError) as caso:
            _normalize_coordinates({"latitude": "-16.5"})

        self.assertIn("longitud", caso.exception.detail)

    def test_mismatched_nulls_are_rejected(self):
        with self.assertRaises(ValidationError):
            _normalize_coordinates({"latitude": None, "longitude": Decimal("-68.1")})

    def test_out_of_range_is_rejected(self):
        with self.assertRaises(ValidationError) as caso:
            _normalize_coordinates({"latitude": "-91", "longitude": "0"})

        self.assertIn("latitud", caso.exception.detail)

    def test_garbage_is_a_validation_error_not_a_crash(self):
        """Sin esto saldria un InvalidOperation, que seria un 500."""
        with self.assertRaises(ValidationError) as caso:
            _normalize_coordinates({"latitude": "por el centro", "longitude": "0"})

        self.assertIn("latitud", caso.exception.detail)

    def test_both_null_passes_through(self):
        specifics = {"latitude": None, "longitude": None}

        _normalize_coordinates(specifics)

        self.assertEqual(specifics, {"latitude": None, "longitude": None})

    def test_nothing_to_do_without_coordinates(self):
        """Editar solo la direccion no debe tocar la ubicacion."""
        specifics = {"address": "Av. Potosí 123"}

        _normalize_coordinates(specifics)

        self.assertEqual(specifics, {"address": "Av. Potosí 123"})


class CoordinateMigrationTests(SimpleTestCase):
    """De los CHECK solo se puede comprobar que el DDL los declare."""

    def test_ddl_declares_range_and_pair_constraints(self):
        ddl = migracion.ADD_COORDINATES

        self.assertIn("latitud  NUMERIC(9,6)", ddl)
        self.assertIn("longitud NUMERIC(9,6)", ddl)
        self.assertIn("latitud BETWEEN -90 AND 90", ddl)
        self.assertIn("longitud BETWEEN -180 AND 180", ddl)
        self.assertIn("(latitud IS NULL) = (longitud IS NULL)", ddl)

    def test_ddl_is_idempotent(self):
        """El deploy de Railway solo corre migrate; puede encontrarlo hecho."""
        ddl = migracion.ADD_COORDINATES

        self.assertIn("ADD COLUMN IF NOT EXISTS latitud", ddl)
        self.assertIn("ADD COLUMN IF NOT EXISTS longitud", ddl)
        # ADD CONSTRAINT no admite IF NOT EXISTS: se consulta pg_constraint.
        self.assertEqual(ddl.count("FROM pg_constraint WHERE conname"), 3)


class CoordinateApiContractTests(_ViewCase):
    """El contrato que van a consumir Angular y, mas adelante, Flutter."""

    databases: ClassVar[set[str]] = {"default"}

    def test_company_response_exposes_the_pair(self):
        lodging = fake_lodging()
        lodging.latitude = Decimal("-20.460350")
        lodging.longitude = Decimal("-66.825320")

        with patch("apps.catalog.views.get_company_lodging", return_value=lodging):
            response = self._call(
                CompanyLodgingDetailView, "get", f"/api/v1/hospedajes/{LODGING_ID}/", pk=LODGING_ID
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["latitud"], "-20.460350")
        self.assertEqual(response.data["longitud"], "-66.825320")

    def test_public_response_exposes_the_pair(self):
        """La ubicacion de un hotel es publica a proposito."""
        lodging = fake_lodging(status="PUBLICADO")
        lodging.latitude = Decimal("-20.460350")
        lodging.longitude = Decimal("-66.825320")

        with patch("apps.catalog.views.get_public_lodging", return_value=lodging):
            response = self._call(
                PublicLodgingDetailView,
                "get",
                f"/api/v1/marketplace/hospedajes/{LODGING_ID}/",
                tenant=None,
                pk=LODGING_ID,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["latitud"], "-20.460350")
        self.assertEqual(response.data["longitud"], "-66.825320")

    def test_a_lodging_without_location_reports_nulls(self):
        with patch("apps.catalog.views.get_company_lodging", return_value=fake_lodging()):
            response = self._call(
                CompanyLodgingDetailView, "get", f"/api/v1/hospedajes/{LODGING_ID}/", pk=LODGING_ID
            )

        self.assertIsNone(response.data["latitud"])
        self.assertIsNone(response.data["longitud"])

    def test_rooms_have_no_coordinates_of_their_own(self):
        """Una habitacion usa la de su hotel; no declara ninguna."""
        datos = RoomSerializer(fake_room()).data

        self.assertNotIn("latitud", datos)
        self.assertNotIn("longitud", datos)

    def test_patch_forwards_the_rounded_pair(self):
        lodging = fake_lodging()
        with self._valid_catalogs(), patch(
            "apps.catalog.views.update_lodging", return_value=lodging
        ) as update:
            response = self._call(
                CompanyLodgingDetailView,
                "patch",
                f"/api/v1/hospedajes/{LODGING_ID}/",
                {"latitud": "-20.4603501234", "longitud": "-66.8253204321"},
                pk=LODGING_ID,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(update.call_args.kwargs["latitud"], Decimal("-20.460350"))
        self.assertEqual(update.call_args.kwargs["longitud"], Decimal("-66.825320"))

    def test_patch_with_half_a_pair_is_a_400(self):
        with self._valid_catalogs(), patch("apps.catalog.views.update_lodging") as update:
            response = self._call(
                CompanyLodgingDetailView,
                "patch",
                f"/api/v1/hospedajes/{LODGING_ID}/",
                {"latitud": "-20.460350"},
                pk=LODGING_ID,
            )

        self.assertEqual(response.status_code, 400)
        update.assert_not_called()

    def test_patch_with_both_nulls_clears_the_location(self):
        lodging = fake_lodging()
        with self._valid_catalogs(), patch(
            "apps.catalog.views.update_lodging", return_value=lodging
        ) as update:
            response = self._call(
                CompanyLodgingDetailView,
                "patch",
                f"/api/v1/hospedajes/{LODGING_ID}/",
                {"latitud": None, "longitud": None},
                pk=LODGING_ID,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(update.call_args.kwargs["latitud"])
        self.assertIsNone(update.call_args.kwargs["longitud"])

    def test_patch_without_coordinates_leaves_them_alone(self):
        """La decision D2: no mencionarlas significa conservarlas.

        El servicio no debe recibir las claves, porque recibirlas en ``None``
        seria indistinguible de pedir que se borren.
        """
        lodging = fake_lodging()
        with self._valid_catalogs(), patch(
            "apps.catalog.views.update_lodging", return_value=lodging
        ) as update:
            response = self._call(
                CompanyLodgingDetailView,
                "patch",
                f"/api/v1/hospedajes/{LODGING_ID}/",
                {"nombre": "Hotel Kachi Wasi"},
                pk=LODGING_ID,
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("latitud", update.call_args.kwargs)
        self.assertNotIn("longitud", update.call_args.kwargs)

    def test_serializer_field_is_read_only_for_the_tenant_id(self):
        """Las coordenadas no abren una via para colar otros campos."""
        datos = LodgingSerializer(fake_lodging()).data

        self.assertIn("latitud", datos)
        self.assertIn("longitud", datos)
        self.assertEqual(datos["empresa_id"], TENANT_ID)


class LodgingModelCoordinateTests(SimpleTestCase):
    """Las columnas fisicas, con la misma forma que ``ciudad``."""

    def test_columns_match_the_city_convention(self):
        for name, column in (("latitude", "latitud"), ("longitude", "longitud")):
            with self.subTest(name=name):
                field = LodgingEstablishment._meta.get_field(name)

                self.assertEqual(field.db_column, column)
                self.assertEqual(field.max_digits, 9)
                self.assertEqual(field.decimal_places, 6)
                self.assertTrue(field.null)
