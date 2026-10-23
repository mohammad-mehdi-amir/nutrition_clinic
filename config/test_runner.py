import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.test.runner import DiscoverRunner


class ClinicTestRunner(DiscoverRunner):
    """
    - محدودیت نرخ در تست‌ها خاموش است (تست‌های خودش آن را با override_settings روشن می‌کنند).
    - فایل‌های آپلودی تست‌ها در پوشه‌ی موقت ذخیره و در پایان پاک می‌شوند.
    """

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        settings.RATELIMIT_ENABLED = False

        self._upload_dir = tempfile.mkdtemp(prefix="clinic-tests-")
        settings.MEDIA_ROOT = Path(self._upload_dir) / "media"
        settings.PRIVATE_MEDIA_ROOT = Path(self._upload_dir) / "private_media"

    def teardown_test_environment(self, **kwargs):
        shutil.rmtree(self._upload_dir, ignore_errors=True)
        super().teardown_test_environment(**kwargs)
