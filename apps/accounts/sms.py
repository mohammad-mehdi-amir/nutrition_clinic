"""
لایه‌ی ارسال پیامک با backend قابل تعویض (settings.SMS_BACKEND).

- ConsoleSMSBackend: توسعه؛ پیام در لاگ چاپ می‌شود.
- KavenegarSMSBackend: ارسال با سرویس verify/lookup کاوه‌نگار.
  تنظیمات از env: SMS_API_KEY، SMS_TEMPLATE (قالب کد بازیابی) و قالب‌های اعلان (SMS_*_TEMPLATE؛
  خالی ⇒ همان پیامک ارسال نمی‌شود). نام قالب‌ها همان قالب تأییدشده در پنل کاوه‌نگار است.
  اعلان‌ها از apps/core/notifications.py ارسال می‌شوند.
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
    def send_lookup(self, phone, template, token, token2="", token3=""):
        """
        ارسال پیامک قالب‌دار (template در پنل سرویس پیامک تعریف شده؛
        token و token2 و token3 جایگزین %token و %token2 و %token3 می‌شوند).
        """
        raise NotImplementedError

    def send_verification_code(self, phone, code):
        self.send_lookup(phone, settings.SMS_TEMPLATE, code)


class ConsoleSMSBackend(BaseSMSBackend):
    def send_lookup(self, phone, template, token, token2="", token3=""):
        tokens = " | ".join(t for t in (token, token2, token3) if t)
        logger.warning("[SMS] to %s: template=%s tokens=%s", phone, template or "-", tokens)

    def send_verification_code(self, phone, code):
        logger.warning("[SMS] to %s: verification code %s", phone, code)


class KavenegarSMSBackend(BaseSMSBackend):
    url = "https://api.kavenegar.com/v1/{api_key}/verify/lookup.json"

    def send_lookup(self, phone, template, token, token2="", token3=""):
        api_key = settings.SMS_API_KEY

        if not api_key or not template:
            raise SMSError("SMS_API_KEY یا نام قالب پیامک تنظیم نشده است.")

        params = {"receptor": phone, "token": token, "template": template}
        if token2:
            params["token2"] = token2
        if token3:
            params["token3"] = token3
        data = urllib.parse.urlencode(params).encode()
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


def send_template(template_setting, phone, *tokens):
    """
    پیامک قالب‌دار با نام قالب از settings (مثلاً SMS_DIET_READY_TEMPLATE) و حداکثر سه token.
    اگر قالب تنظیم نشده باشد ارسال نمی‌شود (در توسعه ConsoleSMSBackend همیشه در لاگ چاپ می‌کند).
    """
    backend = get_backend()
    template = getattr(settings, template_setting, "")
    if not template and not isinstance(backend, ConsoleSMSBackend):
        logger.info("%s تنظیم نشده؛ پیامک ارسال نشد.", template_setting)
        return False
    tokens = [lookup_token(str(t)) for t in tokens][:3]
    backend.send_lookup(phone, template or template_setting, *tokens)
    return True
