from django.urls import path

from . import views

urlpatterns = [
    path("promociones/", views.PromotionListView.as_view(), name="promotion-list"),
    path(
        "promociones/productos-elegibles/",
        views.EligibleProductsView.as_view(),
        name="promotion-products",
    ),
    path("promociones/cotizar/", views.PreviewView.as_view(), name="promotion-preview"),
    path(
        "promociones/<int:pk>/",
        views.PromotionDetailView.as_view(),
        name="promotion-detail",
    ),
    path(
        "promociones/<int:pk>/publicar/",
        views.PromotionPublishView.as_view(),
        name="promotion-publish",
    ),
    path(
        "promociones/<int:pk>/desactivar/",
        views.PromotionDisableView.as_view(),
        name="promotion-disable",
    ),
    path(
        "promociones/<int:pk>/cotizacion/",
        views.RecalculateView.as_view(),
        name="promotion-recalculate",
    ),
    path(
        "promociones/<int:pk>/componentes/",
        views.ComponentListView.as_view(),
        name="promotion-components",
    ),
    path(
        "promociones/<int:pk>/componentes/<int:component_id>/",
        views.ComponentDetailView.as_view(),
        name="promotion-component-detail",
    ),
    path(
        "marketplace/promociones/",
        views.PublicPromotionListView.as_view(),
        name="public-promotion-list",
    ),
    path(
        "marketplace/promociones/<int:pk>/",
        views.PublicPromotionDetailView.as_view(),
        name="public-promotion-detail",
    ),
]
