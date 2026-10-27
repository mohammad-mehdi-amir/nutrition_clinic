"""
درگاه آزمایشی برای توسعه و تست: کاربر به صفحه‌ای داخلی می‌رود و موفق/ناموفق را انتخاب می‌کند.
در Production (DEBUG=False) غیرفعال است.
"""
import secrets

from django.conf import settings
from django.urls import reverse

from .base import BaseGateway, GatewayError, StartResult, VerifyResult


class FakeGateway(BaseGateway):
    code = "fake"

    def _ensure_allowed(self):
        if not settings.DEBUG and not getattr(settings, "PAYMENT_ALLOW_FAKE_GATEWAY", False):
            raise GatewayError("درگاه آزمایشی در محیط اصلی فعال نیست.")

    def start(self, payment, callback_url):
        self._ensure_allowed()
        authority = f"FAKE{secrets.token_hex(12)}"
        url = f"{reverse('payments:fake_gateway', args=[payment.pk])}?authority={authority}"
        return StartResult(authority=authority, redirect_url=url)

    def parse_callback(self, params):
        return params.get("Authority", ""), params.get("Status") != "OK"

    def verify(self, payment):
        self._ensure_allowed()
        return VerifyResult(success=True, ref_id=f"T{secrets.randbelow(10 ** 8):08d}", card_pan="603799******0000", message="Fake OK")

    def inquire(self, payment):
        # در درگاه آزمایشی فقط انتخاب کاربر در صفحه‌ی آزمایشی معتبر است؛ تراکنش رهاشده یعنی پرداخت‌نشده
        return VerifyResult(success=False, message="پرداخت آزمایشی تکمیل نشد.")
