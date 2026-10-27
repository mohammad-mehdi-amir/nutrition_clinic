from django.core.management.base import BaseCommand

from apps.appointments.services import complete_past_appointments, expire_pending_appointments


class Command(BaseCommand):
    help = (
        "لغو نوبت‌های پرداخت‌نشده‌ای که مهلت پرداختشان گذشته و ثبت «انجام‌شده» برای نوبت‌های "
        "تأییدشده‌ی روزهای گذشته (برای اجرا با cron)."
    )

    def handle(self, *args, **options):
        expired = expire_pending_appointments()
        completed = complete_past_appointments()
        self.stdout.write(self.style.SUCCESS(f"{expired} نوبت منقضی و {completed} نوبت انجام‌شده ثبت شد."))
