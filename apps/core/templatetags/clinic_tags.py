from django import template
from django.templatetags.static import static

register = template.Library()


@register.filter
def price(value):
    """۱۲۰۰۰۰ ⇒ «120,000 تومان» (ارقام با فونت سایت فارسی نمایش داده می‌شوند)."""
    if value in (None, ""):
        return ""
    return f"{int(value):,} تومان"


@register.simple_tag
def site_image(field, fallback):
    """آدرس تصویر آپلودشده در تنظیمات سایت، یا تصویر پیش‌فرض قالب."""
    if field:
        return field.url
    return static(fallback)
