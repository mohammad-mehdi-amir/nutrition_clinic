from django.conf import settings
from django.test.runner import DiscoverRunner


class ClinicTestRunner(DiscoverRunner):
    """محدودیت نرخ در تست‌ها خاموش است (تست‌های خودش آن را با override_settings روشن می‌کنند)."""

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        settings.RATELIMIT_ENABLED = False
