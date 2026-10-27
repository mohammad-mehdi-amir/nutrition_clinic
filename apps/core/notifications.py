"""
اعلان‌های پیامکی به بیمار/مشتری برای رویدادهای نوبت، سفارش و رژیم.

- هر اعلان در «تنظیمات سایت» روشن/خاموش می‌شود و نام قالب کاوه‌نگارش در .env است (SMS_*_TEMPLATE).
- ارسال بعد از commit تراکنش انجام می‌شود؛ پس اگر کار اصلی rollback شود پیامکی نمی‌رود.
- خطای سرویس پیامک فقط لاگ می‌شود و هرگز کار اصلی (پرداخت، تأیید، تحویل) را خراب نمی‌کند.
"""
import logging

from django.db import transaction

from utils.jalali import format_jalali

logger = logging.getLogger(__name__)


def _phone(user):
    return user.phone_number or user.username


def _notify(switch, template_setting, user, *tokens):
    from apps.core.models import SiteSettings

    if not getattr(SiteSettings.load(), switch):
        return

    phone = _phone(user)

    def send():
        from apps.accounts.sms import SMSError, send_template

        try:
            send_template(template_setting, phone, *tokens)
        except SMSError:
            logger.exception("ارسال پیامک %s به %s ناموفق بود.", template_setting, phone)

    transaction.on_commit(send)


def _appointment_tokens(appointment):
    patient = appointment.patient
    return patient.first_name, format_jalali(appointment.date), appointment.start_time.strftime("%H:%M")


def appointment_confirmed(appointment):
    _notify("sms_appointment_confirmed", "SMS_APPOINTMENT_CONFIRMED_TEMPLATE",
            appointment.patient, *_appointment_tokens(appointment))


def appointment_cancelled_by_clinic(appointment):
    _notify("sms_appointment_cancelled", "SMS_APPOINTMENT_CANCELLED_TEMPLATE",
            appointment.patient, *_appointment_tokens(appointment))


def order_paid(order):
    _notify("sms_order_paid", "SMS_ORDER_PAID_TEMPLATE", order.user, order.user.first_name, order.pk)


def order_shipped(order):
    _notify("sms_order_shipped", "SMS_ORDER_SHIPPED_TEMPLATE", order.user, order.user.first_name, order.pk)


def diet_ready(user):
    _notify("sms_diet_ready", "SMS_DIET_READY_TEMPLATE", user, user.first_name)
