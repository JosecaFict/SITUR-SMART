from django.urls import path

from .views import (
    BookingCancelView,
    BookingDetailView,
    BookingListCreateView,
    BookingPayView,
    QuoteView,
)

urlpatterns = [
    path("me/reservas/cotizacion/", QuoteView.as_view(), name="booking-quote"),
    path("me/reservas/", BookingListCreateView.as_view(), name="booking-list-create"),
    path("me/reservas/<int:pk>/", BookingDetailView.as_view(), name="booking-detail"),
    path("me/reservas/<int:pk>/pagar/", BookingPayView.as_view(), name="booking-pay"),
    path("me/reservas/<int:pk>/cancelar/", BookingCancelView.as_view(), name="booking-cancel"),
]
