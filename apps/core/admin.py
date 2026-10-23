from django.contrib import admin

from django.utils.html import format_html

from .models import FAQ, ContactMessage, Service, SiteSettings, TransformationCase


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("clinic_name", "phone", "email")
    fieldsets = (
        ("اطلاعات کلینیک", {"fields": ("clinic_name", "tagline", "logo", "about_text")}),
        ("تماس", {"fields": ("phone", "email", "address", "map_embed_url")}),
        ("ساعات کاری", {"fields": ("working_days", "open_at", "close_at")}),
        ("شبکه‌های اجتماعی", {"fields": ("instagram_url", "telegram_url", "whatsapp_url")}),
        ("صفحات حقوقی", {"fields": ("terms_text", "privacy_text")}),
        ("تصاویر سایت", {
            "fields": ("favicon", "hero_image", "about_image", "page_banner_image", "faq_image", "bmi_image", "cta_image"),
            "description": "در صورت خالی بودن هر مورد، تصویر پیش‌فرض قالب نمایش داده می‌شود.",
        }),
        ("نوبت‌دهی", {"fields": ("default_visit_fee", "payment_timeout_minutes", "cancellation_deadline_hours")}),
        ("فروشگاه", {"fields": ("shipping_cost", "free_shipping_threshold", "order_payment_timeout_minutes")}),
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
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "created_at", "is_read")
    list_filter = ("is_read",)
    search_fields = ("name", "phone", "email", "message")
    readonly_fields = ("name", "phone", "email", "message", "created_at")
    actions = ["mark_as_read"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="علامت‌گذاری به‌عنوان خوانده شده")
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)


@admin.register(TransformationCase)
class TransformationCaseAdmin(admin.ModelAdmin):
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
