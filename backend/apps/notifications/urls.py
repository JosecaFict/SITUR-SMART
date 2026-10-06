from django.urls import path

from .views import MarkAllReadView, MarkReadView, NotificationListView, UnreadCountView

urlpatterns = [
    path("me/notificaciones/", NotificationListView.as_view(), name="notification-list"),
    path("me/notificaciones/no-leidas/", UnreadCountView.as_view(), name="notification-unread"),
    path("me/notificaciones/leer-todas/", MarkAllReadView.as_view(), name="notification-read-all"),
    path("me/notificaciones/<int:pk>/leer/", MarkReadView.as_view(), name="notification-read"),
]
