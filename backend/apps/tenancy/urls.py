from django.urls import path

from .views import (
    CityListView,
    CompanyDetailView,
    CompanyListCreateView,
    CompanyOwnerView,
    CountryListView,
)

urlpatterns = [
    path("catalogos/paises/", CountryListView.as_view(), name="country-list"),
    path("catalogos/ciudades/", CityListView.as_view(), name="city-list"),
    path("empresas/", CompanyListCreateView.as_view(), name="company-list-create"),
    path("empresas/<int:pk>/", CompanyDetailView.as_view(), name="company-detail"),
    path("empresas/<int:pk>/propietario/", CompanyOwnerView.as_view(), name="company-owner"),
]
