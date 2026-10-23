from django.core.management.base import BaseCommand
from django.utils import timezone
from feedback.services import process_pending_event_automations


class Command(BaseCommand):
    help = "Periodic automated feedback invitation scheduler & reminder processor for EventPulse."

    def add_arguments(self, parser):
        parser.add_argument('--domain', type=str, default='127.0.0.1:8000', help="Domain or host URL for feedback links")

    def handle(self, *args, **options):
        domain = options['domain']
        now_str = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        self.stdout.write(f"[{now_str}] Starting EventPulse automation runner (Host: {domain})...")

        summary = process_pending_event_automations(domain=domain)

        self.stdout.write(self.style.SUCCESS(
            f"Automation cycle finished successfully:\n"
            f"  • Events evaluated: {summary['events_checked']}\n"
            f"  • New invitations created: {summary['invitations_created']}\n"
            f"  • Emails dispatched: {summary['emails_sent']}\n"
            f"  • Delivery errors: {summary['errors']}"
        ))
