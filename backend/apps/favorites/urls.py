from django.urls import path

from .views import FavoriteDetailView, FavoriteListView

urlpatterns = [
    path("me/favoritos/", FavoriteListView.as_view(), name="favorite-list"),
    path("me/favoritos/<int:producto_id>/", FavoriteDetailView.as_view(), name="favorite-detail"),
]
