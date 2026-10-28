import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Payment(models.Model):
    """
    یک تلاش پرداخت برای یک نوبت یا یک سفارش.
    قواعد تجاری نوبت و سفارش در اپ‌های خودشان می‌ماند؛ این مدل فقط تراکنش را ثبت می‌کند.
    """

    GATEWAY_ZARINPAL = "zarinpal"
    GATEWAY_FAKE = "fake"
    GATEWAY_CHOICES = [
        (GATEWAY_ZARINPAL, "زرین‌پال"),
        (GATEWAY_FAKE, "درگاه آزمایشی (توسعه)"),
    ]

    STATUS_INITIATED = "initiated"
    STATUS_REDIRECTED = "redirected"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_INITIATED, "ایجاد شده"),
        (STATUS_REDIRECTED, "در حال پرداخت"),
        (STATUS_PAID, "موفق"),
        (STATUS_FAILED, "ناموفق"),
        (STATUS_CANCELLED, "انصراف کاربر"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="کاربر",
        help_text="کاربری که پرداخت را انجام داده است.",
    )

    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name="نوبت",
        help_text="نوبتی که این پرداخت بابت آن است (اگر پرداخت برای نوبت باشد).",
    )
    order = models.ForeignKey(
        "shop.Order",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name="سفارش",
        help_text="سفارشی که این پرداخت بابت آن است (اگر پرداخت برای سفارش باشد).",
    )

    gateway = models.CharField(
        max_length=20,
        choices=GATEWAY_CHOICES,
        verbose_name="درگاه",
        help_text="درگاه بانکی که پرداخت از طریق آن انجام شده است.",
    )
    amount = models.PositiveIntegerField(
        verbose_name="مبلغ (تومان)",
        help_text="مبلغ پرداخت به تومان.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_INITIATED,
        verbose_name="وضعیت",
        help_text=(
            "ایجاد شده: پرداخت ساخته شده ولی کاربر هنوز به درگاه نرفته · "
            "در حال پرداخت: کاربر به درگاه رفته و نتیجه هنوز مشخص نیست (سایت هر ۵ دقیقه خودکار از درگاه استعلام می‌گیرد) · "
            "موفق: پول دریافت و تأیید شده · ناموفق: پرداخت انجام نشده · "
            "انصراف کاربر: کاربر پرداخت را لغو کرده است."
        ),
    )

    authority = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        unique=True,
        verbose_name="شناسه‌ی درگاه (Authority)",
        help_text="شناسه‌ای که درگاه برای این تراکنش ساخته است؛ برای پیگیری با پشتیبانی درگاه.",
    )
    ref_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="شماره‌ی پیگیری",
        help_text="شماره‌ی پیگیری بانکی پرداخت موفق؛ برای پیگیری و بازپرداخت.",
    )
    card_pan = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="کارت (ماسک‌شده)",
        help_text="چند رقم از شماره‌ی کارت پرداخت‌کننده (بقیه‌ی ارقام پنهان است).",
    )
    gateway_message = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="پیام درگاه",
        help_text="آخرین پیامی که درگاه درباره‌ی این تراکنش برگردانده است.",
    )

    needs_review = models.BooleanField(
        default=False,
        verbose_name="نیاز به بررسی",
        help_text=(
            "پرداخت موفق بوده ولی نوبت یا سفارش دیگر قابل تأیید نبود (مثلاً مهلت آن تمام شده بود). باید وجه را به کاربر برگردانید و سپس این تیک را بردارید."
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد",
        help_text="زمان شروع پرداخت.",
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان تأیید",
        help_text="زمان تأیید نهایی پرداخت توسط درگاه.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "پرداخت"
        verbose_name_plural = "پرداخت‌ها"
        constraints = [
            models.CheckConstraint(
                condition=(Q(appointment__isnull=False, order__isnull=True) | Q(appointment__isnull=True, order__isnull=False)),
                name="payment_exactly_one_target",
            ),
        ]

    def __str__(self):
        return f"{self.get_gateway_display()} - {self.amount:,} - {self.get_status_display()}"

    @property
    def amount_rial(self):
        return self.amount * 10

    @property
    def target(self):
        return self.appointment or self.order

    @property
    def description(self):
        if self.appointment_id:
            return f"نوبت شماره {self.appointment_id}"
        return f"سفارش شماره {self.order_id}"
