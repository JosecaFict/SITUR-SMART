"""Run the persistent communication push outbox (no broker required)."""

import math
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from apps.notifications.campaigns import process_due_campaigns
from apps.notifications.email_outbox import process_pending_email
from apps.notifications.outbox import process_pending_push


class Command(BaseCommand):
    help = "Procesa campañas programadas y las colas independientes de push y correo."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Procesa un lote y termina.")
        parser.add_argument("--limit", type=int, default=100, help="Entregas por lote (1-1000).")
        parser.add_argument("--poll-seconds", type=float, default=5,
                            help="Espera entre lotes (1-60 segundos).")

    def handle(self, *args, **options):
        limit = options["limit"]
        poll_seconds = options["poll_seconds"]
        if not 1 <= limit <= 1000:
            raise CommandError("--limit debe estar entre 1 y 1000.")
        if not math.isfinite(poll_seconds) or not 1 <= poll_seconds <= 60:
            raise CommandError("--poll-seconds debe estar entre 1 y 60.")
        try:
            while True:
                close_old_connections()
                scheduled = process_due_campaigns(limit=limit)
                processed = process_pending_push(limit=limit)
                emails = process_pending_email(limit=limit)
                if emails:
                    self.stdout.write(f"Correos procesados: {emails}.")
                if scheduled:
                    self.stdout.write(f"Comunicaciones programadas procesadas: {scheduled}.")
                if processed or options["once"]:
                    self.stdout.write(f"Entregas procesadas: {processed}.")
                if options["once"]:
                    break
                time.sleep(poll_seconds)
        except KeyboardInterrupt:
            self.stdout.write("Worker de push detenido.")
        finally:
            close_old_connections()
