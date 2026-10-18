"""
لایه‌ی ارسال پیامک با backend قابل تعویض (settings.SMS_BACKEND).

- ConsoleSMSBackend: توسعه؛ پیام در لاگ چاپ می‌شود.
- KavenegarSMSBackend: ارسال با سرویس verify/lookup کاوه‌نگار.
  تنظیمات از env: SMS_API_KEY و SMS_TEMPLATE (نام قالب تأییدشده در پنل کاوه‌نگار).
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
    def send_verification_code(self, phone, code):
        raise NotImplementedError


class ConsoleSMSBackend(BaseSMSBackend):
    def send_verification_code(self, phone, code):
        logger.warning("[SMS] to %s: verification code %s", phone, code)


class KavenegarSMSBackend(BaseSMSBackend):
    url = "https://api.kavenegar.com/v1/{api_key}/verify/lookup.json"

    def send_verification_code(self, phone, code):
        api_key = settings.SMS_API_KEY
        template = settings.SMS_TEMPLATE

        if not api_key or not template:
            raise SMSError("SMS_API_KEY / SMS_TEMPLATE تنظیم نشده است.")

        data = urllib.parse.urlencode({"receptor": phone, "token": code, "template": template}).encode()
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
