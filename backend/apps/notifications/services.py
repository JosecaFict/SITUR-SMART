"""Notificaciones al usuario.

``notify`` es la unica entrada: hoy guarda el aviso para la bandeja de la app;
cuando llegue el push de Firebase, se enviara desde aqui mismo y ningun
modulo que avisa tendra que cambiar.
"""

from django.db.models import QuerySet
from django.utils import timezone
from rest_framework.exceptions import NotFound

from .models import Notification


def notify(*, user, kind: str, title: str, message: str, data: dict | None = None) -> Notification:
    return Notification.objects.create(
        user=user, kind=kind, title=title[:150], message=message, data=data or {}
    )


def user_notifications(*, user) -> QuerySet[Notification]:
    return Notification.objects.filter(user=user)


def unread_count(*, user) -> int:
    return Notification.objects.filter(user=user, read_at=None).count()


def mark_read(*, user, notification_id: int) -> Notification:
    notification = Notification.objects.filter(user=user, id=notification_id).first()
    if notification is None:
        raise NotFound("Notificación no encontrada.")
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return notification


def mark_all_read(*, user) -> int:
    return Notification.objects.filter(user=user, read_at=None).update(read_at=timezone.now())
