import shutil
import tempfile
from io import BytesIO
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.appointments.models import Doctor
from .models import FAQ, ContactMessage, Service, SiteSettings


class PublicPagesTests(TestCase):

    def test_pages_render_without_site_settings(self):
        for name in ["home", "about", "services", "faqs", "contact", "terms", "privacy"]:
            with self.subTest(page=name):
                response = self.client.get(reverse(f"core:{name}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'dir="rtl"')

    def test_site_settings_in_context(self):
        SiteSettings.objects.create(clinic_name="کلینیک آزمایشی", phone="02112345678")
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "کلینیک آزمایشی")
        self.assertContains(response, "02112345678")

    def test_home_lists_only_active_services_and_doctors(self):
        Service.objects.create(title="مشاوره", slug="consult", summary="خلاصه")
        Service.objects.create(title="غیرفعال", slug="hidden", summary="خلاصه", is_active=False)
        Doctor.objects.create(name="دکتر فعال", specialty="تغذیه")
        Doctor.objects.create(name="دکتر غیرفعال", specialty="تغذیه", is_active=False)

        response = self.client.get(reverse("core:home"))

        self.assertContains(response, "مشاوره")
        self.assertNotContains(response, "غیرفعال")
        self.assertContains(response, "دکتر فعال")
        self.assertNotContains(response, "دکتر غیرفعال")

    def test_service_detail(self):
        service = Service.objects.create(title="کاهش وزن", slug="کاهش-وزن", summary="برنامه‌ی کاهش وزن")
        response = self.client.get(service.get_absolute_url())
        self.assertContains(response, "برنامه‌ی کاهش وزن")

    def test_inactive_service_detail_404(self):
        Service.objects.create(title="x", slug="x", summary="x", is_active=False)
        response = self.client.get(reverse("core:service_detail", kwargs={"slug": "x"}))
        self.assertEqual(response.status_code, 404)

    def test_faqs_page_shows_active_only(self):
        FAQ.objects.create(question="سؤال فعال؟", answer="بله")
        FAQ.objects.create(question="سؤال مخفی؟", answer="نه", is_active=False)
        response = self.client.get(reverse("core:faqs"))
        self.assertContains(response, "سؤال فعال؟")
        self.assertNotContains(response, "سؤال مخفی؟")

    def test_doctors_page(self):
        Doctor.objects.create(name="دکتر نمونه", specialty="رژیم‌درمانی")
        response = self.client.get(reverse("appointments:doctors"))
        self.assertContains(response, "دکتر نمونه")

    @override_settings(DEBUG=False)
    def test_custom_404_template(self):
        response = self.client.get("/page-that-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "صفحه‌ای که به دنبال آن هستید پیدا نشد", status_code=404)


class ContactFormTests(TestCase):

    def test_valid_message_is_saved(self):
        response = self.client.post(
            reverse("core:contact"),
            {"name": "علی", "phone": "۰۹۱۲۳۴۵۶۷۸۹", "message": "سلام"},
            follow=True,
        )

        self.assertRedirects(response, reverse("core:contact"))
        message = ContactMessage.objects.get()
        self.assertEqual(message.phone, "09123456789")
        self.assertContains(response, "پیام شما ثبت شد")

    def test_invalid_phone_rejected(self):
        response = self.client.post(
            reverse("core:contact"),
            {"name": "علی", "phone": "12345", "message": "سلام"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ContactMessage.objects.exists())
        self.assertContains(response, "شماره موبایل باید ۱۱ رقم")


class WebPImageFieldTests(TestCase):

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def _jpeg(self, name="photo.jpg"):
        buffer = BytesIO()
        Image.new("RGB", (20, 20), "green").save(buffer, format="JPEG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")

    def test_upload_converted_to_webp_without_nested_path_or_original(self):
        service = Service.objects.create(title="t", slug="t", summary="s", image=self._jpeg())

        self.assertEqual(service.image.name, "services/photo.webp")
        files = [p.relative_to(self.media_root).as_posix() for p in Path(self.media_root).rglob("*") if p.is_file()]
        self.assertEqual(files, ["services/photo.webp"])

        with Image.open(service.image.path) as image:
            self.assertEqual(image.format, "WEBP")

    def test_resave_does_not_reprocess(self):
        service = Service.objects.create(title="t", slug="t", summary="s", image=self._jpeg())
        service.title = "new"
        service.save()

        files = list(Path(self.media_root).rglob("*.webp"))
        self.assertEqual(len(files), 1)


class SiteImageTests(TestCase):

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_falls_back_to_template_image(self):
        SiteSettings.objects.create(clinic_name="c", phone="1")
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "clinicmaster/src/images/hero-banner/1.png")

    def test_uploaded_image_is_used(self):
        buffer = BytesIO()
        Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(buffer, format="PNG")
        SiteSettings.objects.create(
            clinic_name="c",
            phone="1",
            hero_image=SimpleUploadedFile("hero.png", buffer.getvalue(), content_type="image/png"),
        )
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "/media/site/hero.webp")
        self.assertNotContains(response, "hero-banner/1.png")
