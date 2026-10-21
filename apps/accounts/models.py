from django.db import models

from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    phone_number=models.CharField(
        max_length=11,
        unique=True,
        null=True,
        blank=True,
        verbose_name="شماره موبایل",
    )

    class Meta(AbstractUser.Meta):
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"

class PasswordResetCode(models.Model):
    """کد یک‌بارمصرف بازیابی رمز؛ فقط هش کد ذخیره می‌شود."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_codes")
    phone_number = models.CharField(max_length=11, db_index=True)
    code_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "کد بازیابی رمز"
        verbose_name_plural = "کدهای بازیابی رمز"

    def __str__(self):
        return f"{self.phone_number} - {self.created_at:%Y-%m-%d %H:%M}"


class ShippingAddress(models.Model):
    """نشانی پیش‌فرض کاربر برای پیش‌پر کردن فرم تسویه‌حساب."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="shipping_address", verbose_name="کاربر")
    recipient_name = models.CharField(max_length=100, verbose_name="نام گیرنده")
    recipient_phone = models.CharField(max_length=11, verbose_name="موبایل گیرنده")
    province = models.CharField(max_length=50, verbose_name="استان")
    city = models.CharField(max_length=50, verbose_name="شهر")
    address = models.TextField(verbose_name="نشانی")
    postal_code = models.CharField(max_length=10, verbose_name="کد پستی")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین تغییر")

    class Meta:
        verbose_name = "نشانی پیش‌فرض"
        verbose_name_plural = "نشانی‌های پیش‌فرض"

    def __str__(self):
        return f"{self.recipient_name} - {self.city}"

    FIELDS = ("recipient_name", "recipient_phone", "province", "city", "address", "postal_code")

    def as_initial(self):
        return {name: getattr(self, name) for name in self.FIELDS}
