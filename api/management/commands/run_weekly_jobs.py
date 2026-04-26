from django.core.management.base import BaseCommand
from api.services.incentive_service import calculate_weekly_summary
from api.emails import send_weekly_report


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        summary = calculate_weekly_summary()
        send_weekly_report(summary)