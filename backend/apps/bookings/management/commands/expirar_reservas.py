import threading
import time

from django.core.management.base import BaseCommand

from apps.bookings.services import complete_finished, expire_overdue

# Lo que se espera a que salgan el push y el correo antes de terminar.
SEND_WAIT_SECONDS = 30


class Command(BaseCommand):
    help = (
        "Pone al dia las reservas: concilia las pendientes cuyo plazo de pago "
        "vencio (confirma las que Stripe cobro y libera el cupo de las demas) y "
        "completa las confirmadas cuyo servicio ya paso. Lo corre el cron de "
        "Railway; el webhook de Stripe hace lo mismo al instante y esto es el respaldo."
    )

    def handle(self, *args, **options):
        expired = expire_overdue()
        completed = complete_finished()
        # El push y el correo salen en hilos aparte; si el proceso termina
        # antes, el turista no se entera. Se espera a que terminen.
        deadline = time.monotonic() + SEND_WAIT_SECONDS
        for thread in threading.enumerate():
            if thread is not threading.current_thread():
                thread.join(timeout=max(0, deadline - time.monotonic()))
        self.stdout.write(
            self.style.SUCCESS(f"Reservas conciliadas: {expired}. Completadas: {completed}.")
        )
