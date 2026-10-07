from django.urls import path

from .views import (
    AdminCityDetailView,
    AdminCityListCreateView,
    AdminCityStatusView,
    AdminCountryDetailView,
    AdminCountryListCreateView,
    AdminCountryStatusView,
    CityListView,
    CompanyDetailView,
    CompanyListCreateView,
    CompanyOwnerView,
    CompanySignupView,
    CompanyStatusView,
    CompanySubscriptionView,
    CountryListView,
    MyPlanPayView,
    MyPlanView,
    PlanListView,
)

urlpatterns = [
    path("catalogos/paises/", CountryListView.as_view(), name="country-list"),
    path("catalogos/ciudades/", CityListView.as_view(), name="city-list"),
    path("admin/catalogos/paises/", AdminCountryListCreateView.as_view(), name="admin-country-list-create"),
    path("admin/catalogos/paises/<int:pk>/", AdminCountryDetailView.as_view(), name="admin-country-detail"),
    path("admin/catalogos/paises/<int:pk>/estado/", AdminCountryStatusView.as_view(), name="admin-country-status"),
    path("admin/catalogos/ciudades/", AdminCityListCreateView.as_view(), name="admin-city-list-create"),
    path("admin/catalogos/ciudades/<int:pk>/", AdminCityDetailView.as_view(), name="admin-city-detail"),
    path("admin/catalogos/ciudades/<int:pk>/estado/", AdminCityStatusView.as_view(), name="admin-city-status"),
    path("planes/", PlanListView.as_view(), name="plan-list"),
    path("empresas/", CompanyListCreateView.as_view(), name="company-list-create"),
    path("empresas/autoregistro/", CompanySignupView.as_view(), name="company-signup"),
    path("empresas/<int:pk>/", CompanyDetailView.as_view(), name="company-detail"),
    # El estado tiene accion propia: reglas de transicion y requisitos de
    # activacion que no son los de editar un dato cualquiera.
    path("empresas/<int:pk>/estado/", CompanyStatusView.as_view(), name="company-status"),
    path("empresas/<int:pk>/propietario/", CompanyOwnerView.as_view(), name="company-owner"),
    path("empresas/<int:pk>/suscripcion/", CompanySubscriptionView.as_view(), name="company-subscription"),
    # "Mi plan" de la empresa del encabezado X-Tenant-ID.
    path("empresa/mi-plan/", MyPlanView.as_view(), name="my-plan"),
    path("empresa/mi-plan/pagar/", MyPlanPayView.as_view(), name="my-plan-pay"),
]
