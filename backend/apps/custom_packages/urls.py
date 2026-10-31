from django.urls import path

from .views import (
                    PackageCatalogView,
                    PackageComponentDetailView,
                    PackageComponentListView,
                    PackageDetailView,
                    PackageListView,
                    PackageQuoteView,
                    PackageValidationView,
)

urlpatterns = [
    path("me/paquetes/catalogo/", PackageCatalogView.as_view(), name="custom-package-catalog"),
    path("me/paquetes/", PackageListView.as_view(), name="custom-package-list"),
    path("me/paquetes/<int:pk>/", PackageDetailView.as_view(), name="custom-package-detail"),
    path("me/paquetes/<int:pk>/componentes/", PackageComponentListView.as_view(), name="custom-package-components"),
    path("me/paquetes/<int:pk>/componentes/<int:component_id>/", PackageComponentDetailView.as_view(), name="custom-package-component-detail"),
    path("me/paquetes/<int:pk>/cotizar/", PackageQuoteView.as_view(), name="custom-package-quote"),
    path("me/paquetes/<int:pk>/validar/", PackageValidationView.as_view(), name="custom-package-validate"),
]
