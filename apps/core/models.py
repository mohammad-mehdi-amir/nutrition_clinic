from django.db import models
from django.urls import reverse

from utils.fields import WebPImageField
from utils.validators import iran_mobile_validator, validate_image_size


class SiteSettings(models.Model):
    clinic_name = models.CharField(max_length=100, verbose_name="نام کلینیک")
    tagline = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="معرفی کوتاه",
        help_text="در فوتر و توضیحات متای صفحات استفاده می‌شود.",
    )
    logo = models.ImageField(
        upload_to="site/",
        blank=True,
        validators=[validate_image_size],
        verbose_name="لوگو",
        help_text="در صورت خالی بودن، نام کلینیک نمایش داده می‌شود.",
    )
    phone = models.CharField(max_length=20, verbose_name="تلفن")
    email = models.EmailField(blank=True, verbose_name="ایمیل")
    address = models.TextField(blank=True, verbose_name="نشانی")
    open_at = models.TimeField(null=True, blank=True, verbose_name="ساعت شروع کار")
    close_at = models.TimeField(null=True, blank=True, verbose_name="ساعت پایان کار")
    working_days = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="روزهای کاری",
        help_text="مثال: شنبه تا چهارشنبه",
    )
    map_embed_url = models.URLField(
        max_length=1000,
        blank=True,
        verbose_name="آدرس embed نقشه",
        help_text="مقدار src کد embed نقشه‌ی گوگل یا نشان.",
    )
    instagram_url = models.URLField(blank=True, verbose_name="اینستاگرام")
    telegram_url = models.URLField(blank=True, verbose_name="تلگرام")
    whatsapp_url = models.URLField(blank=True, verbose_name="واتس‌اپ")
    about_text = models.TextField(blank=True, verbose_name="متن درباره ما")
    terms_text = models.TextField(blank=True, verbose_name="قوانین و مقررات")
    privacy_text = models.TextField(blank=True, verbose_name="حریم خصوصی")
    payment_timeout_minutes = models.PositiveIntegerField(default=10,verbose_name="مهلت پرداخت نوبت (دقیقه)",)
    default_visit_fee = models.PositiveIntegerField(
        default=0,
        verbose_name="هزینه‌ی پیش‌فرض ویزیت (تومان)",
        help_text="برای پزشکانی که هزینه‌ی جداگانه ندارند. ۰ یعنی رایگان.",
    )
    cancellation_deadline_hours = models.PositiveIntegerField(
        default=12,
        verbose_name="حداقل فاصله‌ی لغو تا نوبت (ساعت)",
        help_text="بیمار تا این تعداد ساعت قبل از شروع نوبت می‌تواند آن را لغو کند.",
    )

    # تصاویر سایت — در صورت خالی بودن، تصویر پیش‌فرض قالب نمایش داده می‌شود
    hero_image = WebPImageField(
        upload_to="site/",
        blank=True,
        verbose_name="تصویر اصلی صفحه‌ی خانه",
        help_text="PNG با پس‌زمینه‌ی شفاف، حدود ۱۰۴۰×۱۲۲۵ پیکسل.",
    )
    about_image = WebPImageField(
        upload_to="site/",
        blank=True,
        verbose_name="تصویر بخش درباره ما",
        help_text="مربع، حدود ۷۸۰×۷۸۰ پیکسل (به‌صورت دایره نمایش داده می‌شود).",
    )
    page_banner_image = WebPImageField(
        upload_to="site/",
        blank=True,
        verbose_name="تصویر بنر صفحات داخلی",
        help_text="PNG با پس‌زمینه‌ی شفاف، حدود ۵۹۵×۳۹۵ پیکسل.",
    )
    faq_image = WebPImageField(
        upload_to="site/",
        blank=True,
        verbose_name="تصویر بخش سؤالات متداول",
        help_text="حدود ۶۰۰×۶۸۰ پیکسل.",
    )
    bmi_image = WebPImageField(
        upload_to="site/",
        blank=True,
        verbose_name="تصویر بخش محاسبه‌ی BMI",
        help_text="افقی، حدود ۱۱۷۰×۷۰۰ پیکسل.",
    )
    cta_image = WebPImageField(
        upload_to="site/",
        blank=True,
        verbose_name="تصویر بخش دعوت به رزرو",
        help_text="PNG با پس‌زمینه‌ی شفاف، حدود ۸۰۰×۸۰۰ پیکسل.",
    )
    favicon = models.ImageField(
        upload_to="site/",
        blank=True,
        validators=[validate_image_size],
        verbose_name="آیکون سایت (favicon)",
        help_text="PNG مربع، حداقل ۶۴×۶۴ پیکسل.",
    )

    # فروشگاه (مبالغ به تومان)
    shipping_cost = models.PositiveIntegerField(default=0, verbose_name="هزینه‌ی ارسال (تومان)")
    free_shipping_threshold = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="حداقل خرید برای ارسال رایگان (تومان)",
        help_text="خالی یعنی ارسال رایگان نداریم.",
    )
    order_payment_timeout_minutes = models.PositiveIntegerField(
        default=30,
        verbose_name="مهلت پرداخت سفارش (دقیقه)",
        help_text="پس از این مدت سفارش پرداخت‌نشده لغو و موجودی آزاد می‌شود.",
    )


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

    @classmethod
    def load(cls):
        """رکورد تنظیمات یا یک نمونه‌ی ذخیره‌نشده با مقادیر پیش‌فرض."""
        return cls.objects.first() or cls(clinic_name="کلینیک تغذیه")


class Service(models.Model):
    title = models.CharField(max_length=150, verbose_name="عنوان")
    slug = models.SlugField(
        max_length=160,
        unique=True,
        allow_unicode=True,
        verbose_name="نامک (آدرس)",
    )
    summary = models.CharField(max_length=255, verbose_name="خلاصه")
    body = models.TextField(blank=True, verbose_name="توضیحات کامل")
    image = WebPImageField(upload_to="services/", blank=True, verbose_name="تصویر")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "خدمت"
        verbose_name_plural = "خدمات"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("core:service_detail", kwargs={"slug": self.slug})


class FAQ(models.Model):
    question = models.CharField(max_length=255, verbose_name="سؤال")
    answer = models.TextField(verbose_name="پاسخ")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "سؤال متداول"
        verbose_name_plural = "سؤالات متداول"

    def __str__(self):
        return self.question


class ContactMessage(models.Model):
    name = models.CharField(max_length=100, verbose_name="نام")
    phone = models.CharField(
        max_length=11,
        validators=[iran_mobile_validator],
        verbose_name="شماره موبایل",
    )
    email = models.EmailField(blank=True, verbose_name="ایمیل")
    message = models.TextField(max_length=2000, verbose_name="پیام")
    is_read = models.BooleanField(default=False, verbose_name="خوانده شده")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ارسال")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "پیام تماس"
        verbose_name_plural = "پیام‌های تماس"

    def __str__(self):
        return f"{self.name} - {self.phone}"


class TransformationCaseQuerySet(models.QuerySet):
    def public(self):
        # بدون رضایت کتبی مراجع هیچ تصویری در سایت نمایش داده نمی‌شود
        return self.filter(is_active=True, client_consent=True)


class TransformationCase(models.Model):
    """نمونه‌کار قبل/بعد مراجعان (فقط با تصاویر واقعی و رضایت مراجع)."""

    title = models.CharField(
        max_length=150,
        verbose_name="عنوان",
        help_text="مثال: کاهش وزن با برنامه‌ی غذایی شخصی",
    )
    result = models.CharField(
        max_length=100,
        verbose_name="نتیجه",
        help_text="مثال: ۱۲ کیلوگرم کاهش وزن",
    )
    duration = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="مدت",
        help_text="مثال: ۴ ماه",
    )
    description = models.TextField(blank=True, max_length=600, verbose_name="توضیح کوتاه")
    before_image = WebPImageField(upload_to="transformations/", verbose_name="تصویر قبل")
    after_image = WebPImageField(upload_to="transformations/", verbose_name="تصویر بعد")
    client_consent = models.BooleanField(
        default=False,
        verbose_name="رضایت کتبی مراجع گرفته شده است",
        help_text="تا این گزینه تأیید نشود، نمونه‌کار در سایت نمایش داده نمی‌شود.",
    )
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")

    objects = TransformationCaseQuerySet.as_manager()

    class Meta:
        ordering = ["order", "-created_at"]
        verbose_name = "نمونه‌کار قبل و بعد"
        verbose_name_plural = "نمونه‌کارهای قبل و بعد"

    def __str__(self):
        return self.title
