from django.urls import path

from .tour_views import (
    CompanyTourDetailView,
    CompanyTourListCreateView,
    DepartureCloseView,
    DepartureDetailView,
    GuideDetailView,
    GuideListCreateView,
    PublicTourDeparturesView,
    PublicTourDetailView,
    TourDepartureListCreateView,
    TourStopsView,
)
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
    # Tours y experiencias (CU20): ficha, recorrido, salidas y guias.
    path("tours/", CompanyTourListCreateView.as_view(), name="company-tour-list-create"),
    path("tours/<int:pk>/", CompanyTourDetailView.as_view(), name="company-tour-detail"),
    path("tours/<int:pk>/paradas/", TourStopsView.as_view(), name="company-tour-stops"),
    path("tours/<int:pk>/salidas/", TourDepartureListCreateView.as_view(), name="company-tour-departures"),
    path("salidas/<int:pk>/", DepartureDetailView.as_view(), name="company-departure-detail"),
    path("salidas/<int:pk>/cerrar/", DepartureCloseView.as_view(), name="company-departure-close"),
    path("guias/", GuideListCreateView.as_view(), name="company-guide-list-create"),
    path("guias/<int:pk>/", GuideDetailView.as_view(), name="company-guide-detail"),
    path("marketplace/tours/<int:pk>/", PublicTourDetailView.as_view(), name="public-tour-detail"),
    path("marketplace/tours/<int:pk>/salidas/", PublicTourDeparturesView.as_view(), name="public-tour-departures"),
    # Geocodificacion: el navegador nunca habla con el proveedor, la clave no
    # sale del servidor. Requieren sesion, X-Tenant-ID y PRODUCTOS_GESTIONAR.
    path("geo/buscar/", GeocodingSearchView.as_view(), name="geocoding-search"),
    path("geo/inverso/", GeocodingReverseView.as_view(), name="geocoding-reverse"),
]
