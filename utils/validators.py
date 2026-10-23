from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

iran_mobile_validator = RegexValidator(
    regex=r"^09\d{9}$",
    message="شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود.",
)


def normalize_digits(value):
    """تبدیل ارقام فارسی و عربی به انگلیسی."""
    if not value:
        return value
    return value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def validate_image_size(file):
    """حداکثر حجم تصویر آپلودی (settings.MAX_IMAGE_UPLOAD_SIZE، پیش‌فرض ۵ مگابایت)."""
    limit = getattr(settings, "MAX_IMAGE_UPLOAD_SIZE", 5 * 1024 * 1024)
    size = getattr(file, "size", 0) or 0
    if size > limit:
        raise ValidationError(f"حجم تصویر نباید بیشتر از {limit // (1024 * 1024)} مگابایت باشد.")
