from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.urls import reverse

from utils.fields import WebPImageField
from utils.validators import iran_mobile_validator


class Category(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name="نام",
        help_text="نام دسته که در فروشگاه نمایش داده می‌شود. مثال: مکمل‌ها",
    )
    slug = models.SlugField(
        max_length=110,
        unique=True,
        allow_unicode=True,
        verbose_name="نامک (آدرس)",
        help_text="بخشی از آدرس صفحه‌ی دسته؛ از روی نام پر می‌شود. فقط حروف، عدد و خط تیره، بدون فاصله.",
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="ترتیب",
        help_text="ترتیب نمایش؛ عدد کوچک‌تر بالاتر نمایش داده می‌شود.",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
        help_text="اگر غیرفعال شود، دسته و محصولاتش در فروشگاه نمایش داده نمی‌شوند.",
    )

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("shop:category", kwargs={"slug": self.slug})


class ProductQuerySet(models.QuerySet):
    def available(self):
        return self.filter(is_active=True).filter(
            Q(category__isnull=True) | Q(category__is_active=True)
        )


class Product(models.Model):
    TYPE_PHYSICAL = "physical"
    TYPE_PACKAGE = "package"
    TYPE_CHOICES = [
        (TYPE_PHYSICAL, "محصول فیزیکی"),
        (TYPE_PACKAGE, "پکیج رژیم"),
    ]

    product_type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        default=TYPE_PHYSICAL,
        verbose_name="نوع",
        help_text=(
            "محصول فیزیکی: کالایی که برای مشتری ارسال می‌شود و موجودی دارد · "
            "پکیج رژیم: برنامه‌ی غذایی که پس از خرید به‌صورت PDF در پنل مشتری قرار می‌گیرد."
        ),
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="products",
        verbose_name="دسته‌بندی",
        help_text="دسته‌ای که محصول در آن نمایش داده می‌شود (اختیاری).",
    )
    name = models.CharField(
        max_length=150,
        verbose_name="نام",
        help_text="نام محصول که در فروشگاه نمایش داده می‌شود.",
    )
    slug = models.SlugField(
        max_length=160,
        unique=True,
        allow_unicode=True,
        verbose_name="نامک (آدرس)",
        help_text="بخشی از آدرس صفحه‌ی محصول؛ از روی نام پر می‌شود. فقط حروف، عدد و خط تیره، بدون فاصله.",
    )
    short_description = models.CharField(
        max_length=255,
        verbose_name="توضیح کوتاه",
        help_text="یک جمله‌ی کوتاه که زیر نام محصول روی کارت آن نمایش داده می‌شود.",
    )
    description = models.TextField(
        blank=True,
        verbose_name="توضیحات کامل",
        help_text="توضیح کامل محصول در صفحه‌ی آن. بین پاراگراف‌ها یک خط خالی بگذارید.",
    )
    image = WebPImageField(
        upload_to="products/",
        blank=True,
        verbose_name="تصویر",
        help_text="تصویر محصول؛ مربع، حدود ۸۰۰×۸۰۰ پیکسل، حداکثر ۵ مگابایت.",
    )
    price = models.PositiveIntegerField(
        verbose_name="قیمت (تومان)",
        help_text="قیمت اصلی به تومان. مثال: 450000",
    )
    discount_price = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="قیمت با تخفیف (تومان)",
        help_text=(
            "قیمت پس از تخفیف به تومان (اختیاری). باید کمتر از قیمت اصلی باشد؛ در سایت قیمت اصلی خط‌خورده نمایش داده می‌شود."
        ),
    )
    stock = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="موجودی",
        help_text=(
            "تعداد موجود در انبار؛ فقط برای محصول فیزیکی. با هر خرید کم و با لغو سفارش برگردانده می‌شود. عدد ۰ یعنی ناموجود."
        ),
    )
    duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="مدت برنامه‌ی رژیم (روز)",
        help_text="مدت برنامه‌ی رژیم به روز؛ فقط برای پکیج رژیم. مثال: 30",
    )
    features = models.TextField(
        blank=True,
        verbose_name="موارد شامل پکیج",
        help_text="مواردی که در پکیج ارائه می‌شود؛ هر مورد در یک خط جدا.",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
        help_text="اگر غیرفعال شود، محصول از فروشگاه پنهان می‌شود ولی سفارش‌های قبلی آن باقی می‌مانند.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد",
        help_text="زمان افزودن محصول.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخرین تغییر",
        help_text="زمان آخرین تغییر محصول.",
    )

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"
        constraints = [
            models.CheckConstraint(
                condition=Q(discount_price__isnull=True) | Q(discount_price__lt=F("price")),
                name="product_discount_lt_price",
            ),
            models.CheckConstraint(
                condition=Q(product_type="package", stock__isnull=True) | Q(product_type="physical", stock__isnull=False),
                name="product_stock_matches_type",
            ),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("shop:product_detail", kwargs={"slug": self.slug})

    def clean(self):
        errors = {}

        if self.discount_price is not None and self.price is not None and self.discount_price >= self.price:
            errors["discount_price"] = "قیمت با تخفیف باید کمتر از قیمت اصلی باشد."

        if self.product_type == self.TYPE_PHYSICAL:
            if self.stock is None:
                errors["stock"] = "موجودی محصول فیزیکی را وارد کنید."
        else:
            if self.stock is not None:
                errors["stock"] = "پکیج رژیم موجودی ندارد؛ این فیلد را خالی بگذارید."
            if not self.duration_days:
                errors["duration_days"] = "مدت برنامه‌ی رژیم را وارد کنید."

        if errors:
            raise ValidationError(errors)

    @property
    def is_package(self):
        return self.product_type == self.TYPE_PACKAGE

    @property
    def final_price(self):
        return self.discount_price if self.discount_price is not None else self.price

    @property
    def has_discount(self):
        return self.discount_price is not None

    @property
    def discount_percent(self):
        if not self.has_discount or not self.price:
            return 0
        return round((self.price - self.discount_price) * 100 / self.price)

    @property
    def in_stock(self):
        return self.is_package or (self.stock or 0) > 0

    @property
    def max_quantity(self):
        """بیشترین تعدادی که می‌توان در سبد گذاشت."""
        return 1 if self.is_package else (self.stock or 0)

    @property
    def feature_list(self):
        return [line.strip() for line in self.features.splitlines() if line.strip()]


class Order(models.Model):
    STATUS_PENDING = "pending_payment"
    STATUS_PAID = "paid"
    STATUS_PROCESSING = "processing"
    STATUS_SHIPPED = "shipped"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "در انتظار پرداخت"),
        (STATUS_PAID, "پرداخت‌شده"),
        (STATUS_PROCESSING, "در حال پردازش"),
        (STATUS_SHIPPED, "ارسال‌شده"),
        (STATUS_COMPLETED, "تکمیل‌شده"),
        (STATUS_CANCELLED, "لغوشده"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="کاربر",
        help_text="حساب کاربری مشتری.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name="وضعیت",
        help_text=(
            "در انتظار پرداخت: سفارش ثبت شده ولی هنوز پرداخت نشده؛ پس از پایان مهلت خودکار لغو می‌شود · "
            "پرداخت‌شده: پول دریافت شده و سفارش آماده‌ی پردازش است · "
            "در حال پردازش: سفارش در حال آماده‌سازی است · "
            "ارسال‌شده: بسته تحویل پست یا پیک شده (مشتری پیامک دریافت می‌کند) · "
            "تکمیل‌شده: سفارش به دست مشتری رسیده · "
            "لغوشده: سفارش لغو شده و موجودی کالاها برگشته است. برای لغو سفارش پرداخت‌نشده از دکمه‌ی «عملیات» استفاده کنید."
        ),
    )

    recipient_name = models.CharField(
        max_length=100,
        verbose_name="نام گیرنده",
        help_text="نام کسی که بسته را تحویل می‌گیرد.",
    )
    recipient_phone = models.CharField(
        max_length=11,
        validators=[iran_mobile_validator],
        verbose_name="موبایل گیرنده",
        help_text="شماره‌ی موبایل گیرنده برای هماهنگی ارسال.",
    )
    province = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="استان",
        help_text="استان مقصد. برای سفارشی که فقط پکیج رژیم دارد خالی است.",
    )
    city = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="شهر",
        help_text="شهر مقصد. برای سفارشی که فقط پکیج رژیم دارد خالی است.",
    )
    address = models.TextField(
        blank=True,
        verbose_name="نشانی",
        help_text="نشانی کامل پستی گیرنده.",
    )
    postal_code = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="کد پستی",
        help_text="کد پستی ۱۰ رقمی گیرنده.",
    )
    note = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="توضیحات سفارش",
        help_text="توضیحی که مشتری هنگام ثبت سفارش نوشته است.",
    )

    subtotal = models.PositiveIntegerField(
        verbose_name="جمع اقلام (تومان)",
        help_text="جمع قیمت کالاها بدون هزینه‌ی ارسال؛ هنگام ثبت سفارش محاسبه و ثابت می‌شود.",
    )
    shipping_cost = models.PositiveIntegerField(
        default=0,
        verbose_name="هزینه‌ی ارسال (تومان)",
        help_text="هزینه‌ی ارسال این سفارش.",
    )
    total = models.PositiveIntegerField(
        verbose_name="مبلغ نهایی (تومان)",
        help_text="مبلغی که مشتری پرداخت کرده یا باید پرداخت کند (جمع کالاها + ارسال).",
    )

    payment_deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="مهلت پرداخت",
        help_text="اگر تا این زمان پرداخت نشود، سفارش خودکار لغو و موجودی آزاد می‌شود.",
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان پرداخت",
        help_text="زمان پرداخت موفق سفارش.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="زمان ثبت",
        help_text="زمان ثبت سفارش.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="آخرین تغییر",
        help_text="زمان آخرین تغییر سفارش.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "سفارش"
        verbose_name_plural = "سفارش‌ها"
        indexes = [models.Index(fields=["status", "payment_deadline"])]

    def __str__(self):
        return f"سفارش #{self.pk}"

    def get_absolute_url(self):
        return reverse("shop:order_detail", kwargs={"pk": self.pk})

    @property
    def has_physical_items(self):
        return self.items.filter(product_type=Product.TYPE_PHYSICAL).exists()

    @property
    def can_cancel(self):
        return self.status == self.STATUS_PENDING


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="سفارش",
        help_text="سفارشی که این قلم در آن است.",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_items",
        verbose_name="محصول",
        help_text="محصول (اگر بعداً حذف شود، اطلاعات این قلم باقی می‌ماند).",
    )
    # snapshot: تغییرات بعدی محصول روی سفارش ثبت‌شده اثر ندارد
    product_name = models.CharField(
        max_length=150,
        verbose_name="نام محصول",
        help_text="نام محصول در لحظه‌ی خرید.",
    )
    product_type = models.CharField(
        max_length=10,
        choices=Product.TYPE_CHOICES,
        verbose_name="نوع",
        help_text=(
            "محصول فیزیکی: کالایی که ارسال می‌شود · "
            "پکیج رژیم: برنامه‌ای که به‌صورت PDF در پنل مشتری قرار می‌گیرد."
        ),
    )
    unit_price = models.PositiveIntegerField(
        verbose_name="قیمت واحد (تومان)",
        help_text="قیمت هر عدد در لحظه‌ی خرید؛ تغییر بعدی قیمت محصول روی آن اثری ندارد.",
    )
    quantity = models.PositiveIntegerField(
        verbose_name="تعداد",
        help_text="تعداد خریداری‌شده.",
    )
    line_total = models.PositiveIntegerField(
        verbose_name="جمع (تومان)",
        help_text="قیمت واحد × تعداد.",
    )

    class Meta:
        verbose_name = "قلم سفارش"
        verbose_name_plural = "اقلام سفارش"

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"
