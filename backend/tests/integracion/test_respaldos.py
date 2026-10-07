"""Copias de seguridad programadas, contra PostgreSQL real.

pg_dump, Cloudinary y Brevo se reemplazan: aqui se prueba cuando toca una
copia, que se guarda, a quien se avisa y quien puede bajarla.
"""

import io
from datetime import datetime, timedelta
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.backups import scheduled, storage
from apps.backups.models import BackupSchedule, StoredBackup
from apps.backups.services import BackupArtifact, BackupFailed

from .datos import TURISTA, cliente

pytestmark = pytest.mark.django_db(transaction=False)

SUPERADMIN = "superadmin@situr.com.bo"
URL = "/api/v1/admin/copias-seguridad/"


@pytest.fixture
def respaldo(monkeypatch, settings):
    falso = SimpleNamespace(guardadas={}, borradas=[], correos=[], fallar_dump=False)
    settings.WEB_APP_URL = "https://web.test"

    def dump():
        if falso.fallar_dump:
            raise BackupFailed("PostgreSQL rechazó la generación de la copia de seguridad.")
        n = len(falso.guardadas) + len(falso.borradas) + 1
        return BackupArtifact(file=io.BytesIO(b"PGDMP" * n), filename=f"situr-smart-{n:03}.dump", size=5 * n, sha256="a" * 64)

    def upload(file_obj, filename):
        storage_id = f"situr-smart/respaldos/{filename}"
        falso.guardadas[storage_id] = file_obj.read()
        return storage_id

    def delete(storage_id):
        falso.guardadas.pop(storage_id)
        falso.borradas.append(storage_id)

    monkeypatch.setattr(scheduled, "dump_database", dump)
    monkeypatch.setattr(storage, "is_configured", lambda: True)
    monkeypatch.setattr(storage, "upload", upload)
    monkeypatch.setattr(storage, "delete", delete)
    monkeypatch.setattr(storage, "download_link", lambda storage_id: f"https://firmado.test/{storage_id}")
    monkeypatch.setattr(scheduled, "send_email", lambda **kwargs: falso.correos.append(kwargs) or True)
    return falso


def _programar(frecuencia, ultima=None):
    schedule = scheduled.get_schedule()
    schedule.frequency = frecuencia
    schedule.last_run = ultima
    schedule.save()


def _a_las(dias: int, hora: int) -> datetime:
    dia = timezone.localdate() + timedelta(days=dias)
    return datetime.combine(dia, datetime.min.time().replace(hour=hora), tzinfo=timezone.get_current_timezone())


def test_semanal_toca_a_las_3_siete_dias_despues_de_la_ultima(respaldo):
    _programar("SEMANAL", ultima=_a_las(-7, 3))

    assert scheduled.run_if_due(now=_a_las(0, 2)) is None
    copia = scheduled.run_if_due(now=_a_las(0, 3))

    assert copia.origin == "PROGRAMADA"
    assert copia.storage_id in respaldo.guardadas
    assert scheduled.get_schedule().last_run == _a_las(0, 3)
    # La siguiente vuelta del cron ya no repite la copia.
    assert scheduled.run_if_due(now=_a_las(0, 3) + timedelta(minutes=10)) is None


def test_cada_3_dias_y_desactivada(respaldo):
    _programar("CADA_3_DIAS", ultima=_a_las(-3, 4))
    assert scheduled.run_if_due(now=_a_las(0, 3)) is not None

    _programar("DESACTIVADA", ultima=None)
    assert scheduled.next_run(scheduled.get_schedule()) is None
    assert scheduled.run_if_due(now=_a_las(30, 12)) is None


def test_el_correo_lleva_el_enlace_al_panel_y_no_el_archivo(respaldo):
    _programar("SEMANAL")
    copia = scheduled.run_if_due(now=_a_las(0, 3))

    [correo] = respaldo.correos
    assert correo["to_email"] == SUPERADMIN
    assert f"https://web.test/copias-seguridad?copia={copia.id}" in correo["html"]
    assert "PGDMP" not in correo["html"]


def test_conserva_solo_las_ultimas_ocho(respaldo):
    _programar("CADA_3_DIAS")
    for _ in range(10):
        scheduled.create_backup(origin="PROGRAMADA")

    assert StoredBackup.objects.count() == scheduled.KEEP
    assert len(respaldo.guardadas) == scheduled.KEEP
    assert len(respaldo.borradas) == 2


def test_si_falla_avisa_y_reintenta_manana_no_en_cada_vuelta(respaldo):
    _programar("SEMANAL")
    respaldo.fallar_dump = True
    ahora = _a_las(0, 3)

    assert scheduled.run_if_due(now=ahora) is None
    [correo] = respaldo.correos
    assert "No se pudo generar" in correo["subject"]
    assert scheduled.run_if_due(now=ahora + timedelta(minutes=10)) is None
    assert len(respaldo.correos) == 1
    assert scheduled.next_run(scheduled.get_schedule()) == _a_las(1, 3)


def test_el_superadmin_programa_genera_y_baja_desde_la_api(respaldo):
    api = cliente(SUPERADMIN)

    programacion = api.put(f"{URL}programacion/", {"frecuencia": "CADA_3_DIAS"}, format="json").json()
    assert programacion["frecuencia"] == "CADA_3_DIAS"
    assert programacion["almacen_configurado"] is True

    creada = api.post(f"{URL}guardadas/").json()
    assert creada["origen"] == "A_PEDIDO"
    assert creada["correos_enviados"] == 1
    assert [c["id"] for c in api.get(f"{URL}guardadas/").json()] == [creada["id"]]

    enlace = api.post(f"{URL}guardadas/{creada['id']}/enlace/").json()
    assert enlace["url"].startswith("https://firmado.test/situr-smart/respaldos/")
    assert api.post(f"{URL}guardadas/999999/enlace/").status_code == 404


def test_nadie_mas_que_el_superadmin(respaldo):
    turista = cliente(TURISTA)
    assert turista.get(f"{URL}programacion/").status_code == 403
    assert turista.put(f"{URL}programacion/", {"frecuencia": "SEMANAL"}, format="json").status_code == 403
    assert turista.get(f"{URL}guardadas/").status_code == 403
    assert turista.post(f"{URL}guardadas/").status_code == 403
    assert not StoredBackup.objects.exists()


def test_frecuencia_invalida(respaldo):
    respuesta = cliente(SUPERADMIN).put(f"{URL}programacion/", {"frecuencia": "DIARIA"}, format="json")
    assert respuesta.status_code == 400


def test_el_cron_incluye_la_copia(respaldo, stripe):
    _programar("SEMANAL", ultima=timezone.now() - timedelta(days=8))
    salida = StringIO()
    call_command("tareas_programadas", stdout=salida)

    assert "Copia de seguridad: situr-smart-" in salida.getvalue()
    assert BackupSchedule.objects.get().last_run is not None
