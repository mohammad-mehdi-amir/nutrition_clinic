from io import BytesIO

from django.core.files.base import ContentFile
from django.db import models
from PIL import Image


class WebPImageField(models.ImageField):

    def pre_save(self, model_instance, add):
        file = super().pre_save(model_instance, add)

        if not file:
            return file

        image = Image.open(file)

        if image.format == "WEBP":
            return file

        image = image.convert("RGB")

        output = BytesIO()

        image.save(
            output,
            format="WEBP",
            quality=85,
            optimize=True
        )

        filename = file.name.rsplit(".", 1)[0] + ".webp"

        file.save(
            filename,
            ContentFile(output.getvalue()),
            save=False
        )

        return file