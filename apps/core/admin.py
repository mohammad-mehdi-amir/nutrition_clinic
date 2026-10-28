from django.contrib import admin
from django.utils.html import format_html
from jalali_date.admin import ModelAdminJalaliMixin

from .models import FAQ, ContactMessage, Service, SiteSettings, TransformationCase


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("clinic_name", "phone", "email")
    fieldsets = (
        ("اطلاعات کلینیک", {
            "fields": ("clinic_name", "tagline", "logo", "about_text"),
            "description": "این اطلاعات در هدر، فوتر، صفحه‌ی «درباره ما» و عنوان صفحات سایت نمایش داده می‌شود.",
        }),
        ("تماس", {
            "fields": ("phone", "email", "address", "map_embed_url"),
            "description": "راه‌های تماس که در فوتر و صفحه‌ی «تماس با ما» نمایش داده می‌شود.",
        }),
        ("ساعات کاری", {
            "fields": ("working_days", "open_at", "close_at"),
            "description": "فقط برای نمایش در سایت است؛ ساعت‌های قابل رزرو هر پزشک در «برنامه‌ی هفتگی» پزشکان تعیین می‌شود.",
        }),
        ("شبکه‌های اجتماعی", {
            "fields": ("instagram_url", "telegram_url", "whatsapp_url"),
            "description": "آدرس کامل هر صفحه را وارد کنید؛ موارد خالی در سایت نمایش داده نمی‌شوند.",
        }),
        ("صفحات حقوقی", {
            "fields": ("terms_text", "privacy_text"),
            "description": "متن صفحات «قوانین و مقررات» و «حریم خصوصی». پیش از راه‌اندازی سایت حتماً بازبینی شود.",
        }),
        ("تصاویر سایت", {
            "fields": ("favicon", "hero_image", "about_image", "page_banner_image", "faq_image", "bmi_image", "cta_image"),
            "description": "در صورت خالی بودن هر مورد، تصویر پیش‌فرض قالب نمایش داده می‌شود. حجم هر تصویر حداکثر ۵ مگابایت.",
        }),
        ("نوبت‌دهی", {
            "fields": ("default_visit_fee", "deposit_percent", "payment_timeout_minutes", "cancellation_deadline_hours"),
            "description": "قوانین پرداخت و لغو نوبت. تغییر این مقادیر فقط روی نوبت‌های جدید اثر دارد؛ مبالغ نوبت‌های ثبت‌شده تغییر نمی‌کند.",
        }),
        ("فروشگاه", {
            "fields": ("shipping_cost", "free_shipping_threshold", "order_payment_timeout_minutes"),
            "description": "هزینه‌ی ارسال و مهلت پرداخت سفارش‌های فروشگاه (مبالغ به تومان).",
        }),
        ("اعلان‌های پیامکی", {
            "fields": ("sms_appointment_confirmed", "sms_appointment_cancelled", "sms_order_paid", "sms_order_shipped", "sms_diet_ready"),
            "description": "هر پیامک فقط وقتی ارسال می‌شود که روشن باشد و نام قالب آن در تنظیمات سرور (.env) وارد شده باشد.",
        }),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("title", "order", "is_active")
    list_editable = ("order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title", "summary")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "order", "is_active")
    list_editable = ("order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("question", "answer")


@admin.register(ContactMessage)
class ContactMessageAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("name", "phone", "email", "created_at", "is_read")
    list_filter = ("is_read", "created_at")
    search_fields = ("name", "phone", "email", "message")
    readonly_fields = ("name", "phone", "email", "message", "created_at")
    actions = ["mark_as_read"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="علامت‌گذاری به‌عنوان خوانده شده (پس از رسیدگی به پیام)")
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)


@admin.register(TransformationCase)
class TransformationCaseAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("title", "result", "duration", "thumbnails", "client_consent", "is_active", "order")
    list_editable = ("order", "is_active")
    list_filter = ("client_consent", "is_active")
    search_fields = ("title", "result")
    fieldsets = (
        (None, {"fields": ("title", "result", "duration", "description")}),
        ("تصاویر", {
            "fields": ("before_image", "after_image"),
            "description": "از هر دو تصویر با زاویه و کادر مشابه استفاده کنید (عمودی، حدود ۶۰۰×۸۰۰ پیکسل).",
        }),
        ("نمایش", {"fields": ("client_consent", "is_active", "order")}),
    )

    @admin.display(description="تصاویر")
    def thumbnails(self, obj):
        return format_html(
            '<img src="{}" style="height:48px;border-radius:6px"> <img src="{}" style="height:48px;border-radius:6px">',
            obj.before_image.url, obj.after_image.url,
        )
