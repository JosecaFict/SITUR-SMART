from django.core.management.base import BaseCommand

from apps.bookings.services import expire_overdue


class Command(BaseCommand):
    help = (
        "Concilia las reservas pendientes cuyo plazo de pago vencio: confirma las "
        "que Stripe cobro y libera el cupo de las demas. Pensado para un cron."
    )

    def handle(self, *args, **options):
        count = expire_overdue()
        self.stdout.write(self.style.SUCCESS(f"Reservas conciliadas: {count}"))
