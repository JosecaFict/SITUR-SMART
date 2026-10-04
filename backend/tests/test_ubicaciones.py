from typing import ClassVar
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.tenancy.serializers import CityWriteSerializer
from apps.tenancy.services import (
    change_city_status,
    change_country_status,
    require_location_management,
)


class LocationPermissionTests(SimpleTestCase):
    @patch("apps.tenancy.services.is_superadmin", return_value=False)
    def test_only_superadmin_manages_locations(self, _is_superadmin):
        with self.assertRaises(PermissionDenied):
            require_location_management(Mock())

    @patch("apps.tenancy.services.is_superadmin", return_value=True)
    def test_superadmin_manages_locations(self, _is_superadmin):
        require_location_management(Mock())


class LocationRuleTests(SimpleTestCase):
    databases: ClassVar[set[str]] = {"default"}

    @patch("apps.tenancy.services.is_superadmin", return_value=True)
    @patch("apps.tenancy.services.Country.objects.filter")
    @patch("apps.tenancy.services.City.objects.filter")
    def test_country_with_active_cities_cannot_be_deactivated(
        self, city_filter, country_filter, _is_superadmin
    ):
        country_filter.return_value.first.return_value = Mock(id=1, active=True)
        city_filter.return_value.exists.return_value = True

        with self.assertRaises(ValidationError) as error:
            change_country_status(actor=Mock(), country_id=1, activo=False)

        self.assertIn("activo", error.exception.detail)

    @patch("apps.tenancy.services.record_audit")
    @patch("apps.tenancy.services.is_superadmin", return_value=True)
    @patch("apps.tenancy.services.City.objects.select_related")
    def test_city_of_inactive_country_cannot_be_activated(
        self, select_related, _is_superadmin, _audit
    ):
        city = Mock(id=3, active=False, country=Mock(active=False))
        select_related.return_value.filter.return_value.first.return_value = city

        with self.assertRaises(ValidationError) as error:
            change_city_status(actor=Mock(), city_id=3, activo=True)

        self.assertIn("activo", error.exception.detail)


class CitySerializerTests(SimpleTestCase):
    def test_coordinates_must_be_sent_together(self):
        serializer = CityWriteSerializer(
            data={"nombre": "Sucre", "pais_id": 1, "latitud": "-19.033320"}
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("coordenadas", serializer.errors)

    def test_accepts_city_without_coordinates(self):
        serializer = CityWriteSerializer(
            data={"nombre": "Sucre", "pais_id": 1, "zona_horaria": "America/La_Paz"}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
