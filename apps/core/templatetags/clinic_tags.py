from pathlib import Path

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
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


@register.simple_tag
def versioned_static(path):
    """
    آدرس فایل استاتیک که با هر تغییر فایل عوض می‌شود تا مرورگر نسخه‌ی قدیمی را از کش نخواند.
    در Production خود ManifestStaticFilesStorage هش محتوا را در نام فایل می‌گذارد؛
    در توسعه زمان آخرین تغییر فایل به‌صورت ?v= اضافه می‌شود.
    """
    url = static(path)
    if settings.DEBUG:
        found = finders.find(path)
        if found:
            url = f"{url}?v={int(Path(found).stat().st_mtime)}"
    return url
