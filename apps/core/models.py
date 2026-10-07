from django.db import models

# Create your models here.
from django.db import models


class SiteSettings(models.Model):
    clinic_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    open_at= models.TimeField(blank=True)
    close_at= models.TimeField(blank=True)
    payment_timeout_minutes = models.PositiveIntegerField(default=10,verbose_name="مهلت پرداخت نوبت (دقیقه)",)
    

    class Meta:

        verbose_name = "تنظیمات سایت"

        verbose_name_plural = "تنظیمات سایت"

    def save(self, *args, **kwargs):

        self.pk = 1

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):

        pass

    def __str__(self):

        return "تنظیمات سایت"