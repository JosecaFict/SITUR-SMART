from django.urls import path

from .views import (
    CompanyLodgingDetailView,
    CompanyLodgingListCreateView,
    CompanyLodgingRoomListCreateView,
    CompanyProductDetailView,
    CompanyProductListCreateView,
    CompanyRoomDetailView,
    CurrencyListView,
    GeocodingReverseView,
    GeocodingSearchView,
    LodgingTypeListView,
    ProductScheduleView,
    ProductTypeListView,
    PublicLodgingDetailView,
    PublicLodgingListView,
    PublicLodgingRoomListView,
    PublicProductDetailView,
    PublicProductListView,
    PublicRoomDetailView,
    PublicRoomListView,
)

urlpatterns = [
    path("catalogos/tipos-producto/", ProductTypeListView.as_view(), name="product-type-list"),
    path("catalogos/tipos-hospedaje/", LodgingTypeListView.as_view(), name="lodging-type-list"),
    path("catalogos/monedas/", CurrencyListView.as_view(), name="currency-list"),
    path("marketplace/productos/", PublicProductListView.as_view(), name="public-product-list"),
    path("marketplace/productos/<int:pk>/", PublicProductDetailView.as_view(), name="public-product-detail"),
    path("marketplace/hospedajes/", PublicLodgingListView.as_view(), name="public-lodging-list"),
    path("marketplace/hospedajes/<int:pk>/", PublicLodgingDetailView.as_view(), name="public-lodging-detail"),
    path(
        "marketplace/hospedajes/<int:pk>/habitaciones/",
        PublicLodgingRoomListView.as_view(),
        name="public-lodging-room-list",
    ),
    path("marketplace/habitaciones/", PublicRoomListView.as_view(), name="public-room-list"),
    path("marketplace/habitaciones/<int:pk>/", PublicRoomDetailView.as_view(), name="public-room-detail"),
    path("productos/", CompanyProductListCreateView.as_view(), name="company-product-list-create"),
    path("productos/<int:pk>/", CompanyProductDetailView.as_view(), name="company-product-detail"),
    # Publicacion programada de un producto o de un hospedaje (por su producto).
    path("productos/<int:pk>/programacion/", ProductScheduleView.as_view(), name="company-product-schedule"),
    path("hospedajes/", CompanyLodgingListCreateView.as_view(), name="company-lodging-list-create"),
    path("hospedajes/<int:pk>/", CompanyLodgingDetailView.as_view(), name="company-lodging-detail"),
    path(
        "hospedajes/<int:pk>/habitaciones/",
        CompanyLodgingRoomListCreateView.as_view(),
        name="company-lodging-room-list-create",
    ),
    path("habitaciones/<int:pk>/", CompanyRoomDetailView.as_view(), name="company-room-detail"),
    # Geocodificacion: el navegador nunca habla con el proveedor, la clave no
    # sale del servidor. Requieren sesion, X-Tenant-ID y PRODUCTOS_GESTIONAR.
    path("geo/buscar/", GeocodingSearchView.as_view(), name="geocoding-search"),
    path("geo/inverso/", GeocodingReverseView.as_view(), name="geocoding-reverse"),
]
