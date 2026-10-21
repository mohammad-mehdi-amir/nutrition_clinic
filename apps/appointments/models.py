from django.conf import settings
from django.db import models
from utils.fields import WebPImageField
from jalali_date import date2jalali

# وضعیت‌هایی که اسلات را اشغال می‌کنند
ACTIVE_APPOINTMENT_STATUSES = ["pending", "confirmed", "completed"]


class Doctor(models.Model):
    name = models.CharField(max_length=100, verbose_name="نام")
    specialty = models.CharField(max_length=100, verbose_name="تخصص")
    bio = models.TextField(blank=True, verbose_name="معرفی")
    image = WebPImageField(
        upload_to="doctors/",
        blank=True,
        null=True,
        verbose_name="تصویر",
    )
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    visit_fee = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="هزینه‌ی ویزیت (تومان)",
        help_text="خالی یعنی هزینه‌ی پیش‌فرض تنظیمات سایت؛ ۰ یعنی رایگان.",
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
    )

    day_of_week = models.PositiveSmallIntegerField(
        choices=DAYS_OF_WEEK,
        verbose_name="روز هفته",
    )

    time = models.TimeField(verbose_name="ساعت")

    is_active = models.BooleanField(default=True, verbose_name="فعال")

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
    ]

    ACTIVE_STATUSES = ACTIVE_APPOINTMENT_STATUSES

    PAYMENT_NOT_REQUIRED = "not_required"
    PAYMENT_UNPAID = "unpaid"
    PAYMENT_PAID = "paid"
    PAYMENT_REFUND_REQUESTED = "refund_requested"
    PAYMENT_REFUNDED = "refunded"
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_NOT_REQUIRED, "رایگان"),
        (PAYMENT_UNPAID, "پرداخت‌نشده"),
        (PAYMENT_PAID, "پرداخت‌شده"),
        (PAYMENT_REFUND_REQUESTED, "در انتظار بازپرداخت"),
        (PAYMENT_REFUNDED, "بازپرداخت‌شده"),
    ]

    availability = models.ForeignKey(
        DoctorAvailability,
        on_delete=models.PROTECT,
        related_name="appointments",
        limit_choices_to={"is_active": True},
        verbose_name="شیفت",
    )

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name="بیمار",
    )

    date = models.DateField(verbose_name="تاریخ")

    # کپی ساعت شیفت برای قید یکتایی «یک بیمار، یک نوبت در هر ساعت»
    start_time = models.TimeField(verbose_name="ساعت")

    fee = models.PositiveIntegerField(default=0, verbose_name="هزینه (تومان)")

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_UNPAID,
        verbose_name="وضعیت پرداخت",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        blank=True,
        verbose_name="وضعیت",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ثبت")
    
    payment_deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="مهلت پرداخت",
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

    def save(self, *args, **kwargs):
        if self.start_time is None and self.availability_id:
            self.start_time = self.availability.time
        super().save(*args, **kwargs)