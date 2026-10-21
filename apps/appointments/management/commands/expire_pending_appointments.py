from django.core.management.base import BaseCommand

from apps.appointments.services import expire_pending_appointments


class Command(BaseCommand):
    help = "لغو نوبت‌های پرداخت‌نشده‌ای که مهلت پرداختشان گذشته (برای اجرا با cron)."

    def handle(self, *args, **options):
        count = expire_pending_appointments()
        self.stdout.write(self.style.SUCCESS(f"{count} نوبت منقضی شد."))
