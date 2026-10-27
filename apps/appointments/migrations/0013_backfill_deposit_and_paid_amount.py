from django.db import migrations
from django.db.models import F

PAID_STATUSES = ("paid", "refund_requested", "refunded")


def backfill(apps, schema_editor):
    """
    نوبت‌های قبل از سیستم بیعانه با پرداخت کامل ثبت شده‌اند:
    بیعانه = کل هزینه، و برای نوبت‌های پرداخت‌شده مبلغ دریافت‌شده = کل هزینه.
    """
    Appointment = apps.get_model("appointments", "Appointment")
    Appointment.objects.update(deposit=F("fee"))
    Appointment.objects.filter(payment_status__in=PAID_STATUSES).update(paid_amount=F("fee"))


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0012_appointment_deposit_appointment_paid_amount_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
