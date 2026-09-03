from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied

from apps.tenancy.serializers import CompanyCreateSerializer
from apps.tenancy.services import _unique_subdomain, require_company_management


class CompanyCreateSerializerTests(SimpleTestCase):
    @patch("apps.tenancy.serializers.User.objects.filter")
    @patch("apps.tenancy.serializers.City.objects.filter")
    def test_accepts_company_with_new_owner(self, city_filter, user_filter):
        city_filter.return_value.exists.return_value = True
        user_filter.return_value.first.return_value = None
        serializer = CompanyCreateSerializer(
            data={
                "razon_social": "Servicios Turísticos del Oriente SRL",
                "nombre_comercial": "SCZ Tours",
                "ciudad_id": 1,
                "nit": "123456789",
                "email_contacto": "contacto@scztours.bo",
                "propietario": {
                    "email": "propietario@scztours.bo",
                    "nombres": "Ana",
                    "apellidos": "Rojas",
                    "password": "Temporal-Situr-2026!",
                },
            }
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["propietario"]["email"] == "propietario@scztours.bo"

    @patch("apps.tenancy.serializers.User.objects.filter")
    def test_requires_temporary_password_for_new_owner(self, user_filter):
        user_filter.return_value.first.return_value = None
        serializer = CompanyCreateSerializer(
            data={
                "razon_social": "Empresa de Turismo SRL",
                "nombre_comercial": "Turismo Seguro",
                "propietario": {
                    "email": "nuevo@empresa.bo",
                    "nombres": "Luis",
                    "apellidos": "Pérez",
                },
            }
        )

        assert not serializer.is_valid()
        assert "password" in serializer.errors["propietario"]


class CompanyServiceTests(SimpleTestCase):
    @patch("apps.tenancy.services.Tenant.objects.filter")
    def test_generates_unique_subdomain(self, tenant_filter):
        tenant_filter.side_effect = [Mock(exists=lambda: True), Mock(exists=lambda: False)]

        assert _unique_subdomain("SCZ Tours") == "scz-tours-2"

    @patch("apps.tenancy.services.is_superadmin", return_value=False)
    def test_rejects_company_management_for_non_superadmin(self, _is_superadmin):
        with self.assertRaises(PermissionDenied):
            require_company_management(Mock())
