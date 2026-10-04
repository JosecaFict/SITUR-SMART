from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.rbac.views import tenant_id_from_request

from .exporters import build_csv, build_pdf, build_xlsx
from .services import build_report


class ReportView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        report = build_report(
            user=request.user,
            tenant_id=tenant_id_from_request(request),
            params=request.query_params,
        )
        return Response(report)


class ReportCsvView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        tenant_id = tenant_id_from_request(request)
        report = build_report(user=request.user, tenant_id=tenant_id, params=request.query_params)
        record_audit(
            actor=request.user,
            tenant_id=tenant_id,
            action="EXPORTAR",
            entity="reporte",
            entity_id=report["tipo"],
            new_data={"alcance": report["alcance"], "filas": len(report["filas"])},
            request=request,
        )
        response = HttpResponse(build_csv(report), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="reporte-{report["tipo"]}.csv"'
        return response


class ReportExcelView(ReportCsvView):
    def get(self, request):
        tenant_id = tenant_id_from_request(request)
        report = build_report(user=request.user, tenant_id=tenant_id, params=request.query_params)
        self._audit(request, report, tenant_id, "XLSX")
        response = HttpResponse(
            build_xlsx(report),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="reporte-{report["tipo"]}.xlsx"'
        return response

    @staticmethod
    def _audit(request, report, tenant_id, format_name):
        record_audit(
            actor=request.user, tenant_id=tenant_id, action="EXPORTAR", entity="reporte",
            entity_id=report["tipo"],
            new_data={"alcance": report["alcance"], "filas": len(report["filas"]), "formato": format_name},
            request=request,
        )


class ReportPdfView(ReportExcelView):
    def get(self, request):
        tenant_id = tenant_id_from_request(request)
        report = build_report(user=request.user, tenant_id=tenant_id, params=request.query_params)
        self._audit(request, report, tenant_id, "PDF")
        response = HttpResponse(build_pdf(report), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="reporte-{report["tipo"]}.pdf"'
        return response
