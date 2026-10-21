"""
درگاه‌های پرداخت.

برای افزودن درگاه جدید (مثلاً اسنپ‌پی برای پرداخت اقساطی):
1. یک کلاس از BaseGateway بسازید و start/verify را پیاده کنید.
2. آن را در GATEWAYS ثبت و به Payment.GATEWAY_CHOICES اضافه کنید.
3. تنظیمات محرمانه را فقط از env بخوانید.
"""
from django.conf import settings

from .base import BaseGateway, GatewayError, StartResult, VerifyResult
from .fake import FakeGateway
from .zarinpal import ZarinpalGateway

GATEWAYS = {
    ZarinpalGateway.code: ZarinpalGateway,
    FakeGateway.code: FakeGateway,
}


def get_gateway(code=None):
    code = code or settings.PAYMENT_GATEWAY
    try:
        return GATEWAYS[code]()
    except KeyError:
        raise GatewayError(f"درگاه پرداخت «{code}» تعریف نشده است.")


__all__ = ["BaseGateway", "GatewayError", "StartResult", "VerifyResult", "get_gateway", "GATEWAYS"]
