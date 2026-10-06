from django.urls import path

from .views import (
    DeviceRemoveView,
    DeviceView,
    MarkAllReadView,
    MarkReadView,
    NotificationListView,
    UnreadCountView,
)

urlpatterns = [
    path("me/notificaciones/", NotificationListView.as_view(), name="notification-list"),
    path("me/notificaciones/no-leidas/", UnreadCountView.as_view(), name="notification-unread"),
    path("me/notificaciones/leer-todas/", MarkAllReadView.as_view(), name="notification-read-all"),
    path("me/notificaciones/<int:pk>/leer/", MarkReadView.as_view(), name="notification-read"),
    path("me/dispositivos/", DeviceView.as_view(), name="push-device"),
    path("me/dispositivos/quitar/", DeviceRemoveView.as_view(), name="push-device-remove"),
]
