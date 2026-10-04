from django.urls import path

from .views import ReportCsvView, ReportView

urlpatterns = [
    path("reportes/", ReportView.as_view(), name="reports"),
    path("reportes/exportar/", ReportCsvView.as_view(), name="reports-csv"),
]
