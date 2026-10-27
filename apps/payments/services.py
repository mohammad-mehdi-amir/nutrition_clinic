import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .gateways import GatewayError, get_gateway
from .models import Payment

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """خطای قابل نمایش به کاربر."""


def _payable_amount(target):
    """مبلغ از دیتابیس (نه از درخواست کاربر) + بررسی قابل پرداخت بودن."""
    from apps.appointments.models import Appointment
    from apps.shop.models import Order

    now = timezone.now()

    if isinstance(target, Appointment):
        if target.status != "pending" or target.payment_status != Appointment.PAYMENT_UNPAID or not target.deposit:
            raise PaymentError("این نوبت در انتظار پرداخت نیست.")
        if target.payment_deadline and target.payment_deadline <= now:
            raise PaymentError("مهلت پرداخت این نوبت تمام شده است؛ لطفاً دوباره نوبت بگیرید.")
        # آنلاین فقط بیعانه پرداخت می‌شود (اگر درصد بیعانه ۱۰۰ باشد، همان کل هزینه)
        return target.deposit

    if isinstance(target, Order):
        if target.status != Order.STATUS_PENDING or not target.total:
            raise PaymentError("این سفارش در انتظار پرداخت نیست.")
        if target.payment_deadline and target.payment_deadline <= now:
            raise PaymentError("مهلت پرداخت این سفارش تمام شده است.")
        return target.total

    raise PaymentError("مورد پرداخت نامعتبر است.")


def start_payment(user, target, callback_url_builder):
    """
    ایجاد تراکنش و گرفتن آدرس انتقال به درگاه.
    callback_url_builder(payment) آدرس مطلق بازگشت را می‌سازد.
    """
    from apps.appointments.models import Appointment

    amount = _payable_amount(target)
    is_appointment = isinstance(target, Appointment)

    with transaction.atomic():
        # مهلت رزرو را برای مدت حضور کاربر در درگاه تمدید می‌کنیم تا وسط پرداخت منقضی نشود
        window = timezone.now() + timedelta(minutes=settings.PAYMENT_GATEWAY_WINDOW_MINUTES)
        if target.payment_deadline and target.payment_deadline < window:
            target.payment_deadline = window
            target.save(update_fields=["payment_deadline"])

        payment = Payment.objects.create(
            user=user,
            appointment=target if is_appointment else None,
            order=None if is_appointment else target,
            gateway=settings.PAYMENT_GATEWAY,
            amount=amount,
        )

    gateway = get_gateway(payment.gateway)

    try:
        result = gateway.start(payment, callback_url_builder(payment))
    except GatewayError as error:
        payment.status = Payment.STATUS_FAILED
        payment.gateway_message = str(error)[:255]
        payment.save(update_fields=["status", "gateway_message"])
        raise PaymentError(str(error)) from error

    payment.authority = result.authority
    payment.status = Payment.STATUS_REDIRECTED
    payment.save(update_fields=["authority", "status"])

    return payment, result.redirect_url


def handle_callback(payment_id, params):
    """
    بازگشت از درگاه. idempotent است: callback تکراری فقط نتیجه‌ی قبلی را برمی‌گرداند.
    """
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment_id)

        if payment.status in (Payment.STATUS_PAID, Payment.STATUS_FAILED, Payment.STATUS_CANCELLED):
            return payment

        gateway = get_gateway(payment.gateway)
        authority, user_cancelled = gateway.parse_callback(params)

        if not authority or authority != payment.authority:
            logger.warning("Payment %s callback with mismatched authority %r", payment.pk, authority)
            payment.status = Payment.STATUS_FAILED
            payment.gateway_message = "شناسه‌ی بازگشتی درگاه با تراکنش مطابقت ندارد."
            payment.save(update_fields=["status", "gateway_message"])
            return payment

        if user_cancelled:
            payment.status = Payment.STATUS_CANCELLED
            payment.gateway_message = "پرداخت توسط کاربر لغو شد یا ناموفق بود."
            payment.save(update_fields=["status", "gateway_message"])
            return payment

        try:
            result = gateway.verify(payment)
        except GatewayError as error:
            # وضعیت نامشخص: تراکنش redirected می‌ماند تا reconcile_payments دوباره استعلام کند
            payment.gateway_message = str(error)[:255]
            payment.save(update_fields=["gateway_message"])
            return payment

        _apply_verify_result(payment, result)

    return payment


def _apply_verify_result(payment, result):
    """نتیجه‌ی verify/استعلام را روی تراکنش قفل‌شده اعمال می‌کند (مشترک callback و reconcile)."""
    if not result.success:
        payment.status = Payment.STATUS_FAILED
        payment.gateway_message = result.message[:255]
        payment.save(update_fields=["status", "gateway_message"])
        return

    payment.status = Payment.STATUS_PAID
    payment.ref_id = result.ref_id
    payment.card_pan = result.card_pan
    payment.gateway_message = result.message[:255]
    payment.verified_at = timezone.now()
    payment.needs_review = not _fulfil(payment)
    payment.save(update_fields=["status", "ref_id", "card_pan", "gateway_message", "verified_at", "needs_review"])
    if payment.needs_review:
        # پول گرفته شده ولی نوبت/سفارش قابل تأیید نبود ⇒ ادمین باید بازپرداخت کند (ایمیل به ADMINS)
        logger.error(
            "Payment %s (%s, %s تومان, ref %s) succeeded but its target could not be fulfilled; refund needed.",
            payment.pk, payment.description, payment.amount, payment.ref_id,
        )


RECONCILE_PAID = "paid"
RECONCILE_FAILED = "failed"
RECONCILE_PENDING = "pending"
RECONCILE_SKIPPED = "skipped"


def reconcile_payment(payment_id, now=None):
    """
    استعلام یک تراکنش «در حال پرداخت» که callback آن نرسیده.

    - موفق ⇒ مثل callback: پرداخت‌شده و نوبت/سفارش از مسیر _fulfil تکمیل می‌شود.
    - ناموفق ⇒ فقط وقتی failed می‌شود که از PAYMENT_RECONCILE_GIVE_UP_MINUTES گذشته باشد؛
      قبل از آن ممکن است کاربر هنوز در درگاه باشد و دیرتر پرداخت کند.
    - خطای شبکه ⇒ بدون تغییر (هیچ‌وقت به‌خاطر خطای ارتباط، پرداخت را ناموفق فرض نمی‌کنیم).
    قفل ردیف مانع تکمیل دوباره در صورت رسیدن هم‌زمان callback می‌شود.
    """
    now = now or timezone.now()

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment_id)
        if payment.status != Payment.STATUS_REDIRECTED or not payment.authority:
            return RECONCILE_SKIPPED

        try:
            result = get_gateway(payment.gateway).inquire(payment)
        except GatewayError as error:
            logger.warning("Payment %s inquiry failed: %s", payment.pk, error)
            payment.gateway_message = str(error)[:255]
            payment.save(update_fields=["gateway_message"])
            return RECONCILE_PENDING

        give_up_at = payment.created_at + timedelta(minutes=settings.PAYMENT_RECONCILE_GIVE_UP_MINUTES)
        if not result.success and now < give_up_at:
            return RECONCILE_PENDING

        _apply_verify_result(payment, result)
        logger.info("Payment %s reconciled: %s", payment.pk, payment.status)
        return RECONCILE_PAID if payment.status == Payment.STATUS_PAID else RECONCILE_FAILED


def reconcile_payments(now=None):
    """
    استعلام همه‌ی تراکنش‌های redirected قدیمی‌تر از PAYMENT_RECONCILE_AFTER_MINUTES (برای cron).
    نتیجه: شمارش هر حالت.
    """
    now = now or timezone.now()
    threshold = now - timedelta(minutes=settings.PAYMENT_RECONCILE_AFTER_MINUTES)
    ids = list(
        Payment.objects.filter(status=Payment.STATUS_REDIRECTED, created_at__lte=threshold)
        .order_by("created_at")
        .values_list("pk", flat=True)
    )

    counts = {RECONCILE_PAID: 0, RECONCILE_FAILED: 0, RECONCILE_PENDING: 0, RECONCILE_SKIPPED: 0}
    for payment_id in ids:
        counts[reconcile_payment(payment_id, now=now)] += 1
    return counts


def _fulfil(payment):
    """اعمال پرداخت موفق روی نوبت/سفارش طبق قواعد همان اپ."""
    if payment.appointment_id:
        from apps.appointments.services import mark_appointment_paid
        return mark_appointment_paid(payment.appointment)

    from apps.shop.services import mark_order_paid
    return mark_order_paid(payment.order)
