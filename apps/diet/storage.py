"""
ذخیره‌سازی خصوصی فایل‌های پزشکی (PDF رژیم‌ها).

فایل‌ها خارج از MEDIA_ROOT (که Nginx عمومی سرو می‌کند) ذخیره می‌شوند و فقط از طریق viewهایی
که دسترسی را بررسی می‌کنند تحویل داده می‌شوند (serve_private_file).
"""
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404, HttpResponse
from django.urls import reverse
from django.utils.deconstruct import deconstructible
from django.utils.http import content_disposition_header


@deconstructible
class PrivateMediaStorage(FileSystemStorage):
    """مسیر از settings.PRIVATE_MEDIA_ROOT در زمان اجرا خوانده می‌شود (نه در migration)."""

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return str(Path(self.base_location).resolve())

    def url(self, name):
        # لینک ادمین به view مخصوص کارکنان؛ آدرس مستقیم فایل وجود ندارد
        return reverse("diet:staff_file", kwargs={"path": name})

    # تنظیمات همه‌ی نمونه‌ها یکی است؛ بدون این، autodetector هر بار فیلد فایل را «تغییرکرده» می‌بیند
    # و روی SQLite جدول را بازسازی می‌کند
    def __eq__(self, other):
        return isinstance(other, PrivateMediaStorage)

    def __hash__(self):
        return hash(PrivateMediaStorage)


private_storage = PrivateMediaStorage()


# نام تصادفی تا نام فایل اصلی (که ممکن است نام بیمار باشد) فاش نشود و قابل حدس نباشد
def template_upload_to(instance, filename):
    return f"diet_templates/{uuid.uuid4().hex}.pdf"


def patient_diet_upload_to(instance, filename):
    return f"patient_diets/{uuid.uuid4().hex}.pdf"


def pdf_download_name(title):
    """نام فایل دانلودی از روی عنوان (بدون کاراکترهای مسیر)."""
    cleaned = "".join("-" if ch in '\\/:*?"<>|' else ch for ch in title).strip() or "diet"
    return f"{cleaned[:100]}.pdf"


def serve_private_file(field_file, download_name):
    """
    تحویل فایل خصوصی. در Production با PRIVATE_MEDIA_SERVE=nginx فقط هدر X-Accel-Redirect
    برگردانده می‌شود و خود Nginx فایل را از location داخلی (internal) می‌فرستد.
    """
    if not field_file or not field_file.storage.exists(field_file.name):
        raise Http404("فایل پیدا نشد.")

    if settings.PRIVATE_MEDIA_SERVE == "nginx":
        response = HttpResponse(content_type="application/pdf")
        response["X-Accel-Redirect"] = settings.PRIVATE_MEDIA_ACCEL_PREFIX + field_file.name
        response["Content-Disposition"] = content_disposition_header(True, download_name)
    else:
        response = FileResponse(
            field_file.open("rb"),
            as_attachment=True,
            filename=download_name,
            content_type="application/pdf",
        )

    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
