from django.conf import settings
from django.db import models
from utils.fields import WebPImageField
from jalali_date import date2jalali
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

    availability = models.ForeignKey(
        DoctorAvailability,
        on_delete=models.PROTECT,
        related_name="appointments",
        blank=True,
        limit_choices_to={"is_active": True},
    )

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments",
        blank=True,
    )

    date = models.DateField(blank=True,)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True,blank=True,)
    
    payment_deadline = models.DateTimeField(
    null=True,
    blank=True,
)

    class Meta:
        ordering = ["-date", "-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["availability", "date"],
                name="unique_appointment_slot"
            )
        ]

    def __str__(self):
        jalali_date = date2jalali(self.date)
        return (
            f"{self.patient} - "
            f"{self.availability.doctor} - "
            f"{jalali_date.strftime('%Y/%m/%d %H:%M')} - "
            f"{self.availability.time}"
        )