from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from utils.fields import WebPImageField
from utils.validators import iran_mobile_validator, validate_image_size


class SiteSettings(models.Model):
    clinic_name = models.CharField(
        max_length=100,
        verbose_name="نام کلینیک",
        help_text="نام کلینیک که در هدر، فوتر و عنوان صفحات نمایش داده می‌شود.",
    )
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
    phone = models.CharField(
        max_length=20,
        verbose_name="تلفن",
        help_text="شماره‌ی تماس کلینیک که در هدر، فوتر و صفحه‌ی تماس نمایش داده می‌شود. مثال: 02112345678",
    )
    email = models.EmailField(
        blank=True,
        verbose_name="ایمیل",
        help_text="ایمیل کلینیک که در صفحه‌ی تماس نمایش داده می‌شود (اختیاری).",
    )
    address = models.TextField(
        blank=True,
        verbose_name="نشانی",
        help_text="نشانی کامل مطب که در فوتر و صفحه‌ی تماس نمایش داده می‌شود.",
    )
    open_at = models.TimeField(
        null=True,
        blank=True,
        verbose_name="ساعت شروع کار",
        help_text="ساعت شروع کار روزانه‌ی کلینیک برای نمایش در سایت. مثال: 09:00",
    )
    close_at = models.TimeField(
        null=True,
        blank=True,
        verbose_name="ساعت پایان کار",
        help_text="ساعت پایان کار روزانه‌ی کلینیک برای نمایش در سایت. مثال: 18:00",
    )
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
    instagram_url = models.URLField(
        blank=True,
        verbose_name="اینستاگرام",
        help_text="آدرس کامل صفحه‌ی اینستاگرام (با https://). در صورت خالی بودن، آیکون آن نمایش داده نمی‌شود.",
    )
    telegram_url = models.URLField(
        blank=True,
        verbose_name="تلگرام",
        help_text="آدرس کامل کانال یا حساب تلگرام (با https://). در صورت خالی بودن، آیکون آن نمایش داده نمی‌شود.",
    )
    whatsapp_url = models.URLField(
        blank=True,
        verbose_name="واتس‌اپ",
        help_text=(
            "آدرس کامل واتس‌اپ (مثلاً https://wa.me/989121234567). در صورت خالی بودن، آیکون آن نمایش داده نمی‌شود."
        ),
    )
    about_text = models.TextField(
        blank=True,
        verbose_name="متن درباره ما",
        help_text="متن صفحه‌ی «درباره ما» و بخش معرفی صفحه‌ی اصلی. بین پاراگراف‌ها یک خط خالی بگذارید.",
    )
    terms_text = models.TextField(
        blank=True,
        verbose_name="قوانین و مقررات",
        help_text="متن صفحه‌ی «قوانین و مقررات». بین پاراگراف‌ها یک خط خالی بگذارید.",
    )
    privacy_text = models.TextField(
        blank=True,
        verbose_name="حریم خصوصی",
        help_text="متن صفحه‌ی «حریم خصوصی». بین پاراگراف‌ها یک خط خالی بگذارید.",
    )
    payment_timeout_minutes = models.PositiveIntegerField(
        default=10,
        verbose_name="مهلت پرداخت نوبت (دقیقه)",
        help_text=(
            "مدتی (به دقیقه) که نوبت پس از ثبت برای پرداخت بیمار رزرو می‌ماند؛ پس از آن نوبت پرداخت‌نشده خودکار لغو می‌شود. پیشنهاد: ۱۰"
        ),
    )
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
    deposit_percent = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name="درصد بیعانه‌ی نوبت",
        help_text=(
            "بیمار هنگام رزرو فقط این درصد از هزینه‌ی ویزیت را آنلاین پرداخت می‌کند و مابقی را در مطب می‌پردازد. "
            "مثال: ۳۰ یعنی برای ویزیت ۳۰۰٬۰۰۰ تومانی، ۹۰٬۰۰۰ تومان آنلاین. عدد ۱۰۰ یعنی پرداخت کامل هزینه به‌صورت آنلاین."
        ),
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
    shipping_cost = models.PositiveIntegerField(
        default=0,
        verbose_name="هزینه‌ی ارسال (تومان)",
        help_text="هزینه‌ی ارسال هر سفارش فیزیکی به تومان. عدد ۰ یعنی ارسال رایگان.",
    )
    free_shipping_threshold = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="حداقل خرید برای ارسال رایگان (تومان)",
        help_text="اگر مبلغ خرید به این عدد (تومان) برسد، ارسال رایگان می‌شود. خالی یعنی ارسال رایگان نداریم.",
    )
    order_payment_timeout_minutes = models.PositiveIntegerField(
        default=30,
        verbose_name="مهلت پرداخت سفارش (دقیقه)",
        help_text="پس از این مدت سفارش پرداخت‌نشده لغو و موجودی آزاد می‌شود.",
    )

    # اعلان‌های پیامکی (نام قالب هر پیامک در .env؛ apps/core/notifications.py)
    sms_appointment_confirmed = models.BooleanField(
        default=True,
        verbose_name="پیامک تأیید نوبت",
        help_text=(
            "اگر فعال باشد، پس از تأیید نوبت (پرداخت آنلاین، تأیید دستی یا ویزیت رایگان) برای بیمار پیامک ارسال می‌شود."
        ),
    )
    sms_appointment_cancelled = models.BooleanField(
        default=True,
        verbose_name="پیامک لغو نوبت توسط کلینیک",
        help_text="اگر فعال باشد، وقتی کلینیک نوبتی را لغو می‌کند برای بیمار پیامک ارسال می‌شود.",
    )
    sms_order_paid = models.BooleanField(
        default=True,
        verbose_name="پیامک ثبت و پرداخت سفارش",
        help_text="اگر فعال باشد، پس از پرداخت موفق سفارش برای مشتری پیامک ارسال می‌شود.",
    )
    sms_order_shipped = models.BooleanField(
        default=True,
        verbose_name="پیامک ارسال سفارش",
        help_text="اگر فعال باشد، وقتی وضعیت سفارش به «ارسال‌شده» تغییر می‌کند برای مشتری پیامک ارسال می‌شود.",
    )
    sms_diet_ready = models.BooleanField(
        default=True,
        verbose_name="پیامک آماده شدن رژیم",
        help_text="اگر فعال باشد، پس از قرار گرفتن رژیم در پنل بیمار برای او پیامک ارسال می‌شود.",
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
    title = models.CharField(
        max_length=150,
        verbose_name="عنوان",
        help_text="نام خدمت که در سایت نمایش داده می‌شود. مثال: برنامه‌ی کاهش وزن",
    )
    slug = models.SlugField(
        max_length=160,
        unique=True,
        allow_unicode=True,
        verbose_name="نامک (آدرس)",
        help_text="بخشی از آدرس صفحه‌ی خدمت؛ از روی عنوان پر می‌شود. فقط حروف، عدد و خط تیره، بدون فاصله.",
    )
    summary = models.CharField(
        max_length=255,
        verbose_name="خلاصه",
        help_text="یک یا دو جمله‌ی کوتاه که روی کارت خدمت در صفحه‌ی اصلی نمایش داده می‌شود.",
    )
    body = models.TextField(
        blank=True,
        verbose_name="توضیحات کامل",
        help_text="توضیح کامل خدمت در صفحه‌ی اختصاصی آن. بین پاراگراف‌ها یک خط خالی بگذارید.",
    )
    image = WebPImageField(
        upload_to="services/",
        blank=True,
        verbose_name="تصویر",
        help_text="تصویر کارت و صفحه‌ی خدمت؛ افقی، حدود ۸۰۰×۶۰۰ پیکسل، حداکثر ۵ مگابایت.",
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="ترتیب",
        help_text="ترتیب نمایش؛ عدد کوچک‌تر جلوتر نمایش داده می‌شود.",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
        help_text="اگر غیرفعال شود، خدمت از سایت پنهان می‌شود ولی حذف نمی‌شود.",
    )

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "خدمت"
        verbose_name_plural = "خدمات"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("core:service_detail", kwargs={"slug": self.slug})


class FAQ(models.Model):
    question = models.CharField(
        max_length=255,
        verbose_name="سؤال",
        help_text="متن سؤال، همان‌طور که در سایت نمایش داده می‌شود.",
    )
    answer = models.TextField(
        verbose_name="پاسخ",
        help_text="پاسخ کامل سؤال.",
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="ترتیب",
        help_text="ترتیب نمایش؛ عدد کوچک‌تر بالاتر نمایش داده می‌شود.",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
        help_text="اگر غیرفعال شود، سؤال در سایت نمایش داده نمی‌شود ولی حذف نمی‌شود.",
    )

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "سؤال متداول"
        verbose_name_plural = "سؤالات متداول"

    def __str__(self):
        return self.question


class ContactMessage(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name="نام",
        help_text="نامی که فرستنده در فرم تماس وارد کرده است.",
    )
    phone = models.CharField(
        max_length=11,
        validators=[iran_mobile_validator],
        verbose_name="شماره موبایل",
        help_text="شماره‌ی موبایل فرستنده برای تماس با او.",
    )
    email = models.EmailField(
        blank=True,
        verbose_name="ایمیل",
        help_text="ایمیل فرستنده (اختیاری).",
    )
    message = models.TextField(
        max_length=2000,
        verbose_name="پیام",
        help_text="متن پیام ارسال‌شده از فرم «تماس با ما».",
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name="خوانده شده",
        help_text="پس از رسیدگی به پیام علامت بزنید تا پیام‌های جدید از رسیدگی‌شده‌ها جدا باشند.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ارسال",
        help_text="زمان ارسال پیام.",
    )

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
    description = models.TextField(
        blank=True,
        max_length=600,
        verbose_name="توضیح کوتاه",
        help_text="توضیح کوتاه درباره‌ی برنامه و روند مراجع، بدون ذکر نام یا اطلاعات شناسایی او.",
    )
    before_image = WebPImageField(
        upload_to="transformations/",
        verbose_name="تصویر قبل",
        help_text="عکس پیش از شروع برنامه؛ عمودی، حدود ۶۰۰×۸۰۰ پیکسل. زاویه و کادر دو عکس یکسان باشد.",
    )
    after_image = WebPImageField(
        upload_to="transformations/",
        verbose_name="تصویر بعد",
        help_text="عکس پس از برنامه با همان زاویه و کادر عکس قبل؛ عمودی، حدود ۶۰۰×۸۰۰ پیکسل.",
    )
    client_consent = models.BooleanField(
        default=False,
        verbose_name="رضایت کتبی مراجع گرفته شده است",
        help_text="تا این گزینه تأیید نشود، نمونه‌کار در سایت نمایش داده نمی‌شود.",
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="ترتیب",
        help_text="ترتیب نمایش؛ عدد کوچک‌تر جلوتر نمایش داده می‌شود.",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
        help_text="اگر غیرفعال شود، این نمونه‌کار در سایت نمایش داده نمی‌شود ولی حذف نمی‌شود.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد",
        help_text="زمان ثبت؛ به‌طور خودکار ثبت می‌شود.",
    )

    objects = TransformationCaseQuerySet.as_manager()

    class Meta:
        ordering = ["order", "-created_at"]
        verbose_name = "نمونه‌کار قبل و بعد"
        verbose_name_plural = "نمونه‌کارهای قبل و بعد"

    def __str__(self):
        return self.title
