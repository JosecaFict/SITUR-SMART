import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied

from apps.audit.services import record_audit
from apps.rbac.services import is_superadmin


class BackupUnavailable(APIException):
    status_code = 503
    default_detail = "El servicio de copias de seguridad no está disponible."
    default_code = "backup_unavailable"


class BackupFailed(APIException):
    status_code = 500
    default_detail = "No fue posible generar la copia de seguridad."
    default_code = "backup_failed"


@dataclass
class BackupArtifact:
    file: object
    filename: str
    size: int
    sha256: str


def require_backup_management(actor) -> None:
    if not is_superadmin(actor):
        raise PermissionDenied(
            "Solo el SuperAdministrador puede generar copias de seguridad."
        )


def _database_arguments() -> tuple[list[str], dict[str, str]]:
    database = settings.DATABASES["default"]
    command = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--host",
        str(database.get("HOST") or "127.0.0.1"),
        "--port",
        str(database.get("PORT") or "5432"),
        "--username",
        str(database.get("USER") or "postgres"),
        "--dbname",
        str(database.get("NAME") or "postgres"),
    ]
    environment = os.environ.copy()
    environment["PGPASSWORD"] = str(database.get("PASSWORD") or "")
    sslmode = (database.get("OPTIONS") or {}).get("sslmode")
    if sslmode:
        environment["PGSSLMODE"] = str(sslmode)
    return command, environment


def generate_backup(*, actor, request=None) -> BackupArtifact:
    require_backup_management(actor)
    if shutil.which("pg_dump") is None:
        raise BackupUnavailable(
            "pg_dump no está instalado en el servidor. Revisa la configuración de despliegue."
        )

    backup_file = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
    command, environment = _database_arguments()
    try:
        result = subprocess.run(
            command,
            stdout=backup_file,
            stderr=subprocess.PIPE,
            env=environment,
            check=False,
            timeout=180,
        )
    except subprocess.TimeoutExpired as error:
        backup_file.close()
        raise BackupFailed("La copia excedió el tiempo máximo permitido.") from error
    except OSError as error:
        backup_file.close()
        raise BackupUnavailable("No fue posible ejecutar pg_dump en el servidor.") from error

    if result.returncode != 0:
        backup_file.close()
        raise BackupFailed("PostgreSQL rechazó la generación de la copia de seguridad.")

    backup_file.seek(0)
    digest = hashlib.sha256()
    size = 0
    while chunk := backup_file.read(1024 * 1024):
        digest.update(chunk)
        size += len(chunk)
    backup_file.seek(0)
    timestamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
    filename = f"situr-smart-{timestamp}.dump"
    sha256 = digest.hexdigest()
    record_audit(
        actor=actor,
        action="GENERAR_COPIA",
        entity="copia_seguridad",
        entity_id=filename,
        new_data={"archivo": filename, "tamano_bytes": size, "sha256": sha256},
        request=request,
    )
    return BackupArtifact(
        file=backup_file,
        filename=filename,
        size=size,
        sha256=sha256,
    )

