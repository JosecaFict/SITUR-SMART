from django.urls import path

from .views import AuditLogListView

urlpatterns = [
    path("bitacora/", AuditLogListView.as_view(), name="audit-log-list"),
]
