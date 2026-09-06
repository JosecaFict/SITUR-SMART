from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.tenancy.serializers import CompanyCreateSerializer
from apps.tenancy.services import (
    _resolve_plan,
    _unique_subdomain,
    ensure_product_quota_available,
    ensure_user_quota_available,
    require_company_management,
)


class CompanyCreateSerializerTests(SimpleTestCase):
    @patch("apps.tenancy.serializers.Plan.objects.filter")
    @patch("apps.tenancy.serializers.User.objects.filter")
    @patch("apps.tenancy.serializers.City.objects.filter")
    def test_accepts_company_with_new_owner(self, city_filter, user_filter, plan_filter):
        city_filter.return_value.exists.return_value = True
        plan_filter.return_value.exists.return_value = True
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

    @patch("apps.tenancy.serializers.Plan.objects.filter")
    @patch("apps.tenancy.serializers.User.objects.filter")
    def test_requires_temporary_password_for_new_owner(self, user_filter, plan_filter):
        user_filter.return_value.first.return_value = None
        plan_filter.return_value.exists.return_value = True
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


class SubscriptionServiceTests(SimpleTestCase):
    @patch("apps.tenancy.services.Plan.objects.filter")
    def test_resolve_plan_raises_when_plan_does_not_exist(self, plan_filter):
        plan_filter.return_value.first.return_value = None

        with self.assertRaises(ValidationError):
            _resolve_plan("INEXISTENTE")

    @patch("apps.tenancy.services.UserTenant.objects.filter")
    @patch("apps.tenancy.services.Subscription.objects.select_related")
    def test_user_quota_blocks_when_plan_limit_reached(self, select_related, user_tenant_filter):
        subscription = Mock(plan=Mock(max_users=3))
        select_related.return_value.filter.return_value.first.return_value = subscription
        user_tenant_filter.return_value.count.return_value = 3

        with self.assertRaises(ValidationError):
            ensure_user_quota_available(tenant_id=1)

    @patch("apps.tenancy.services.Subscription.objects.select_related")
    def test_user_quota_allows_when_no_active_subscription(self, select_related):
        select_related.return_value.filter.return_value.first.return_value = None

        ensure_user_quota_available(tenant_id=1)

    @patch("apps.catalog.models.TourismProduct.objects.filter")
    @patch("apps.tenancy.services.Subscription.objects.select_related")
    def test_product_quota_blocks_when_plan_limit_reached(self, select_related, product_filter):
        subscription = Mock(plan=Mock(max_products=15))
        select_related.return_value.filter.return_value.first.return_value = subscription
        product_filter.return_value.count.return_value = 15

        with self.assertRaises(ValidationError):
            ensure_product_quota_available(tenant_id=1)

    @patch("apps.catalog.models.TourismProduct.objects.filter")
    @patch("apps.tenancy.services.Subscription.objects.select_related")
    def test_product_quota_allows_when_under_limit(self, select_related, product_filter):
        subscription = Mock(plan=Mock(max_products=15))
        select_related.return_value.filter.return_value.first.return_value = subscription
        product_filter.return_value.count.return_value = 5

        ensure_product_quota_available(tenant_id=1)
