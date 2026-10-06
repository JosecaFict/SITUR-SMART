from django.urls import path

from .views import (
    ActivityDetailView,
    ActivityListView,
    ItineraryDetailView,
    ItineraryListView,
)

urlpatterns = [
    path("me/itinerarios/", ItineraryListView.as_view(), name="itinerary-list"),
    path("me/itinerarios/<int:pk>/", ItineraryDetailView.as_view(), name="itinerary-detail"),
    path("me/itinerarios/<int:pk>/actividades/", ActivityListView.as_view(), name="itinerary-activity-list"),
    path(
        "me/itinerarios/<int:pk>/actividades/<int:activity_id>/",
        ActivityDetailView.as_view(),
        name="itinerary-activity-detail",
    ),
]
