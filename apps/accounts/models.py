from django.db import models

from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    phone_number=models.CharField(
        max_length=11,
        unique=True,
        null=True,
        blank=True,
        verbose_name="شماره موبایل",
        help_text=(
            "شماره‌ی موبایل کاربر که نام کاربری او نیز هست؛ ۱۱ رقم و با ۰۹ شروع شود. پیامک‌های سایت به این شماره ارسال می‌شود."
        ),
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

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="shipping_address",
        verbose_name="کاربر",
        help_text="حسابی که این نشانی متعلق به آن است.",
    )
    recipient_name = models.CharField(
        max_length=100,
        verbose_name="نام گیرنده",
        help_text="نام و نام خانوادگی کسی که بسته را تحویل می‌گیرد.",
    )
    recipient_phone = models.CharField(
        max_length=11,
        verbose_name="موبایل گیرنده",
        help_text="شماره‌ی موبایل گیرنده برای هماهنگی ارسال؛ ۱۱ رقم و با ۰۹ شروع شود. مثال: 09121234567",
    )
    province = models.CharField(
        max_length=50,
        verbose_name="استان",
        help_text="استان مقصد ارسال.",
    )
    city = models.CharField(
        max_length=50,
        verbose_name="شهر",
        help_text="شهر مقصد ارسال.",
    )
    address = models.TextField(
        verbose_name="نشانی",
        help_text="نشانی کامل پستی شامل خیابان، کوچه، پلاک و واحد.",
    )
    postal_code = models.CharField(
        max_length=10,
        verbose_name="کد پستی",
        help_text="کد پستی ۱۰ رقمی، بدون فاصله و خط تیره.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخرین تغییر",
        help_text="زمان آخرین تغییر این نشانی؛ به‌طور خودکار ثبت می‌شود.",
    )

    class Meta:
        verbose_name = "نشانی پیش‌فرض"
        verbose_name_plural = "نشانی‌های پیش‌فرض"

    def __str__(self):
        return f"{self.recipient_name} - {self.city}"

    FIELDS = ("recipient_name", "recipient_phone", "province", "city", "address", "postal_code")

    def as_initial(self):
        return {name: getattr(self, name) for name in self.FIELDS}
