"""
لایه‌ی ارسال پیامک با backend قابل تعویض (settings.SMS_BACKEND).

- ConsoleSMSBackend: توسعه؛ پیام در لاگ چاپ می‌شود.
- KavenegarSMSBackend: ارسال با سرویس verify/lookup کاوه‌نگار.
  تنظیمات از env: SMS_API_KEY، SMS_TEMPLATE (قالب کد بازیابی) و SMS_DIET_READY_TEMPLATE
  (قالب «رژیم آماده است»؛ خالی ⇒ این پیامک ارسال نمی‌شود). نام قالب‌ها همان قالب تأییدشده در پنل کاوه‌نگار است.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class SMSError(Exception):
    pass


class BaseSMSBackend:
    def send_lookup(self, phone, template, token):
        """ارسال پیامک قالب‌دار (template در پنل سرویس پیامک تعریف شده؛ token جایگزین %token می‌شود)."""
        raise NotImplementedError

    def send_verification_code(self, phone, code):
        self.send_lookup(phone, settings.SMS_TEMPLATE, code)


class ConsoleSMSBackend(BaseSMSBackend):
    def send_lookup(self, phone, template, token):
        logger.warning("[SMS] to %s: template=%s token=%s", phone, template or "-", token)

    def send_verification_code(self, phone, code):
        logger.warning("[SMS] to %s: verification code %s", phone, code)


class KavenegarSMSBackend(BaseSMSBackend):
    url = "https://api.kavenegar.com/v1/{api_key}/verify/lookup.json"

    def send_lookup(self, phone, template, token):
        api_key = settings.SMS_API_KEY

        if not api_key or not template:
            raise SMSError("SMS_API_KEY یا نام قالب پیامک تنظیم نشده است.")

        data = urllib.parse.urlencode({"receptor": phone, "token": token, "template": template}).encode()
        request = urllib.request.Request(self.url.format(api_key=api_key), data=data, method="POST")

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise SMSError("ارسال پیامک ناموفق بود.") from error

        if payload.get("return", {}).get("status") != 200:
            raise SMSError(f"پاسخ نامعتبر سرویس پیامک: {payload.get('return')}")


def get_backend():
    return import_string(settings.SMS_BACKEND)()


def send_verification_code(phone, code):
    get_backend().send_verification_code(phone, code)


def lookup_token(text, fallback="مراجع"):
    """token کاوه‌نگار نباید فاصله داشته باشد؛ فاصله با نیم‌فاصله جایگزین می‌شود."""
    text = (text or "").strip()
    return text.replace(" ", "\u200c")[:30] if text else fallback


def send_diet_ready(phone, name):
    """پیامک «رژیم شما آماده است». بدون قالب تنظیم‌شده (SMS_DIET_READY_TEMPLATE) ارسال نمی‌شود."""
    backend = get_backend()
    template = settings.SMS_DIET_READY_TEMPLATE
    if not template and not isinstance(backend, ConsoleSMSBackend):
        logger.info("SMS_DIET_READY_TEMPLATE تنظیم نشده؛ پیامک آماده بودن رژیم ارسال نشد.")
        return False
    backend.send_lookup(phone, template, lookup_token(name))
    return True
