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
        self.assertContains(response, 'name="viewport"', status_code=404)


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


class SeedDemoContentTests(TestCase):

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def _run(self):
        from django.core.management import call_command
        from io import StringIO
        call_command("seed_demo_content", stdout=StringIO())

    def test_fills_site_and_is_idempotent(self):
        from apps.blog.models import Post
        from apps.shop.models import Product

        self._run()
        counts = (Service.objects.count(), FAQ.objects.count(), Post.objects.count(), Product.objects.count())
        self.assertEqual(counts, (6, 8, 6, 8))
        self.assertTrue(all(s.image for s in Service.objects.all()))
        self.assertTrue(Post.objects.published().count() == 6)
        settings_obj = SiteSettings.load()
        self.assertTrue(settings_obj.hero_image.name.endswith(".webp"))
        self.assertTrue(settings_obj.about_text)

        self._run()  # دوباره: چیز تکراری ساخته نمی‌شود
        self.assertEqual(
            (Service.objects.count(), FAQ.objects.count(), Post.objects.count(), Product.objects.count()),
            counts,
        )

    def test_does_not_overwrite_existing_content(self):
        SiteSettings.objects.create(clinic_name="کلینیک من", phone="02100000000", tagline="شعار خودم")
        Service.objects.create(slug="کاهش-وزن", title="عنوان خودم", summary="خلاصه‌ی خودم")

        self._run()

        self.assertEqual(SiteSettings.load().tagline, "شعار خودم")
        self.assertEqual(SiteSettings.load().clinic_name, "کلینیک من")
        self.assertEqual(Service.objects.get(slug="کاهش-وزن").title, "عنوان خودم")


class TransformationSectionTests(TestCase):

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def _image(self, name):
        buffer = BytesIO()
        Image.new("RGB", (30, 40), "green").save(buffer, format="JPEG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")

    def _case(self, title, **extra):
        from .models import TransformationCase
        return TransformationCase.objects.create(
            title=title, result="۱۰ کیلوگرم کاهش وزن",
            before_image=self._image("b.jpg"), after_image=self._image("a.jpg"), **extra,
        )

    def test_only_consented_active_cases_shown_on_home(self):
        self._case("با رضایت", client_consent=True)
        self._case("بدون رضایت", client_consent=False)
        self._case("غیرفعال", client_consent=True, is_active=False)

        response = self.client.get(reverse("core:home"))

        self.assertContains(response, "تغییرات واقعی مراجعان ما")
        self.assertContains(response, "با رضایت")
        self.assertNotContains(response, "بدون رضایت")
        self.assertNotContains(response, "غیرفعال")
        self.assertContains(response, 'type="range"')

    def test_section_hidden_without_cases(self):
        self.assertNotContains(self.client.get(reverse("core:home")), "تغییرات واقعی مراجعان ما")


class ImageUploadValidationTests(TestCase):

    def test_oversized_image_rejected(self):
        from django.core.exceptions import ValidationError

        class FakeFile:
            size = 6 * 1024 * 1024

        field = Service._meta.get_field("image")
        with self.assertRaisesMessage(ValidationError, "مگابایت"):
            field.run_validators(FakeFile())

    def test_non_image_rejected_by_form(self):
        from django import forms

        class ServiceForm(forms.ModelForm):
            class Meta:
                model = Service
                fields = ["title", "slug", "summary", "image"]

        fake = SimpleUploadedFile("evil.jpg", b"<?php echo 1; ?>", content_type="image/jpeg")
        form = ServiceForm({"title": "t", "slug": "t", "summary": "s"}, {"image": fake})
        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)

    def test_svg_rejected_by_form(self):
        from django import forms

        class LogoForm(forms.ModelForm):
            class Meta:
                model = SiteSettings
                fields = ["clinic_name", "phone", "logo"]

        svg = SimpleUploadedFile("logo.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', content_type="image/svg+xml")
        form = LogoForm({"clinic_name": "c", "phone": "1"}, {"logo": svg})
        self.assertFalse(form.is_valid())


class SeoEndpointTests(TestCase):

    def test_robots_txt(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        body = response.content.decode()
        self.assertIn("Disallow: /admin/", body)
        self.assertIn("Disallow: /shop/checkout/", body)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", body)

    def test_sitemap_lists_public_content_only(self):
        from apps.blog.models import Post
        from apps.shop.models import Product
        from django.utils import timezone

        Service.objects.create(title="فعال", slug="active-service", summary="s")
        Service.objects.create(title="غیرفعال", slug="hidden-service", summary="s", is_active=False)
        Post.objects.create(title="p", slug="published-post", summary="s", body="b", status="published", published_at=timezone.now())
        Post.objects.create(title="d", slug="draft-post", summary="s", body="b", status="draft")
        Product.objects.create(product_type="physical", name="x", slug="visible-product", short_description="s", price=1, stock=1)

        response = self.client.get("/sitemap.xml")
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("http://testserver/", body)
        self.assertIn("active-service", body)
        self.assertNotIn("hidden-service", body)
        self.assertIn("published-post", body)
        self.assertNotIn("draft-post", body)
        self.assertIn("visible-product", body)
        self.assertNotIn("/accounts/", body)

    def test_health(self):
        response = self.client.get("/health/")
        self.assertEqual(response.json(), {"status": "ok", "database": True})


@override_settings(ADMINS=[("Admin", "admin@clinic.test")])
class ErrorEmailTests(TestCase):
    """خطاهای ۵۰۰ و رویدادهای مهم برنامه به ADMINS ایمیل می‌شوند؛ هشدارهای امنیتی نه."""

    def test_server_error_is_emailed_to_admins(self):
        import logging
        from django.core import mail
        logging.getLogger("django.request").error("Internal Server Error: /x/")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@clinic.test"])
        self.assertTrue(mail.outbox[0].subject.startswith("[کلینیک] "))

    def test_app_error_is_emailed(self):
        import logging
        from django.core import mail
        logging.getLogger("apps.payments.services").error("refund needed")
        self.assertEqual(len(mail.outbox), 1)

    def test_security_warnings_and_info_are_not_emailed(self):
        import logging
        from django.core import mail
        logging.getLogger("django.security.DisallowedHost").error("Invalid HTTP_HOST header")
        logging.getLogger("apps.payments.services").info("Payment reconciled")
        self.assertEqual(mail.outbox, [])


class AdminJalaliDatesTests(TestCase):
    """تاریخ‌ها در پنل ادمین شمسی نمایش داده شوند (سند: بخش ۶)."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        self.admin = get_user_model().objects.create_superuser(username="admin", password="x")
        self.client.force_login(self.admin)
        import jdatetime
        self.jalali_year = str(jdatetime.date.today().year)

    def test_contact_messages_list_and_detail(self):
        message = ContactMessage.objects.create(name="سارا", phone="09121234567", message="سلام")
        changelist = self.client.get(reverse("admin:core_contactmessage_changelist"))
        self.assertContains(changelist, self.jalali_year)
        detail = self.client.get(reverse("admin:core_contactmessage_change", args=[message.pk]))
        self.assertContains(detail, self.jalali_year)

    def test_user_admin_pages_still_work_with_jalali_dates(self):
        self.assertContains(self.client.get(reverse("admin:accounts_user_changelist")), self.jalali_year)
        change = self.client.get(reverse("admin:accounts_user_change", args=[self.admin.pk]))
        self.assertEqual(change.status_code, 200)
        self.assertContains(change, self.jalali_year)
        self.assertEqual(self.client.get(reverse("admin:accounts_user_add")).status_code, 200)
        # Django نام این مسیر را برای مدل کاربر سفارشی هم auth_user_password_change می‌گذارد
        password_url = reverse("admin:auth_user_password_change", args=[self.admin.pk])
        self.assertEqual(self.client.get(password_url).status_code, 200)

    def test_user_can_still_be_created_and_edited_in_admin(self):
        from django.contrib.auth import get_user_model
        response = self.client.post(reverse("admin:accounts_user_add"), {
            "username": "09129998877", "password1": "Strong-Pass-123", "password2": "Strong-Pass-123",
            "phone_number": "09129998877", "usable_password": "true",
            # inline نشانی پیش‌فرض
            "shipping_address-TOTAL_FORMS": "0", "shipping_address-INITIAL_FORMS": "0",
            "shipping_address-MIN_NUM_FORMS": "0", "shipping_address-MAX_NUM_FORMS": "1",
        })
        errors = response.context["adminform"].form.errors if response.status_code == 200 else None
        self.assertEqual(response.status_code, 302, errors)
        self.assertTrue(get_user_model().objects.filter(username="09129998877").exists())
