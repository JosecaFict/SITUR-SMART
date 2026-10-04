from django.urls import path

from .views import BackupDownloadView

urlpatterns = [
    path("admin/copias-seguridad/descargar/", BackupDownloadView.as_view(), name="backup-download"),
]
