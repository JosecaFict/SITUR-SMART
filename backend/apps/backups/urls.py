from django.urls import path

from .views import (
    BackupDownloadView,
    BackupScheduleView,
    StoredBackupLinkView,
    StoredBackupListView,
)

urlpatterns = [
    path("admin/copias-seguridad/descargar/", BackupDownloadView.as_view(), name="backup-download"),
    path("admin/copias-seguridad/programacion/", BackupScheduleView.as_view(), name="backup-schedule"),
    path("admin/copias-seguridad/guardadas/", StoredBackupListView.as_view(), name="backup-stored-list"),
    path(
        "admin/copias-seguridad/guardadas/<int:pk>/enlace/",
        StoredBackupLinkView.as_view(),
        name="backup-stored-link",
    ),
]
