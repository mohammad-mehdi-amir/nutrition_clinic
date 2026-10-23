from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import models
from PIL import Image

from utils.validators import validate_image_size


class WebPImageField(models.ImageField):
    """
    ImageField که فایل آپلودشده را قبل از ذخیره به WEBP تبدیل می‌کند.

    تبدیل فقط روی فایل جدید (commit‌نشده) انجام می‌شود، پس:
    - فایل اصلی (jpg/png) هرگز در storage ذخیره نمی‌شود؛
    - upload_to فقط یک بار اعمال می‌شود (بدون مسیر تودرتو)؛
    - ذخیره‌ی دوباره‌ی مدل، تصویر را دوباره پردازش نمی‌کند.
    """

    # بدون ورود به deconstruct ⇒ migration جدید لازم نیست
    default_validators = models.ImageField.default_validators + [validate_image_size]

    def pre_save(self, model_instance, add):
        file = getattr(model_instance, self.attname)

        if file and not file._committed:
            self._convert_to_webp(file)

        return super().pre_save(model_instance, add)

    @staticmethod
    def _convert_to_webp(file):
        file.seek(0)
        image = Image.open(file)

        if image.format == "WEBP":
            file.seek(0)
            return

        # WEBP از شفافیت پشتیبانی می‌کند؛ کانال alpha را نگه می‌داریم
        has_alpha = image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        )
        image = image.convert("RGBA" if has_alpha else "RGB")

        output = BytesIO()

        image.save(
            output,
            format="WEBP",
            quality=85,
            optimize=True
        )

        file.file = ContentFile(output.getvalue())
        file.name = f"{Path(file.name).stem}.webp"
