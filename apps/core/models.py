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

    def __str__(self):
        return self.clinic_name