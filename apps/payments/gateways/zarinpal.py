"""
زرین‌پال (API نسخه‌ی ۴) — مستندات: https://www.zarinpal.com/docs/paymentGateway/connectToGateway.html

- مبلغ همیشه به ریال (currency=IRR) ارسال می‌شود تا درخواست و verify یک واحد داشته باشند.
- sandbox: همان مسیرها روی sandbox.zarinpal.com؛ merchant_id یک UUID دلخواه.
- verify: کد 100 یعنی موفق، کد 101 یعنی قبلاً verify شده (آن هم موفق است).
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

from .base import BaseGateway, GatewayError, StartResult, VerifyResult

logger = logging.getLogger(__name__)

SUCCESS = 100
ALREADY_VERIFIED = 101


class ZarinpalGateway(BaseGateway):
    code = "zarinpal"

    @property
    def timeout(self):
        return settings.ZARINPAL_TIMEOUT

    @property
    def base_url(self):
        host = "sandbox.zarinpal.com" if settings.ZARINPAL_SANDBOX else "payment.zarinpal.com"
        return f"https://{host}/pg"

    @property
    def merchant_id(self):
        if not settings.ZARINPAL_MERCHANT_ID:
            raise GatewayError("درگاه پرداخت پیکربندی نشده است.")
        return settings.ZARINPAL_MERCHANT_ID

    def _post(self, path, payload):
        request = urllib.request.Request(
            f"{self.base_url}/v4/payment/{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            # زرین‌پال خطاها را با کد HTTP غیر 200 و بدنه‌ی JSON برمی‌گرداند
            try:
                return json.loads(error.read().decode())
            except ValueError:
                raise GatewayError("پاسخ نامعتبر از درگاه پرداخت.") from error
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            logger.warning("Zarinpal %s failed: %s", path, error)
            raise GatewayError("ارتباط با درگاه پرداخت برقرار نشد؛ لطفاً دوباره تلاش کنید.") from error

    @staticmethod
    def _error_message(body):
        errors = body.get("errors") or {}
        if isinstance(errors, dict) and errors.get("code"):
            return f"{errors.get('code')}: {errors.get('message', '')}"
        return "پاسخ نامعتبر از درگاه پرداخت."

    def start(self, payment, callback_url):
        metadata = {"order_id": str(payment.pk)}
        phone = getattr(payment.user, "phone_number", None)
        if phone:
            metadata["mobile"] = phone

        body = self._post("request.json", {
            "merchant_id": self.merchant_id,
            "amount": payment.amount_rial,
            "currency": "IRR",
            "callback_url": callback_url,
            "description": payment.description,
            "metadata": metadata,
        })

        data = body.get("data") or {}
        if data.get("code") != SUCCESS or not data.get("authority"):
            logger.warning("Zarinpal request rejected: %s", body)
            raise GatewayError("درخواست پرداخت توسط درگاه پذیرفته نشد. " + self._error_message(body))

        authority = data["authority"]
        return StartResult(authority=authority, redirect_url=f"{self.base_url}/StartPay/{authority}")

    def parse_callback(self, params):
        return params.get("Authority", ""), params.get("Status") != "OK"

    def verify(self, payment):
        body = self._post("verify.json", {
            "merchant_id": self.merchant_id,
            "amount": payment.amount_rial,
            "authority": payment.authority,
        })

        data = body.get("data") or {}
        code = data.get("code")

        if code in (SUCCESS, ALREADY_VERIFIED):
            return VerifyResult(
                success=True,
                ref_id=str(data.get("ref_id", "")),
                card_pan=data.get("card_pan", "") or "",
                message=data.get("message", ""),
                raw={"code": code, "ref_id": data.get("ref_id"), "fee": data.get("fee")},
            )

        return VerifyResult(success=False, message=self._error_message(body), raw={"errors": body.get("errors")})
