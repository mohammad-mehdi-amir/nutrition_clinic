from django.conf import settings
from django.db import models
from utils.fields import WebPImageField

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

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="appointments"
    )

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appointments"
    )

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "date", "start_time"],
                name="unique_doctor_appointment"
            )
        ]

    def __str__(self):
        return f"{self.doctor} - {self.patient} - {self.date}"