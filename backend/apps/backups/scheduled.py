"""Copias de seguridad automaticas.

El SuperAdmin elige la frecuencia (cada 3 dias o semanal) en la web. El cron
``tareas_programadas`` corre cada pocos minutos y llama a ``run_if_due``: cuando
toca, genera la copia con pg_dump, la guarda privada en Cloudinary y le manda a
cada SuperAdmin un correo con el enlace para bajarla desde el panel.

Por correo va un enlace y no el archivo: la copia tiene toda la base (datos
personales, contrasenas cifradas) y un adjunto queda para siempre en un buzon.
El enlace pide iniciar sesion como SuperAdmin.
"""

import logging
from datetime import datetime, time, timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.html import escape
from rest_framework.exceptions import NotFound

from apps.accounts.brevo import send_email
from apps.accounts.models import User
from apps.audit.services import record_audit

from . import storage
from .models import BackupSchedule, StoredBackup
from .services import (
    BackupFailed,
    BackupUnavailable,
    dump_database,
    require_backup_management,
)

logger = logging.getLogger(__name__)

# Hora local a la que toca la copia: de madrugada, con poco uso.
RUN_AT = time(3, 0)
# Copias que se conservan; las mas viejas se borran del almacen.
KEEP = 8


def get_schedule() -> BackupSchedule:
    schedule, _ = BackupSchedule.objects.get_or_create(id=1)
    return schedule


def next_run(schedule: BackupSchedule) -> datetime | None:
    """Cuando toca la proxima copia, o None si esta desactivada."""
    days = BackupSchedule.DAYS.get(schedule.frequency)
    if days is None:
        return None
    zone = timezone.get_current_timezone()
    if schedule.last_run is None:
        return datetime.combine(timezone.localdate(), RUN_AT, tzinfo=zone)
    last_day = timezone.localtime(schedule.last_run).date()
    return datetime.combine(last_day + timedelta(days=days), RUN_AT, tzinfo=zone)


def update_schedule(*, actor, frequency: str, request=None) -> BackupSchedule:
    require_backup_management(actor)
    schedule = get_schedule()
    previous = schedule.frequency
    schedule.frequency = frequency
    schedule.updated_by = actor
    schedule.save()
    record_audit(
        actor=actor,
        action="PROGRAMAR_COPIA",
        entity="copia_seguridad",
        previous_data={"frecuencia": previous},
        new_data={"frecuencia": frequency},
        request=request,
    )
    return schedule


def list_backups() -> list[StoredBackup]:
    return list(StoredBackup.objects.all()[:KEEP])


def create_backup(*, origin: str, actor=None, request=None) -> StoredBackup:
    """Genera la copia, la guarda en el almacen y la registra. No manda correo."""
    if not storage.is_configured():
        raise BackupUnavailable("No hay dónde guardar la copia: Cloudinary no está configurado.")
    artifact = dump_database()
    try:
        storage_id = storage.upload(artifact.file, artifact.filename)
    except storage.StorageUnavailable as exc:
        logger.error("No se pudo guardar la copia en Cloudinary: %s", exc)
        raise BackupFailed("La copia se generó, pero no se pudo guardar en el almacén.") from exc
    finally:
        artifact.file.close()
    backup = StoredBackup.objects.create(
        filename=artifact.filename,
        storage_id=storage_id,
        size=artifact.size,
        sha256=artifact.sha256,
        origin=origin,
        requested_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    record_audit(
        actor=actor,
        action="GENERAR_COPIA",
        entity="copia_seguridad",
        entity_id=artifact.filename,
        new_data={"archivo": artifact.filename, "tamano_bytes": artifact.size, "origen": origin},
        request=request,
    )
    _prune()
    return backup


def _prune() -> None:
    for old in StoredBackup.objects.all()[KEEP:]:
        try:
            storage.delete(old.storage_id)
        except storage.StorageUnavailable as exc:
            # Se reintenta en la proxima copia: la fila queda hasta poder borrarla.
            logger.warning("No se pudo borrar la copia vieja %s: %s", old.filename, exc)
            continue
        old.delete()


def download_link(*, actor, backup_id: int, request=None) -> str:
    require_backup_management(actor)
    backup = StoredBackup.objects.filter(id=backup_id).first()
    if backup is None:
        raise NotFound("La copia ya no está disponible.")
    record_audit(
        actor=actor,
        action="DESCARGAR_COPIA",
        entity="copia_seguridad",
        entity_id=backup.filename,
        request=request,
    )
    return storage.download_link(backup.storage_id)


def run_if_due(now: datetime | None = None) -> StoredBackup | None:
    """Lo que hace el cron: genera la copia si toca y avisa por correo."""
    now = now or timezone.now()
    schedule = get_schedule()
    due = next_run(schedule)
    if due is None or now < due:
        return None
    try:
        backup = create_backup(origin=StoredBackup.Origin.SCHEDULED)
    except (BackupFailed, BackupUnavailable) as exc:
        logger.error("Fallo la copia automatica: %s", exc.detail)
        # Se reintenta manana y no en cada pasada del cron: si no, el
        # SuperAdmin recibiria un correo de error cada 10 minutos.
        days = BackupSchedule.DAYS[schedule.frequency]
        schedule.last_run = now - timedelta(days=days - 1)
        schedule.save(update_fields=["last_run", "updated_at"])
        notify(error=str(exc.detail))
        return None
    schedule.last_run = now
    schedule.save(update_fields=["last_run", "updated_at"])
    notify(backup=backup)
    return backup


# --- Correo -----------------------------------------------------------------------


def _recipients():
    return User.objects.filter(
        status=User.Status.ACTIVE,
        user_roles__role__code="SUPER_ADMIN",
        user_roles__tenant__isnull=True,
    ).distinct()


def _size(size: int) -> str:
    return f"{max(1, round(size / 1024))} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB"


def notify(*, backup: StoredBackup | None = None, error: str | None = None) -> int:
    """Avisa a cada SuperAdmin. Devuelve a cuantos se les envio."""
    panel = f"{settings.WEB_APP_URL.rstrip('/')}/copias-seguridad"
    if backup is not None:
        subject = "Copia de seguridad lista - SITUR-SMART"
        when = timezone.localtime(backup.created_at).strftime("%d/%m/%Y %H:%M")
        body = (
            f"<p>Se generó la copia de seguridad automática del <strong>{escape(when)}</strong> "
            f"({escape(_size(backup.size))}).</p>"
            f'<p><a href="{escape(panel)}?copia={backup.id}" style="display:inline-block;padding:10px 18px;'
            'background:#0f766e;color:#fff;border-radius:8px;text-decoration:none;font-weight:600">'
            "Descargar la copia</a></p>"
            "<p style=\"color:#64748b;font-size:13px\">El enlace abre el panel de SITUR-SMART y pide "
            f"iniciar sesión como SuperAdmin. Se conservan las últimas {KEEP} copias.</p>"
        )
    else:
        subject = "No se pudo generar la copia de seguridad - SITUR-SMART"
        body = (
            f"<p>La copia de seguridad automática falló: {escape(error or 'error desconocido')}</p>"
            "<p>Se volverá a intentar mañana. También puedes generarla a mano desde "
            f'<a href="{escape(panel)}">Copias de seguridad</a>.</p>'
        )
    html = (
        '<div style="font-family:Arial,sans-serif;max-width:520px;color:#0f172a">'
        '<h2 style="color:#0f766e">SITUR-SMART</h2>'
        f"{body}</div>"
    )
    sent = 0
    for user in _recipients():
        if send_email(to_email=user.email, to_name=user.get_full_name(), subject=subject, html=html):
            sent += 1
    return sent
