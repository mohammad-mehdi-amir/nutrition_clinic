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
