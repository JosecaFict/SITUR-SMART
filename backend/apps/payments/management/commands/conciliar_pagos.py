from django.core.management.base import BaseCommand

from apps.payments.reconciliation import run


class Command(BaseCommand):
    help = "Compara ahora los pagos y reembolsos de SITUR-SMART con Stripe."

    def handle(self, *args, **options):
        result = run(force=True)
        self.stdout.write(self.style.SUCCESS(
            "Conciliación terminada: "
            f"{result['pagos']['revisados']} pagos y "
            f"{result['reembolsos']['revisados']} reembolsos revisados."
        ))
