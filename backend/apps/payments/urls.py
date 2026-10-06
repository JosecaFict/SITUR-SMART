from django.urls import path

from .views import StripeWebhookView, stripe_return

urlpatterns = [
    path("pagos/stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("pagos/stripe/retorno/", stripe_return, name="stripe-return"),
]
