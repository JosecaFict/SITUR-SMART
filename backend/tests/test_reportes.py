from datetime import datetime
from io import BytesIO
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from openpyxl import load_workbook
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.reports.exporters import build_xlsx, export_value, logo_path
from apps.reports.services import parse_filters, report_scope
from apps.reports.views import ReportCsvView, ReportExcelView, ReportPdfView, ReportView


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


class ReportExporterTests(SimpleTestCase):
    def test_packaged_logo_is_available_without_the_frontend_directory(self):
        path = logo_path()
        self.assertIsNotNone(path)
        self.assertEqual(path.parent.name, "assets")
        self.assertEqual(path.name, "situr-smart-logo.png")

    def test_iso_timestamp_is_presented_in_a_readable_local_format(self):
        self.assertEqual(
            export_value("registro", "2026-09-06T17:34:05.335489+00:00"),
            "06/09/2026 13:34",
        )

    def test_excel_contains_the_logo_and_a_real_date_cell(self):
        report = {
            "tipo": "plataforma",
            "empresa": None,
            "indicadores": [{"etiqueta": "Empresas", "valor": 1, "detalle": ""}],
            "columnas": [["empresa", "Empresa"], ["registro", "Fecha de registro"]],
            "filas": [{"empresa": "ToursBo", "registro": "2026-09-06T17:34:05+00:00"}],
            "nota": "Datos de prueba.",
            "filtros": {},
        }
        workbook = load_workbook(filename=BytesIO(build_xlsx(report)))
        sheet = workbook.active
        self.assertEqual(len(sheet._images), 1)
        self.assertIsInstance(sheet["B9"].value, datetime)
        self.assertEqual(sheet["B9"].number_format, "dd/mm/yyyy hh:mm")


class ReportViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = Mock(is_authenticated=True)
        self.report = {
            "tipo": "catalogo",
            "alcance": "EMPRESA",
            "empresa": {"id": 9, "nombre": "Empresa de prueba"},
            "indicadores": [
                {"clave": "total", "etiqueta": "Productos", "valor": 1, "detalle": ""}
            ],
            "columnas": [["nombre", "Nombre"], ["detalle", "Detalle"]],
            "filas": [{"nombre": "Café, museo", "detalle": '=CMD("x")'}],
            "nota": "Datos de prueba.",
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

    @patch("apps.reports.views.ReportExcelView._audit")
    @patch("apps.reports.views.build_report")
    def test_excel_is_a_real_xlsx_workbook(self, build_report, audit):
        build_report.return_value = self.report
        request = self.factory.get("/api/v1/reportes/exportar/excel/", HTTP_X_TENANT_ID="9")
        force_authenticate(request, user=self.user)
        response = ReportExcelView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"PK"))
        self.assertIn("reporte-catalogo.xlsx", response["Content-Disposition"])
        audit.assert_called_once()

    @patch("apps.reports.views.ReportPdfView._audit")
    @patch("apps.reports.views.build_report")
    def test_pdf_is_a_real_pdf_document(self, build_report, audit):
        build_report.return_value = self.report
        request = self.factory.get("/api/v1/reportes/exportar/pdf/", HTTP_X_TENANT_ID="9")
        force_authenticate(request, user=self.user)
        response = ReportPdfView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn("reporte-catalogo.pdf", response["Content-Disposition"])
        audit.assert_called_once()
