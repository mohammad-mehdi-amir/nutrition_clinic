import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import PasswordResetCode, User
from .sms import SMSError, send_verification_code

logger = logging.getLogger(__name__)

CODE_LENGTH = 6
CODE_TTL = timedelta(minutes=2)
RESEND_INTERVAL = timedelta(minutes=2)
MAX_CODES_PER_HOUR = 5
MAX_ATTEMPTS = 5


class ResetError(Exception):
    """خطای قابل نمایش به کاربر."""


def _hash_code(phone, code):
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def request_reset_code(phone):
    """
    ارسال کد بازیابی. برای جلوگیری از افشای ثبت‌نام بودن شماره،
    در صورت نبود کاربر هم خطایی برنمی‌گرداند (rate limit برای همه اعمال می‌شود).
    """
    now = timezone.now()
    recent = PasswordResetCode.objects.filter(phone_number=phone, created_at__gte=now - timedelta(hours=1))

    if recent.filter(created_at__gte=now - RESEND_INTERVAL).exists():
        raise ResetError("کد قبلی هنوز معتبر است؛ لطفاً دو دقیقه بعد دوباره تلاش کنید.")

    if recent.count() >= MAX_CODES_PER_HOUR:
        raise ResetError("تعداد درخواست‌ها بیش از حد مجاز است؛ لطفاً یک ساعت بعد تلاش کنید.")

    user = User.objects.filter(phone_number=phone, is_active=True).first()
    if user is None:
        return

    code = f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"

    with transaction.atomic():
        PasswordResetCode.objects.filter(user=user, used_at__isnull=True).update(used_at=now)
        PasswordResetCode.objects.create(
            user=user,
            phone_number=phone,
            code_hash=_hash_code(phone, code),
            expires_at=now + CODE_TTL,
        )

    try:
        send_verification_code(phone, code)
    except SMSError:
        logger.exception("Sending password reset SMS failed")
        raise ResetError("ارسال پیامک با خطا مواجه شد؛ لطفاً چند دقیقه بعد تلاش کنید.")


def verify_and_reset(phone, code, new_password):
    """بررسی کد و تغییر رمز. در صورت موفقیت کاربر را برمی‌گرداند."""
    now = timezone.now()

    with transaction.atomic():
        reset = (
            PasswordResetCode.objects.select_for_update()
            .filter(phone_number=phone, used_at__isnull=True, expires_at__gt=now)
            .select_related("user")
            .first()
        )

        if reset is None:
            raise ResetError("کد منقضی شده یا معتبر نیست؛ کد جدید دریافت کنید.")

        if reset.attempts >= MAX_ATTEMPTS:
            raise ResetError("تعداد تلاش‌های ناموفق زیاد است؛ کد جدید دریافت کنید.")

        code_is_valid = hmac.compare_digest(reset.code_hash, _hash_code(phone, code))

        if not code_is_valid:
            # شمارنده باید commit شود؛ پس خطا بعد از بلوک atomic داده می‌شود
            reset.attempts += 1
            reset.save(update_fields=["attempts"])
        else:
            user = reset.user
            user.set_password(new_password)
            user.save(update_fields=["password"])

            reset.used_at = now
            reset.save(update_fields=["used_at"])

    if not code_is_valid:
        raise ResetError("کد واردشده صحیح نیست.")

    return user
