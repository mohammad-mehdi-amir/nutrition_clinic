import uuid

from django.conf import settings
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from utils.validators import validate_pdf

from .storage import patient_diet_upload_to, private_storage, template_upload_to

PDF_VALIDATORS = [FileExtensionValidator(["pdf"]), validate_pdf]

GOAL_CHOICES = [
    ("lose", "کاهش وزن"),
    ("maintain", "تثبیت وزن"),
    ("gain", "افزایش وزن"),
    ("muscle", "افزایش حجم عضلانی / ورزشی"),
    ("medical", "رژیم درمانی (بیماری خاص)"),
]


class HealthProfile(models.Model):
    """اطلاعات سلامت بیمار؛ تکمیل آن اختیاری است و همه‌ی فیلدها خالی‌پذیرند."""

    SEX_FEMALE = "female"
    SEX_MALE = "male"
    SEX_CHOICES = [(SEX_FEMALE, "زن"), (SEX_MALE, "مرد")]

    # ضریب فعالیت برای محاسبه‌ی کالری روزانه (TDEE)
    ACTIVITY_FACTORS = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    }
    ACTIVITY_CHOICES = [
        ("sedentary", "کم‌تحرک (کار پشت میز، بدون ورزش)"),
        ("light", "فعالیت سبک (ورزش ۱ تا ۳ روز در هفته)"),
        ("moderate", "فعالیت متوسط (ورزش ۳ تا ۵ روز در هفته)"),
        ("active", "فعال (ورزش ۶ تا ۷ روز در هفته)"),
        ("very_active", "خیلی فعال (ورزش سنگین یا کار بدنی)"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="health_profile",
        verbose_name="کاربر",
    )
    sex = models.CharField(max_length=10, choices=SEX_CHOICES, blank=True, verbose_name="جنسیت")
    birth_date = models.DateField(null=True, blank=True, verbose_name="تاریخ تولد")
    height_cm = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(100), MaxValueValidator(250)],
        verbose_name="قد (سانتی‌متر)",
    )
    activity_level = models.CharField(
        max_length=20, choices=ACTIVITY_CHOICES, blank=True, verbose_name="میزان فعالیت بدنی"
    )
    goal = models.CharField(max_length=20, choices=GOAL_CHOICES, blank=True, verbose_name="هدف")
    target_weight_kg = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(30), MaxValueValidator(300)],
        verbose_name="وزن هدف (کیلوگرم)",
    )
    medical_conditions = models.TextField(max_length=1000, blank=True, verbose_name="بیماری‌ها و سابقه‌ی پزشکی")
    medications = models.TextField(max_length=1000, blank=True, verbose_name="داروها و مکمل‌های مصرفی")
    allergies = models.TextField(max_length=1000, blank=True, verbose_name="حساسیت و عدم تحمل غذایی")
    food_preferences = models.TextField(
        max_length=1000, blank=True, verbose_name="ترجیحات غذایی (علاقه، عدم علاقه، گیاه‌خواری و...)"
    )
    consent_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان رضایت پردازش اطلاعات سلامت")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین تغییر")

    class Meta:
        verbose_name = "پروفایل سلامت"
        verbose_name_plural = "پروفایل‌های سلامت"

    def __str__(self):
        return f"پروفایل سلامت {self.user}"

    @property
    def age(self):
        if not self.birth_date:
            return None
        today = timezone.localdate()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )


class BodyMeasurement(models.Model):
    """سابقه‌ی وزن و دور کمر؛ آخرین ردیف، وزن فعلی بیمار است."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="body_measurements",
        verbose_name="کاربر",
    )
    weight_kg = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        validators=[MinValueValidator(20), MaxValueValidator(350)],
        verbose_name="وزن (کیلوگرم)",
    )
    waist_cm = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(30), MaxValueValidator(250)],
        verbose_name="دور کمر (سانتی‌متر)",
    )
    recorded_at = models.DateTimeField(default=timezone.now, verbose_name="زمان ثبت")

    class Meta:
        ordering = ["-recorded_at", "-id"]
        indexes = [models.Index(fields=["user", "recorded_at"])]
        verbose_name = "اندازه‌گیری بدن"
        verbose_name_plural = "سابقه‌ی وزن"

    def __str__(self):
        return f"{self.weight_kg} kg"


class DietTemplate(models.Model):
    """کتابخانه‌ی رژیم‌های آماده (PDF) که کارشناس می‌تواند برای بیماران بفرستد."""

    title = models.CharField(
        max_length=150,
        verbose_name="عنوان",
        help_text=(
            "نامی که با آن رژیم را در فهرست پیدا می‌کنید؛ اگر هنگام ارسال عنوان دیگری وارد نشود، بیمار نیز همین عنوان را می‌بیند. مثال: رژیم کاهش وزن ۱۵۰۰ کالری"
        ),
    )
    goal = models.CharField(
        max_length=20,
        choices=GOAL_CHOICES,
        blank=True,
        verbose_name="هدف",
        help_text="هدف این رژیم؛ برای پیدا کردن سریع‌تر رژیم مناسب.",
    )
    calories = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="کالری روزانه",
        help_text="کالری روزانه‌ی این رژیم (اختیاری). مثال: 1500",
    )
    description = models.TextField(
        blank=True,
        verbose_name="توضیح (فقط برای کارشناس)",
        help_text="توضیح برای همکاران (مثلاً مناسب چه کسانی است)؛ بیمار آن را نمی‌بیند.",
    )
    file = models.FileField(
        storage=private_storage,
        upload_to=template_upload_to,
        validators=PDF_VALIDATORS,
        verbose_name="فایل PDF",
        help_text="فایل PDF رژیم، حداکثر ۱۰ مگابایت. هنگام ارسال برای بیمار یک نسخه از آن کپی می‌شود.",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
        help_text=(
            "اگر غیرفعال شود، این رژیم در فهرست انتخاب هنگام ارسال نمایش داده نمی‌شود. رژیم‌هایی که قبلاً برای بیماران ارسال شده‌اند تغییری نمی‌کنند."
        ),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="ایجادکننده",
        help_text="کارمندی که این رژیم را اضافه کرده است؛ به‌طور خودکار ثبت می‌شود.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد",
        help_text="زمان افزودن؛ به‌طور خودکار ثبت می‌شود.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخرین تغییر",
        help_text="زمان آخرین تغییر؛ به‌طور خودکار ثبت می‌شود.",
    )

    class Meta:
        ordering = ["title"]
        verbose_name = "رژیم آماده"
        verbose_name_plural = "رژیم‌های آماده"

    def __str__(self):
        return f"{self.title} ({self.calories} کالری)" if self.calories else self.title


class DietRequest(models.Model):
    """درخواست رژیم؛ به ازای هر پکیج پرداخت‌شده یکی به‌طور خودکار ساخته می‌شود."""

    STATUS_PENDING = "pending"
    STATUS_DELIVERED = "delivered"
    STATUS_CHOICES = [
        (STATUS_PENDING, "در انتظار رژیم"),
        (STATUS_DELIVERED, "تحویل‌شده"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="diet_requests",
        verbose_name="بیمار",
        help_text="بیماری که پکیج را خریده و منتظر رژیم است.",
    )
    order_item = models.OneToOneField(
        "shop.OrderItem",
        on_delete=models.PROTECT,
        related_name="diet_request",
        verbose_name="قلم سفارش",
        help_text="قلم سفارشی که این درخواست از آن ساخته شده است.",
    )
    package_name = models.CharField(
        max_length=150,
        verbose_name="پکیج",
        help_text="نام پکیجی که بیمار خریده است (در لحظه‌ی خرید).",
    )
    doctor = models.ForeignKey(
        "appointments.Doctor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diet_requests",
        verbose_name="کارشناس مسئول",
        help_text="کارشناسی که مسئول نوشتن رژیم این بیمار است (اختیاری).",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="وضعیت",
        help_text=(
            "در انتظار رژیم: هنوز فایلی برای بیمار ارسال نشده · "
            "تحویل‌شده: حداقل یک فایل رژیم در پنل بیمار قرار گرفته است. این وضعیت با ارسال رژیم خودکار تغییر می‌کند."
        ),
    )
    staff_note = models.TextField(
        blank=True,
        verbose_name="یادداشت داخلی (بیمار نمی‌بیند)",
        help_text="یادداشت داخلی برای همکاران؛ بیمار آن را نمی‌بیند.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ثبت",
        help_text="زمان ثبت درخواست (زمان پرداخت پکیج).",
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان تحویل",
        help_text="زمان ارسال اولین رژیم برای بیمار؛ به‌طور خودکار ثبت می‌شود.",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]
        verbose_name = "درخواست رژیم"
        verbose_name_plural = "درخواست‌های رژیم"

    def __str__(self):
        return f"{self.package_name} — {self.user}"


class PatientDiet(models.Model):
    """PDF رژیمی که به بیمار تحویل داده شده؛ برای همیشه در پنل او قابل دانلود است."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(
        DietRequest,
        on_delete=models.CASCADE,
        related_name="diets",
        verbose_name="درخواست",
        help_text="درخواست رژیمی که این فایل برای آن ارسال شده است.",
    )
    title = models.CharField(
        max_length=150,
        verbose_name="عنوان",
        help_text=(
            "عنوانی که بیمار در «رژیم‌های من» می‌بیند. اگر رژیم آماده انتخاب کنید و خالی بگذارید، عنوان رژیم آماده استفاده می‌شود."
        ),
    )
    # snapshot: نسخه‌ی مستقل از فایل؛ تغییر یا حذف رژیم آماده روی آن اثر ندارد
    file = models.FileField(
        storage=private_storage,
        upload_to=patient_diet_upload_to,
        validators=PDF_VALIDATORS,
        verbose_name="فایل PDF",
        help_text=(
            "یک فایل PDF جدید آپلود کنید (حداکثر ۱۰ مگابایت)، یا به‌جای آن از «انتخاب از رژیم‌های آماده» استفاده کنید؛ فقط یکی از این دو."
        ),
    )
    template = models.ForeignKey(
        DietTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
        verbose_name="از رژیم آماده",
        help_text="یکی از رژیم‌های آماده را انتخاب کنید، یا به‌جای آن فایل PDF جدید آپلود کنید؛ فقط یکی از این دو.",
    )
    note = models.TextField(
        max_length=2000,
        blank=True,
        verbose_name="پیام کارشناس به بیمار",
        help_text="پیامی که بیمار کنار فایل رژیم می‌بیند (اختیاری). مثال: روزانه ۸ لیوان آب بنوشید.",
    )
    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="تحویل‌دهنده",
        help_text="کارمندی که رژیم را ارسال کرده است؛ به‌طور خودکار ثبت می‌شود.",
    )
    delivered_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="زمان تحویل",
        help_text="زمان ارسال رژیم؛ به‌طور خودکار ثبت می‌شود.",
    )

    class Meta:
        ordering = ["-delivered_at"]
        verbose_name = "رژیم تحویل‌شده"
        verbose_name_plural = "رژیم‌های تحویل‌شده"

    def __str__(self):
        return self.title
