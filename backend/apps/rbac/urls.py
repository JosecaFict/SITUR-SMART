from django.urls import path

from .views import PermissionListView, RoleListCreateView

urlpatterns = [
    path("permissions/", PermissionListView.as_view(), name="permission-list"),
    path("roles/", RoleListCreateView.as_view(), name="role-list-create"),
]
