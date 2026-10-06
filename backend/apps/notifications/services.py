"""Notificaciones al usuario.

``notify`` es la unica entrada: guarda el aviso para la bandeja de la app y lo
manda por push a los celulares del usuario. Los modulos que avisan (reservas,
pagos) no saben nada de Firebase.
"""

from django.db.models import QuerySet
from django.utils import timezone
from rest_framework.exceptions import NotFound

from . import push
from .models import Notification, PushDevice


def notify(*, user, kind: str, title: str, message: str, data: dict | None = None) -> Notification:
    notification = Notification.objects.create(
        user=user, kind=kind, title=title[:150], message=message, data=data or {}
    )
    push.push_notification(notification)
    return notification


def register_device(*, user, token: str, platform: str) -> PushDevice:
    """Guarda el token de Firebase del celular con sesion iniciada.

    El token es del celular, no de la cuenta: si ahi entra otra cuenta, el
    dispositivo pasa a ella y la anterior deja de recibir avisos en ese celular.
    """
    device, _ = PushDevice.objects.update_or_create(
        token=token, defaults={"user": user, "platform": platform}
    )
    return device


def unregister_device(*, user, token: str) -> None:
    """Al cerrar sesion el celular deja de recibir los avisos de esa cuenta."""
    PushDevice.objects.filter(user=user, token=token).delete()


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
