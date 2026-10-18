from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.urls import reverse

from utils.fields import WebPImageField
from utils.validators import iran_mobile_validator


class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="نام")
    slug = models.SlugField(max_length=110, unique=True, allow_unicode=True, verbose_name="نامک (آدرس)")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

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

    product_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_PHYSICAL, verbose_name="نوع")
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="products",
        verbose_name="دسته‌بندی",
    )
    name = models.CharField(max_length=150, verbose_name="نام")
    slug = models.SlugField(max_length=160, unique=True, allow_unicode=True, verbose_name="نامک (آدرس)")
    short_description = models.CharField(max_length=255, verbose_name="توضیح کوتاه")
    description = models.TextField(blank=True, verbose_name="توضیحات کامل")
    image = WebPImageField(upload_to="products/", blank=True, verbose_name="تصویر")
    price = models.PositiveIntegerField(verbose_name="قیمت (تومان)")
    discount_price = models.PositiveIntegerField(null=True, blank=True, verbose_name="قیمت با تخفیف (تومان)")
    stock = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="موجودی",
        help_text="فقط برای محصول فیزیکی.",
    )
    duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="مدت اعتبار (روز)",
        help_text="فقط برای پکیج رژیم.",
    )
    features = models.TextField(
        blank=True,
        verbose_name="موارد شامل پکیج",
        help_text="هر مورد در یک خط.",
    )
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین تغییر")

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
                errors["duration_days"] = "مدت اعتبار پکیج را وارد کنید."

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
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="وضعیت")

    recipient_name = models.CharField(max_length=100, verbose_name="نام گیرنده")
    recipient_phone = models.CharField(max_length=11, validators=[iran_mobile_validator], verbose_name="موبایل گیرنده")
    province = models.CharField(max_length=50, blank=True, verbose_name="استان")
    city = models.CharField(max_length=50, blank=True, verbose_name="شهر")
    address = models.TextField(blank=True, verbose_name="نشانی")
    postal_code = models.CharField(max_length=10, blank=True, verbose_name="کد پستی")
    note = models.CharField(max_length=500, blank=True, verbose_name="توضیحات سفارش")

    subtotal = models.PositiveIntegerField(verbose_name="جمع اقلام (تومان)")
    shipping_cost = models.PositiveIntegerField(default=0, verbose_name="هزینه‌ی ارسال (تومان)")
    total = models.PositiveIntegerField(verbose_name="مبلغ نهایی (تومان)")

    payment_deadline = models.DateTimeField(null=True, blank=True, verbose_name="مهلت پرداخت")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ثبت")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین تغییر")

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
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="سفارش")
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_items",
        verbose_name="محصول",
    )
    # snapshot: تغییرات بعدی محصول روی سفارش ثبت‌شده اثر ندارد
    product_name = models.CharField(max_length=150, verbose_name="نام محصول")
    product_type = models.CharField(max_length=10, choices=Product.TYPE_CHOICES, verbose_name="نوع")
    unit_price = models.PositiveIntegerField(verbose_name="قیمت واحد (تومان)")
    quantity = models.PositiveIntegerField(verbose_name="تعداد")
    line_total = models.PositiveIntegerField(verbose_name="جمع (تومان)")

    class Meta:
        verbose_name = "قلم سفارش"
        verbose_name_plural = "اقلام سفارش"

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"
