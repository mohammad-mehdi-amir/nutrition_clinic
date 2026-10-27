from dataclasses import dataclass, field


class GatewayError(Exception):
    """خطای ارتباط با درگاه یا پاسخ نامعتبر؛ پیامش قابل نمایش به کاربر است."""


@dataclass
class StartResult:
    authority: str
    redirect_url: str


@dataclass
class VerifyResult:
    success: bool
    ref_id: str = ""
    card_pan: str = ""
    message: str = ""
    raw: dict = field(default_factory=dict)


class BaseGateway:
    code = ""

    def start(self, payment, callback_url):
        """ثبت تراکنش در درگاه و برگرداندن آدرس انتقال کاربر."""
        raise NotImplementedError

    def parse_callback(self, params):
        """(authority, user_cancelled) از پارامترهای بازگشت درگاه."""
        raise NotImplementedError

    def verify(self, payment):
        """تأیید سمت سرور تراکنش؛ مبلغ از دیتابیس خوانده می‌شود، نه از مرورگر."""
        raise NotImplementedError

    def inquire(self, payment):
        """
        استعلام تراکنشی که callback آن نرسیده (کاربر برنگشت یا verify با خطای شبکه مواجه شد).
        در زرین‌پال همان verify است: برای پرداخت‌نشده خطا و برای قبلاً تأییدشده کد ۱۰۱ برمی‌گرداند.
        """
        return self.verify(payment)
