from django.urls import path

from .views import ReportCsvView, ReportExcelView, ReportPdfView, ReportView

urlpatterns = [
    path("reportes/", ReportView.as_view(), name="reports"),
    path("reportes/exportar/", ReportCsvView.as_view(), name="reports-csv"),
    path("reportes/exportar/excel/", ReportExcelView.as_view(), name="reports-excel"),
    path("reportes/exportar/pdf/", ReportPdfView.as_view(), name="reports-pdf"),
]
