import csv
from io import StringIO

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.rbac.views import tenant_id_from_request

from .services import build_report


def _csv_value(value):
    text = "" if value is None else str(value)
    # Evita que Excel/LibreOffice interpreten contenido proveniente de usuarios
    # como una formula al abrir el archivo.
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


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
        output = StringIO()
        output.write("\ufeff")
        writer = csv.writer(output)
        writer.writerow([column[1] for column in report["columnas"]])
        for row in report["filas"]:
            writer.writerow([_csv_value(row.get(column[0])) for column in report["columnas"]])
        record_audit(
            actor=request.user,
            tenant_id=tenant_id,
            action="EXPORTAR",
            entity="reporte",
            entity_id=report["tipo"],
            new_data={"alcance": report["alcance"], "filas": len(report["filas"])},
            request=request,
        )
        response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="reporte-{report["tipo"]}.csv"'
        return response
