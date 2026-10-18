from django.core.management.base import BaseCommand

from apps.shop.services import expire_pending_orders


class Command(BaseCommand):
    help = "لغو سفارش‌های پرداخت‌نشده‌ای که مهلتشان گذشته و آزادسازی موجودی (برای اجرا با cron)."

    def handle(self, *args, **options):
        count = expire_pending_orders()
        self.stdout.write(self.style.SUCCESS(f"{count} سفارش منقضی شد."))
