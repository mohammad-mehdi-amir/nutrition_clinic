from django.contrib import admin, messages
from jalali_date.admin import ModelAdminJalaliMixin

from apps.core import notifications
from apps.diet.services import create_requests_for_order

from .models import Category, Order, OrderItem, Product
from .services import PAID_ORDER_STATUSES, OrderError, cancel_order


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_active")
    list_editable = ("order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "product_type", "category", "price", "discount_price", "stock", "is_active")
    list_editable = ("price", "discount_price", "stock", "is_active")
    list_filter = ("product_type", "category", "is_active")
    list_select_related = ("category",)
    search_fields = ("name", "short_description")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {
            "fields": ("product_type", "name", "slug", "category", "is_active"),
            "description": "ابتدا نوع را انتخاب کنید؛ سپس فقط بخش مربوط به همان نوع (محصول فیزیکی یا پکیج رژیم) را پر کنید.",
        }),
        ("قیمت", {"fields": ("price", "discount_price"), "description": "مبالغ به تومان، بدون ممیز. مثال: 450000"}),
        ("محصول فیزیکی", {"fields": ("stock",), "description": "فقط برای محصول فیزیکی پر شود؛ برای پکیج رژیم خالی بماند."}),
        ("پکیج رژیم", {"fields": ("duration_days", "features"), "description": "فقط برای پکیج رژیم پر شود؛ برای محصول فیزیکی خالی بماند."}),
        ("محتوا", {"fields": ("image", "short_description", "description"), "description": "متن و تصویری که مشتری در فروشگاه می‌بیند."}),
    )


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ("product_name", "product_type", "unit_price", "quantity", "line_total")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("__str__", "user", "recipient_name", "total", "status", "created_at")
    list_filter = ("status", "created_at")
    list_select_related = ("user",)
    search_fields = ("id", "user__username", "user__phone_number", "recipient_name", "recipient_phone")
    readonly_fields = ("user", "subtotal", "shipping_cost", "total", "payment_deadline", "created_at", "updated_at")
    inlines = [OrderItemInline]
    actions = ["cancel_orders"]
    fieldsets = (
        (None, {
            "fields": ("user", "status", "payment_deadline", "created_at", "updated_at"),
            "description": "برای پیشبرد سفارش، «وضعیت» را تغییر دهید و ذخیره کنید (مثلاً پس از تحویل بسته به پست: «ارسال‌شده»).",
        }),
        ("گیرنده", {
            "fields": ("recipient_name", "recipient_phone", "province", "city", "address", "postal_code", "note"),
            "description": "اطلاعات ارسال که مشتری هنگام خرید وارد کرده است.",
        }),
        ("مبالغ (تومان)", {
            "fields": ("subtotal", "shipping_cost", "total"),
            "description": "مبالغ در لحظه‌ی خرید ثبت شده‌اند و قابل تغییر نیستند.",
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and "status" in form.changed_data and obj.status == Order.STATUS_SHIPPED:
            notifications.order_shipped(obj)
        # اگر ادمین پرداخت را دستی ثبت کند، درخواست رژیم پکیج‌ها هم ساخته شود
        if obj.status in PAID_ORDER_STATUSES:
            create_requests_for_order(obj)

    def has_add_permission(self, request):
        # سفارش فقط از مسیر تسویه‌حساب ساخته می‌شود تا مبالغ و موجودی معتبر بمانند
        return False

    @admin.action(description="لغو سفارش‌های در انتظار پرداخت (موجودی کالاها به انبار برمی‌گردد)")
    def cancel_orders(self, request, queryset):
        cancelled = 0
        for order in queryset:
            try:
                cancel_order(order)
                cancelled += 1
            except OrderError:
                continue
        self.message_user(request, f"{cancelled} سفارش لغو شد.", messages.SUCCESS)
