from django.urls import path

from .views import (
    CompanyProductDetailView,
    CompanyProductListCreateView,
    CurrencyListView,
    ProductTypeListView,
    PublicProductDetailView,
    PublicProductListView,
)

urlpatterns = [
    path("catalogos/tipos-producto/", ProductTypeListView.as_view(), name="product-type-list"),
    path("catalogos/monedas/", CurrencyListView.as_view(), name="currency-list"),
    path("marketplace/productos/", PublicProductListView.as_view(), name="public-product-list"),
    path("marketplace/productos/<int:pk>/", PublicProductDetailView.as_view(), name="public-product-detail"),
    path("productos/", CompanyProductListCreateView.as_view(), name="company-product-list-create"),
    path("productos/<int:pk>/", CompanyProductDetailView.as_view(), name="company-product-detail"),
]
