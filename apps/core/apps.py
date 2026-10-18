from django.apps import AppConfig
from django.contrib.staticfiles.apps import StaticFilesConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = "تنظیمات و محتوا"


class ClinicStaticFilesConfig(StaticFilesConfig):
    """
    فایل‌های ورودی build تیلویند (tailwind.css، clinic.css و partialهای قالب)
    در زمان اجرا لازم نیستند و فقط clinic.build.css سرو می‌شود؛ پس در
    collectstatic جمع‌آوری نمی‌شوند. (مسیرهای نسبی داخل partialها فقط پس از build معتبرند.)
    """

    ignore_patterns = StaticFilesConfig.ignore_patterns + [
        "clinicmaster/assets/css/tailwind.css",
        "clinicmaster/assets/css/clinic.css",
        "clinicmaster/assets/css/*/*.css",
    ]
