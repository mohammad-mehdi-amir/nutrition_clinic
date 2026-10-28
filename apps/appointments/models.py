import math

from django.conf import settings
from django.db import models
from utils.fields import WebPImageField
from jalali_date import date2jalali

# وضعیت‌هایی که اسلات را اشغال می‌کنند
ACTIVE_APPOINTMENT_STATUSES = ["pending", "confirmed", "completed"]


def calculate_deposit(fee, percent):
    """بیعانه = درصدی از هزینه‌ی ویزیت، گرد به بالا تا هزار تومان و حداکثر برابر هزینه."""
    if not fee:
        return 0
    deposit = math.ceil(fee * percent / 100 / 1000) * 1000
    return min(deposit, fee)


class Doctor(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name="نام",
        help_text="نام کامل پزشک یا کارشناس، همان‌طور که در سایت نمایش داده می‌شود. مثال: دکتر مرجان فدایی",
    )
    specialty = models.CharField(
        max_length=100,
        verbose_name="تخصص",
        help_text="عنوان تخصص که زیر نام پزشک نمایش داده می‌شود. مثال: کارشناس ارشد تغذیه و رژیم‌درمانی",
    )
    bio = models.TextField(
        blank=True,
        verbose_name="معرفی",
        help_text="معرفی کوتاه پزشک (چند جمله) که روی کارت پزشک در سایت نمایش داده می‌شود.",
    )
    image = WebPImageField(
        upload_to="doctors/",
        blank=True,
        null=True,
        verbose_name="تصویر",
        help_text=(
            "عکس پرسنلی پزشک؛ عمودی و حدود ۶۰۰×۷۵۰ پیکسل، حداکثر ۵ مگابایت. عکس بدون واترمارک و با پس‌زمینه‌ی ساده توصیه می‌شود."
        ),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
        help_text="اگر غیرفعال شود، پزشک از سایت و فرم رزرو پنهان می‌شود ولی نوبت‌های قبلی او حذف نمی‌شوند.",
    )

    visit_fee = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="هزینه‌ی ویزیت (تومان)",
        help_text=(
            "هزینه‌ی ویزیت این پزشک به تومان. اگر خالی بماند، «هزینه‌ی پیش‌فرض ویزیت» از تنظیمات سایت استفاده می‌شود؛ عدد ۰ یعنی ویزیت رایگان."
        ),
    )

    class Meta:
        verbose_name = "پزشک"
        verbose_name_plural = "پزشکان"

    def __str__(self):
        return self.name

    def get_visit_fee(self):
        """هزینه‌ی ویزیت این پزشک یا مقدار پیش‌فرض تنظیمات سایت (تومان)."""
        if self.visit_fee is not None:
            return self.visit_fee

        from apps.core.models import SiteSettings
        return SiteSettings.load().default_visit_fee

    def get_deposit(self):
        """مبلغی که هنگام رزرو آنلاین پرداخت می‌شود (بیعانه)."""
        from apps.core.models import SiteSettings
        return calculate_deposit(self.get_visit_fee(), SiteSettings.load().deposit_percent)



class DoctorAvailability(models.Model):
    DAYS_OF_WEEK = [
        (0, "شنبه"),
        (1, "یکشنبه"),
        (2, "دوشنبه"),
        (3, "سه‌شنبه"),
        (4, "چهارشنبه"),
        (5, "پنجشنبه"),
        (6, "جمعه"),
    ]

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="availabilities",
        verbose_name="پزشک",
        help_text="پزشکی که این شیفت متعلق به اوست.",
    )

    day_of_week = models.PositiveSmallIntegerField(
        choices=DAYS_OF_WEEK,
        verbose_name="روز هفته",
        help_text="روزی از هفته که این شیفت هر هفته تکرار می‌شود.",
    )

    time = models.TimeField(
        verbose_name="ساعت",
        help_text="ساعت شروع نوبت. برای ساخت سریع همه‌ی شیفت‌ها از لینک «برنامه‌ی هفتگی» در فهرست پزشکان استفاده کنید.",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
        help_text="اگر غیرفعال شود، این ساعت دیگر برای رزرو نمایش داده نمی‌شود؛ نوبت‌های قبلی آن باقی می‌مانند.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "day_of_week", "time"],
                name="unique_doctor_availability"
            )
        ]
        ordering = ["day_of_week", "time"]
        verbose_name = "شیفت پزشک"
        verbose_name_plural = "شیفت‌های پزشکان"

    @staticmethod
    def day_of_week_for(date):
        """تبدیل weekday پایتون (دوشنبه=0) به اندیس DAYS_OF_WEEK (شنبه=0)."""
        return (date.weekday() + 2) % 7

    def __str__(self):
        return (
            f"{self.doctor.name} - "
            f"{self.get_day_of_week_display()} - "
            f"{self.time}"
        )


class Appointment(models.Model):
    STATUS_CHOICES = [
        ("pending", "در انتظار پرداخت"),
        ("confirmed", "تایید شده"),
        ("cancelled", "لغو شده"),
        ("completed", "انجام شده"),
        ("no_show", "عدم حضور"),
    ]

    ACTIVE_STATUSES = ACTIVE_APPOINTMENT_STATUSES

    PAYMENT_NOT_REQUIRED = "not_required"
    PAYMENT_UNPAID = "unpaid"
    PAYMENT_DEPOSIT_PAID = "deposit_paid"
    PAYMENT_PAID = "paid"
    PAYMENT_REFUND_REQUESTED = "refund_requested"
    PAYMENT_REFUNDED = "refunded"
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_NOT_REQUIRED, "رایگان"),
        (PAYMENT_UNPAID, "پرداخت‌نشده"),
        (PAYMENT_DEPOSIT_PAID, "بیعانه پرداخت‌شده"),
        (PAYMENT_PAID, "پرداخت‌شده (کامل)"),
        (PAYMENT_REFUND_REQUESTED, "در انتظار بازپرداخت"),
        (PAYMENT_REFUNDED, "بازپرداخت‌شده"),
    ]

    availability = models.ForeignKey(
        DoctorAvailability,
        on_delete=models.PROTECT,
        related_name="appointments",
        limit_choices_to={"is_active": True},
        verbose_name="شیفت",
        help_text="شیفت هفتگی پزشک (روز و ساعت) که این نوبت در آن گرفته شده است.",
    )

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name="بیمار",
        help_text="حساب کاربری بیماری که نوبت را گرفته است.",
    )

    date = models.DateField(
        verbose_name="تاریخ",
        help_text="تاریخ مراجعه‌ی بیمار.",
    )

    # کپی ساعت شیفت برای قید یکتایی «یک بیمار، یک نوبت در هر ساعت»
    start_time = models.TimeField(
        verbose_name="ساعت",
        help_text="ساعت شروع نوبت؛ از شیفت پزشک برداشته می‌شود.",
    )

    fee = models.PositiveIntegerField(
        default=0,
        verbose_name="هزینه‌ی ویزیت (تومان)",
        help_text="کل هزینه‌ی ویزیت در لحظه‌ی رزرو. تغییر بعدی قیمت پزشک روی این نوبت اثری ندارد.",
    )
    # snapshot بیعانه در لحظه‌ی رزرو؛ همین مبلغ آنلاین پرداخت می‌شود
    deposit = models.PositiveIntegerField(
        default=0,
        verbose_name="بیعانه (تومان)",
        help_text=(
            "مبلغی که بیمار هنگام رزرو به‌صورت آنلاین پرداخت می‌کند (طبق «درصد بیعانه» در تنظیمات سایت). مابقی در مطب دریافت می‌شود."
        ),
    )
    # مبلغ واقعاً دریافت‌شده (آنلاین یا در مطب)؛ مبنای بازپرداخت
    paid_amount = models.PositiveIntegerField(
        default=0,
        verbose_name="مبلغ دریافت‌شده (تومان)",
        help_text=(
            "مجموع مبلغی که واقعاً از بیمار دریافت شده است (آنلاین یا در مطب). در صورت لغو، همین مبلغ بازپرداخت می‌شود."
        ),
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_UNPAID,
        verbose_name="وضعیت پرداخت",
        help_text=(
            "رایگان: ویزیت هزینه ندارد · پرداخت‌نشده: هنوز پولی پرداخت نشده · "
            "بیعانه پرداخت‌شده: بیعانه آنلاین پرداخت شده و مابقی در مطب گرفته می‌شود · "
            "پرداخت‌شده (کامل): کل هزینه دریافت شده · "
            "در انتظار بازپرداخت: نوبت لغو شده و باید وجه به بیمار برگردانده شود · "
            "بازپرداخت‌شده: وجه به بیمار برگردانده شده است. این وضعیت فقط با دکمه‌های «عملیات» در فهرست نوبت‌ها تغییر می‌کند."
        ),
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        blank=True,
        verbose_name="وضعیت",
        help_text=(
            "در انتظار پرداخت: نوبت موقتاً رزرو شده و بیمار باید تا پایان مهلت پرداخت کند، وگرنه خودکار لغو می‌شود · "
            "تأیید شده: نوبت قطعی است · لغو شده: نوبت لغو شده و آن ساعت دوباره آزاد است · "
            "انجام شده: بیمار مراجعه کرده است · "
            "عدم حضور: بیمار نیامده و بیعانه بازگردانده نمی‌شود. این وضعیت فقط با دکمه‌های «عملیات» در فهرست نوبت‌ها تغییر می‌کند."
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ثبت",
        help_text="زمان ثبت نوبت در سایت؛ به‌طور خودکار ثبت می‌شود.",
    )
    
    payment_deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="مهلت پرداخت",
        help_text="اگر تا این زمان پرداخت انجام نشود، نوبت خودکار لغو و ساعت آن آزاد می‌شود.",
    )

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "نوبت"
        verbose_name_plural = "نوبت‌ها"

        constraints = [
            models.UniqueConstraint(
                fields=["availability", "date"],
                condition=models.Q(status__in=ACTIVE_APPOINTMENT_STATUSES),
                name="unique_active_appointment_slot",
            ),
            models.UniqueConstraint(
                fields=["patient", "date", "start_time"],
                condition=models.Q(status__in=ACTIVE_APPOINTMENT_STATUSES),
                name="unique_active_patient_time",
            ),
        ]

    def __str__(self):
        jalali_date = date2jalali(self.date)
        return (
            f"{self.patient} - "
            f"{self.availability.doctor} - "
            f"{jalali_date.strftime('%Y/%m/%d')} - "
            f"{self.start_time:%H:%M}"
        )

    @property
    def remaining(self):
        """مبلغی که بیمار باید در مطب بپردازد."""
        return max(self.fee - self.paid_amount, 0)

    @property
    def has_deposit_only(self):
        """بیعانه کمتر از کل هزینه است (مابقی در مطب پرداخت می‌شود)."""
        return 0 < self.deposit < self.fee

    def save(self, *args, **kwargs):
        if self.start_time is None and self.availability_id:
            self.start_time = self.availability.time
        super().save(*args, **kwargs)