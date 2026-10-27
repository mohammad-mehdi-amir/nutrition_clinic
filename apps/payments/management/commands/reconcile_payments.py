from django.core.management.base import BaseCommand

from apps.payments.services import reconcile_payments


class Command(BaseCommand):
    help = (
        "استعلام تراکنش‌های «در حال پرداخت» که callback درگاه برای آن‌ها نرسیده "
        "(کاربر برنگشت یا verify با خطای شبکه مواجه شد) — برای اجرا با cron."
    )

    def handle(self, *args, **options):
        counts = reconcile_payments()
        self.stdout.write(self.style.SUCCESS(
            f"موفق: {counts['paid']}، ناموفق: {counts['failed']}، "
            f"هنوز نامشخص: {counts['pending']}، رد شده: {counts['skipped']}"
        ))
