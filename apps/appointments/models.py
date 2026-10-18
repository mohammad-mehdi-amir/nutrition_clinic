from django.conf import settings
from django.db import models
from utils.fields import WebPImageField
from jalali_date import date2jalali

# وضعیت‌هایی که اسلات را اشغال می‌کنند
ACTIVE_APPOINTMENT_STATUSES = ["pending", "confirmed", "completed"]


class Doctor(models.Model):
    name = models.CharField(max_length=100)
    specialty = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    image = WebPImageField(
        upload_to="doctors/",
        blank=True,
        null=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "پزشک"
        verbose_name_plural = "پزشکان"

    def __str__(self):
        return self.name



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
        related_name="availabilities"
    )

    day_of_week = models.PositiveSmallIntegerField(
        choices=DAYS_OF_WEEK
    )

    time = models.TimeField()

    is_active = models.BooleanField(default=True)

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

    availability = models.ForeignKey(
        DoctorAvailability,
        on_delete=models.PROTECT,
        related_name="appointments",
        limit_choices_to={"is_active": True},
    )

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments",
    )

    date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    
    payment_deadline = models.DateTimeField(
        null=True,
        blank=True,
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
            )
        ]

    def __str__(self):
        jalali_date = date2jalali(self.date)
        return (
            f"{self.patient} - "
            f"{self.availability.doctor} - "
            f"{jalali_date.strftime('%Y/%m/%d')} - "
            f"{self.availability.time}"
        )