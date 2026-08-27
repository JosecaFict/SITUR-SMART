from django.urls import path

from .views import TenantDetailView, TenantListCreateView


urlpatterns = [
    path("", TenantListCreateView.as_view(), name="tenant-list-create"),
    path("<int:pk>/", TenantDetailView.as_view(), name="tenant-detail"),
]