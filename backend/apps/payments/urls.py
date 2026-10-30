from django.urls import path

from .views import (
    CompanyManualPaymentView,
    CompanyPaymentListView,
    CustomerPaymentDetailView,
    CustomerPaymentListView,
    StripeWebhookView,
    stripe_return,
)

urlpatterns = [
    path("me/pagos/", CustomerPaymentListView.as_view(), name="customer-payment-list"),
    path("me/pagos/<int:pk>/", CustomerPaymentDetailView.as_view(), name="customer-payment-detail"),
    path("empresa/pagos/", CompanyPaymentListView.as_view(), name="company-payment-list"),
    path("empresa/pagos/manuales/", CompanyManualPaymentView.as_view(), name="company-manual-payment"),
    path("pagos/stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("pagos/stripe/retorno/", stripe_return, name="stripe-return"),
]
