from django.contrib import admin
from django.utils import timezone
from jalali_date.admin import ModelAdminJalaliMixin

from .models import Post, PostCategory


@admin.register(PostCategory)
class PostCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_active")
    list_editable = ("order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Post)
class PostAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("title", "category", "status", "published_at", "author")
    list_filter = ("status", "category", "published_at")
    list_select_related = ("category", "author")
    search_fields = ("title", "summary", "body")
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_at"
    readonly_fields = ("created_at", "updated_at")
    actions = ["publish", "unpublish"]
    fieldsets = (
        (None, {"fields": ("title", "slug", "category", "image")}),
        ("محتوا", {
            "fields": ("summary", "body"),
            "description": "خلاصه روی کارت مقاله و در نتایج گوگل نمایش داده می‌شود؛ متن کامل در صفحه‌ی مقاله.",
        }),
        ("انتشار", {
            "fields": ("status", "published_at", "author", "created_at", "updated_at"),
            "description": "تا وضعیت «منتشرشده» نباشد و زمان انتشار نرسیده باشد، مقاله فقط برای کارکنان قابل مشاهده است.",
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="انتشار مقاله‌های انتخاب‌شده (نمایش در سایت)")
    def publish(self, request, queryset):
        updated = queryset.filter(status=Post.STATUS_DRAFT).update(status=Post.STATUS_PUBLISHED)
        self.message_user(request, f"{updated} مقاله منتشر شد.")

    @admin.action(description="بازگرداندن به پیش‌نویس (پنهان شدن از سایت)")
    def unpublish(self, request, queryset):
        updated = queryset.update(status=Post.STATUS_DRAFT)
        self.message_user(request, f"{updated} مقاله به پیش‌نویس برگشت.")
