from django.urls import path

from .communication_views import (
    CancelCommunicationView,
    CommunicationAudienceView,
    CommunicationDetailView,
    CommunicationEmailPreviewView,
    CommunicationOptionsView,
    CommunicationPreferencesView,
    CommunicationsView,
    PublishCommunicationView,
    WebPushConfigView,
)
from .unsubscribe import UnsubscribeView
from .views import (
    DeviceRemoveView,
    DeviceView,
    InterestsView,
    MarkAllReadView,
    MarkReadView,
    NotificationListView,
    UnreadCountView,
)

urlpatterns = [
    path("comunicaciones/", CommunicationsView.as_view(), name="communications"),
    path("comunicaciones/audiencia/", CommunicationAudienceView.as_view(), name="communication-audience"),
    path("comunicaciones/opciones/", CommunicationOptionsView.as_view(), name="communication-options"),
    path("comunicaciones/<int:pk>/", CommunicationDetailView.as_view(), name="communication-detail"),
    path("comunicaciones/<int:pk>/publicar/", PublishCommunicationView.as_view(), name="communication-publish"),
    path("comunicaciones/<int:pk>/correo/", CommunicationEmailPreviewView.as_view(), name="communication-email-preview"),
    path("comunicaciones/baja/<str:token>/", UnsubscribeView.as_view(), name="communication-unsubscribe"),
    path("comunicaciones/<int:pk>/cancelar/", CancelCommunicationView.as_view(), name="communication-cancel"),
    path("me/comunicaciones/preferencias/", CommunicationPreferencesView.as_view(), name="communication-preferences"),
    path("notificaciones/push-config/", WebPushConfigView.as_view(), name="web-push-config"),
    path("me/notificaciones/", NotificationListView.as_view(), name="notification-list"),
    path("me/notificaciones/no-leidas/", UnreadCountView.as_view(), name="notification-unread"),
    path("me/notificaciones/leer-todas/", MarkAllReadView.as_view(), name="notification-read-all"),
    path("me/notificaciones/<int:pk>/leer/", MarkReadView.as_view(), name="notification-read"),
    path("me/intereses/", InterestsView.as_view(), name="customer-interests"),
    path("me/dispositivos/", DeviceView.as_view(), name="push-device"),
    path("me/dispositivos/quitar/", DeviceRemoveView.as_view(), name="push-device-remove"),
]
