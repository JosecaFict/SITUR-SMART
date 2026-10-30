from django.core.management.base import BaseCommand

from apps.payments.refunds import reconcile_pending


class Command(BaseCommand):
    help = "Consulta en Stripe los reembolsos pendientes cuyo webhook no llegó."

    def handle(self, *args, **options):
        updated = reconcile_pending()
        self.stdout.write(self.style.SUCCESS(f"Reembolsos actualizados: {updated}"))
