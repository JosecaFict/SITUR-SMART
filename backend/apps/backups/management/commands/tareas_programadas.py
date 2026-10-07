import threading
import time

from django.core.management.base import BaseCommand

from apps.backups.scheduled import run_if_due
from apps.bookings.services import complete_finished, expire_overdue
from apps.tenancy.subscriptions import process_due

# Tope total para esperar a que salgan el push y el correo antes de terminar.
SEND_WAIT_SECONDS = 30


class Command(BaseCommand):
    help = (
        "Tareas automaticas de la plataforma, para el cron de Railway (cada 10 minutos): "
        "vence las reservas sin pagar, completa las que ya pasaron, avisa, renueva o vence "
        "los planes de las empresas y genera la copia de seguridad cuando toca segun la "
        "frecuencia elegida por el SuperAdmin."
    )

    def handle(self, *args, **options):
        expired = expire_overdue()
        completed = complete_finished()
        plans = process_due()
        backup = run_if_due()

        # El push y el correo de las reservas salen en hilos aparte; si el
        # proceso termina antes, se pierden. Se espera a que terminen.
        deadline = time.monotonic() + SEND_WAIT_SECONDS
        for thread in threading.enumerate():
            if thread is not threading.current_thread():
                thread.join(timeout=max(0, deadline - time.monotonic()))

        self.stdout.write(
            self.style.SUCCESS(
                f"Reservas conciliadas: {expired}. Completadas: {completed}. "
                f"Planes: {plans['avisos']} avisos, {plans['renovadas']} renovados, {plans['vencidas']} vencidos. "
                f"Copia de seguridad: {backup.filename if backup else 'no tocaba'}."
            )
        )
