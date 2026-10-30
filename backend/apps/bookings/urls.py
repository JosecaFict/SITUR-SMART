from django.urls import path

from .company_views import (
    CheckInView,
    CompanyBookingDetailView,
    CompanyBookingListView,
    ReportCustomerView,
    VoucherLookupView,
)
from .views import (
    BookingCancellationQuoteView,
    BookingCancelView,
    BookingDetailView,
    BookingListCreateView,
    BookingPaidCancellationView,
    BookingPayView,
    BookingReceiptLinkView,
    QuoteView,
    receipt_pdf,
)

urlpatterns = [
    path("me/reservas/cotizacion/", QuoteView.as_view(), name="booking-quote"),
    path("me/reservas/", BookingListCreateView.as_view(), name="booking-list-create"),
    path("me/reservas/<int:pk>/", BookingDetailView.as_view(), name="booking-detail"),
    path("me/reservas/<int:pk>/pagar/", BookingPayView.as_view(), name="booking-pay"),
    path("me/reservas/<int:pk>/cancelar/", BookingCancelView.as_view(), name="booking-cancel"),
    path(
        "me/reservas/<int:pk>/cancelacion/cotizacion/",
        BookingCancellationQuoteView.as_view(),
        name="booking-cancellation-quote",
    ),
    path(
        "me/reservas/<int:pk>/cancelacion/",
        BookingPaidCancellationView.as_view(),
        name="booking-paid-cancellation",
    ),
    path("me/reservas/<int:pk>/comprobante/", BookingReceiptLinkView.as_view(), name="booking-receipt"),
    # Publico pero firmado: lo abre el navegador del celular o el enlace del correo.
    path("comprobantes/<str:token>/", receipt_pdf, name="booking-receipt-public"),
    # La empresa que vende (X-Tenant-ID): sus reservas, llegada y reportes.
    path("empresa/reservas/", CompanyBookingListView.as_view(), name="company-booking-list"),
    path("empresa/reservas/validar/", VoucherLookupView.as_view(), name="company-voucher-lookup"),
    path("empresa/reservas/<int:pk>/", CompanyBookingDetailView.as_view(), name="company-booking-detail"),
    path("empresa/reservas/<int:pk>/llegada/", CheckInView.as_view(), name="company-booking-checkin"),
    path("empresa/reservas/<int:pk>/reportar/", ReportCustomerView.as_view(), name="company-booking-report"),
]
