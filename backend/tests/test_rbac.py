from unittest.mock import Mock, patch

from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.services import (
    _protect_company_owner,
    _require_assignable_role,
    _require_company_employee_management,
)
from apps.rbac.models import Role
from apps.rbac.services import _tenant_permissions, update_tenant_role


class TenantRoleSecurityTests(TestCase):
    @patch("apps.accounts.services.is_superadmin", return_value=True)
    def test_superadmin_cannot_manage_company_employees(self, _is_superadmin):
        with self.assertRaises(PermissionDenied):
            _require_company_employee_management(Mock())

    def test_rejects_platform_permissions_for_company_role(self):
        with self.assertRaises(ValidationError):
            _tenant_permissions(["TENANTS_GESTIONAR", "PRODUCTOS_LEER"])

    @patch("apps.rbac.services.get_tenant_role")
    def test_system_role_cannot_be_modified(self, get_role):
        get_role.return_value = Mock(is_system=True)
        with self.assertRaises(PermissionDenied):
            update_tenant_role(actor=Mock(), tenant_id=4, role_id=2, name="Otro nombre")

    @patch("apps.accounts.services.is_superadmin", return_value=False)
    def test_owner_role_cannot_be_assigned_by_company_user(self, _is_superadmin):
        role = Mock(scope=Role.Scope.TENANT, code="TENANT_ADMIN")
        with self.assertRaises(PermissionDenied):
            _require_assignable_role(Mock(), role)

    @patch("apps.accounts.services.UserRole.objects.filter")
    def test_owner_cannot_be_modified_from_employee_management(self, role_filter):
        role_filter.return_value.exists.return_value = True
        with self.assertRaises(PermissionDenied):
            _protect_company_owner(Mock(), user_id=8, tenant_id=3)
