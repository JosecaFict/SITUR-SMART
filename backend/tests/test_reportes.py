from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.reports.services import parse_filters, report_scope
from apps.reports.views import ReportCsvView, ReportView


class ReportScopeTests(SimpleTestCase):
    @patch("apps.reports.services.require_permission")
    @patch("apps.reports.services.is_superadmin", return_value=True)
    def test_superadmin_can_use_global_scope(self, _is_superadmin, require_permission):
        self.assertEqual(report_scope(user=Mock(), tenant_id=None), (True, None))
        self.assertEqual(require_permission.call_args.args[1], "REPORTES_GLOBALES")

    @patch("apps.reports.services.is_superadmin", return_value=False)
    def test_tenant_user_cannot_query_without_tenant(self, _is_superadmin):
        with self.assertRaises(PermissionDenied):
            report_scope(user=Mock(), tenant_id=None)

    @patch("apps.reports.services.require_permission")
    @patch("apps.reports.services.require_tenant_access")
    @patch("apps.reports.services.is_superadmin", return_value=False)
    def test_tenant_scope_checks_access_and_permission(
        self, _is_superadmin, require_access, require_permission
    ):
        user = Mock()
        self.assertEqual(report_scope(user=user, tenant_id=7), (False, 7))
        require_access.assert_called_once_with(user, 7)
        require_permission.assert_called_once_with(user, "REPORTES_TENANT", 7)


class ReportFilterTests(SimpleTestCase):
    def test_rejects_inverted_date_range(self):
        with self.assertRaises(ValidationError):
            parse_filters({"tipo": "catalogo", "desde": "2026-10-04", "hasta": "2026-10-01"})

    def test_rejects_unknown_report(self):
        with self.assertRaises(ValidationError):
            parse_filters({"tipo": "pagos"})


class ReportViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = Mock(is_authenticated=True)
        self.report = {
            "tipo": "catalogo",
            "alcance": "EMPRESA",
            "columnas": [["nombre", "Nombre"], ["detalle", "Detalle"]],
            "filas": [{"nombre": "Café, museo", "detalle": '=CMD("x")'}],
        }

    @patch("apps.reports.views.build_report")
    def test_passes_tenant_header_to_report_builder(self, build_report):
        build_report.return_value = self.report
        request = self.factory.get("/api/v1/reportes/", HTTP_X_TENANT_ID="9")
        force_authenticate(request, user=self.user)
        response = ReportView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(build_report.call_args.kwargs["tenant_id"], 9)

    @patch("apps.reports.views.record_audit")
    @patch("apps.reports.views.build_report")
    def test_csv_is_utf8_and_quoted(self, build_report, record_audit):
        build_report.return_value = self.report
        request = self.factory.get("/api/v1/reportes/exportar/", HTTP_X_TENANT_ID="9")
        force_authenticate(request, user=self.user)
        response = ReportCsvView.as_view()(request)
        body = response.content.decode("utf-8-sig")
        self.assertEqual(response.status_code, 200)
        self.assertIn('"Café, museo"', body)
        self.assertIn("'=CMD(\"\"x\"\")", body)
        self.assertIn("reporte-catalogo.csv", response["Content-Disposition"])
        record_audit.assert_called_once()
