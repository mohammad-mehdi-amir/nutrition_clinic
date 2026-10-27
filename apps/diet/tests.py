from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.shop.models import Order, OrderItem, Product
from apps.shop.services import mark_order_paid
from utils.validators import validate_pdf

from .models import BodyMeasurement, DietRequest, DietTemplate, HealthProfile, PatientDiet
from .services import create_requests_for_order

PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def pdf_file(name="diet.pdf", content=PDF_BYTES):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def make_user(username="09120000001", **extra):
    return get_user_model().objects.create_user(username=username, phone_number=username, password="pass12345", **extra)


def make_order(user, *, package=True, physical=False, status=Order.STATUS_PENDING):
    order = Order.objects.create(
        user=user, status=status, recipient_name="x", recipient_phone="09121112233", subtotal=1, total=1,
    )
    if package:
        product = Product.objects.create(
            product_type=Product.TYPE_PACKAGE, name="پکیج یک‌ماهه", slug=f"pkg-{order.pk}",
            short_description="x", price=1, duration_days=30,
        )
        OrderItem.objects.create(
            order=order, product=product, product_name=product.name, product_type=Product.TYPE_PACKAGE,
            unit_price=1, quantity=1, line_total=1,
        )
    if physical:
        product = Product.objects.create(
            product_type=Product.TYPE_PHYSICAL, name="مکمل", slug=f"phy-{order.pk}",
            short_description="x", price=1, stock=5,
        )
        OrderItem.objects.create(
            order=order, product=product, product_name=product.name, product_type=Product.TYPE_PHYSICAL,
            unit_price=1, quantity=1, line_total=1,
        )
    return order


class DietRequestCreationTests(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_paying_an_order_creates_one_request_per_package(self):
        order = make_order(self.user, physical=True)

        self.assertTrue(mark_order_paid(order))

        request = DietRequest.objects.get()
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.package_name, "پکیج یک‌ماهه")
        self.assertEqual(request.status, DietRequest.STATUS_PENDING)

    def test_repeated_callback_does_not_duplicate_request(self):
        order = make_order(self.user)
        mark_order_paid(order)
        mark_order_paid(order)
        self.assertEqual(DietRequest.objects.count(), 1)

    def test_order_without_package_creates_no_request(self):
        mark_order_paid(make_order(self.user, package=False, physical=True))
        self.assertFalse(DietRequest.objects.exists())

    def test_payment_that_cannot_be_applied_creates_no_request(self):
        # سفارش منقضی‌شده‌ای که موجودی کالای فیزیکی‌اش دیگر کافی نیست ⇒ نیاز به بازپرداخت، نه رژیم
        order = make_order(self.user, physical=True, status=Order.STATUS_CANCELLED)
        Product.objects.filter(product_type=Product.TYPE_PHYSICAL).update(stock=0)

        self.assertFalse(mark_order_paid(order))
        self.assertFalse(DietRequest.objects.exists())

    def test_create_requests_for_order_is_idempotent(self):
        order = make_order(self.user, status=Order.STATUS_PAID)
        self.assertEqual(len(create_requests_for_order(order)), 1)
        self.assertEqual(create_requests_for_order(order), [])

    def test_admin_marking_order_paid_creates_request(self):
        admin = make_user("09120000009", is_staff=True, is_superuser=True)
        order = make_order(self.user)
        self.client.force_login(admin)

        response = self.client.post(
            reverse("admin:shop_order_change", args=[order.pk]),
            {
                "status": Order.STATUS_PAID,
                "recipient_name": "x", "recipient_phone": "09121112233",
                "province": "", "city": "", "address": "", "postal_code": "", "note": "",
                "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "1",
                "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "0",
                "items-0-id": str(order.items.get().pk), "items-0-order": str(order.pk),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(DietRequest.objects.filter(user=self.user).count(), 1)


class PdfValidationTests(TestCase):

    def test_accepts_real_pdf(self):
        validate_pdf(pdf_file())

    def test_rejects_non_pdf_content_even_with_pdf_extension(self):
        with self.assertRaises(ValidationError):
            validate_pdf(pdf_file(content=b"<html>not a pdf</html>"))

    def test_rejects_oversized_file(self):
        with self.settings(MAX_PDF_UPLOAD_SIZE=10):
            with self.assertRaises(ValidationError):
                validate_pdf(pdf_file())


class PrivateStorageTests(TestCase):

    def setUp(self):
        self.template = DietTemplate.objects.create(title="رژیم ۱۵۰۰ کالری", file=pdf_file("سارا احمدی.pdf"))

    def test_file_is_stored_outside_public_media_with_random_name(self):
        path = self.template.file.path
        self.assertTrue(path.startswith(str(settings.PRIVATE_MEDIA_ROOT.resolve())))
        self.assertNotIn(str(settings.MEDIA_ROOT), path)
        self.assertNotIn("سارا", self.template.file.name)
        self.assertTrue(self.template.file.name.endswith(".pdf"))

    def test_file_url_points_to_protected_view(self):
        self.assertEqual(
            self.template.file.url,
            reverse("diet:staff_file", kwargs={"path": self.template.file.name}),
        )

    def test_staff_file_requires_permission(self):
        url = self.template.file.url

        self.assertEqual(self.client.get(url).status_code, 302)  # مهمان ⇒ صفحه‌ی ورود ادمین

        patient = make_user("09120000002")
        self.client.force_login(patient)
        self.assertEqual(self.client.get(url).status_code, 302)  # غیر کارمند

        staff = make_user("09120000003", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 403)  # کارمند بدون مجوز رژیم

        staff.user_permissions.add(Permission.objects.get(codename="view_diettemplate"))
        staff = get_user_model().objects.get(pk=staff.pk)
        self.client.force_login(staff)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), PDF_BYTES)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_staff_file_rejects_paths_not_owned_by_a_record(self):
        admin = make_user("09120000004", is_staff=True, is_superuser=True)
        self.client.force_login(admin)
        url = reverse("diet:staff_file", kwargs={"path": "../config/settings.py"})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_nginx_mode_returns_accel_redirect_only(self):
        admin = make_user("09120000005", is_staff=True, is_superuser=True)
        self.client.force_login(admin)
        with self.settings(PRIVATE_MEDIA_SERVE="nginx"):
            response = self.client.get(self.template.file.url)
        self.assertEqual(response["X-Accel-Redirect"], "/protected-media/" + self.template.file.name)
        self.assertEqual(response.content, b"")


class HealthCalculationTests(TestCase):

    def test_bmi_and_category(self):
        from .services import bmi_category, calculate_bmi
        self.assertEqual(calculate_bmi(70, 175), 22.9)
        self.assertEqual(bmi_category(17.9)[0], "کمبود وزن")
        self.assertEqual(bmi_category(22.9)[0], "وزن طبیعی")
        self.assertEqual(bmi_category(25)[0], "اضافه‌وزن")
        self.assertEqual(bmi_category(31)[0], "چاقی")

    def test_healthy_range_bmr_tdee_water_whtr(self):
        from .services import calculate_bmr, calculate_tdee, daily_water_liters, healthy_weight_range, waist_to_height
        self.assertEqual(healthy_weight_range(170), (53.5, 72.0))
        # Mifflin-St Jeor: مرد ۸۰kg، ۱۸۰cm، ۳۰ سال ⇒ ۱۷۸۰؛ زن ۶۰kg، ۱۶۵cm، ۲۵ سال ⇒ ۱۳۴۵
        self.assertEqual(calculate_bmr(80, 180, 30, "male"), 1780)
        self.assertEqual(calculate_bmr(60, 165, 25, "female"), 1345)
        self.assertEqual(calculate_tdee(1780, "moderate"), 2760)
        self.assertEqual(daily_water_liters(70), 2.3)
        self.assertEqual(waist_to_height(80, 170)[1], "مطلوب")
        self.assertEqual(waist_to_height(95, 170)[1], "افزایش خطر")
        self.assertEqual(waist_to_height(110, 170)[1], "خطر بالا")


class HealthProfileTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.url = reverse("diet:health_profile")

    def post_profile(self, **overrides):
        data = {
            "sex": "female", "birth_date": "۱۳۷۵/۰۳/۱۰", "height_cm": "۱۶۵", "activity_level": "light",
            "goal": "lose", "target_weight_kg": "60", "weight_kg": "۷۲٫۵", "waist_cm": "88",
            "medical_conditions": "کم‌کاری تیروئید", "medications": "", "allergies": "لاکتوز",
            "food_preferences": "", "consent": "on",
        }
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_stats_are_empty_without_data(self):
        from .services import get_health_stats
        stats = get_health_stats(self.user)
        self.assertIsNone(stats["bmi"])
        self.assertFalse(stats["is_complete"])
        self.assertIn("وزن", stats["missing"])

    def test_saving_profile_with_persian_digits_records_weight(self):
        response = self.post_profile()
        self.assertRedirects(response, reverse("accounts:dashboard"))

        profile = self.user.health_profile
        self.assertEqual(profile.height_cm, 165)
        self.assertEqual(str(profile.birth_date), "1996-05-30")
        self.assertIsNotNone(profile.consent_at)
        self.assertEqual(str(self.user.body_measurements.get().weight_kg), "72.5")

        from .services import get_health_stats, is_profile_complete
        stats = get_health_stats(self.user)
        self.assertTrue(is_profile_complete(self.user))
        self.assertEqual(stats["bmi"]["value"], 26.6)
        self.assertEqual(stats["target_diff"], 12.5)
        self.assertIsNotNone(stats["tdee"])
        self.assertIsNotNone(stats["whtr"])

    def test_all_fields_optional_but_consent_required(self):
        response = self.client.post(self.url, {"consent": "on"})
        self.assertEqual(response.status_code, 302)

        response = self.client.post(self.url, {"height_cm": "170"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("consent", response.context["form"].errors)

    def test_unchanged_weight_does_not_add_history_row(self):
        self.post_profile()
        self.post_profile(medications="ویتامین D")
        self.assertEqual(self.user.body_measurements.count(), 1)
        self.post_profile(weight_kg="70")
        self.assertEqual(self.user.body_measurements.count(), 2)

    def test_invalid_values_rejected(self):
        response = self.post_profile(height_cm="40", weight_kg="900")
        form = response.context["form"]
        self.assertIn("height_cm", form.errors)
        self.assertIn("weight_kg", form.errors)

    def test_quick_weight_entry_and_chart(self):
        url = reverse("diet:add_measurement")
        self.client.post(url, {"weight_kg": "80"})
        self.client.post(url, {"weight_kg": "78.5", "next": "https://evil.example/"})
        self.assertEqual(self.user.body_measurements.count(), 2)

        from .services import get_health_stats
        stats = get_health_stats(self.user)
        self.assertEqual(stats["weight_change"], -1.5)
        self.assertEqual(len(stats["chart"]["dots"]), 2)

    def test_quick_weight_rejects_open_redirect(self):
        response = self.client.post(reverse("diet:add_measurement"), {"weight_kg": "80", "next": "https://evil.example/"})
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)

    def test_profile_and_measurements_are_private(self):
        other = make_user("09120000077")
        self.post_profile()
        self.client.force_login(other)
        response = self.client.get(self.url)
        self.assertEqual(response.context["form"].instance.pk, None)
        self.assertEqual(list(response.context["measurements"]), [])

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.post(reverse("diet:add_measurement"), {"weight_kg": "80"})
        self.assertFalse(BodyMeasurement.objects.exists())


class HealthNoticeTests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.dashboard = reverse("accounts:dashboard")

    def test_notice_shown_and_dismissible(self):
        self.assertContains(self.client.get(self.dashboard), "تکمیل پروفایل</a>")
        self.client.post(reverse("diet:dismiss_health_notice"), {"next": self.dashboard})
        self.assertNotContains(self.client.get(self.dashboard), "پروفایل سلامت خود را تکمیل کنید")

    def test_notice_cannot_be_dismissed_while_diet_pending(self):
        mark_order_paid(make_order(self.user))
        self.client.post(reverse("diet:dismiss_health_notice"))
        self.assertContains(self.client.get(self.dashboard), "در حال آماده‌سازی رژیم شماست")

    def test_notice_hidden_when_profile_complete(self):
        HealthProfile.objects.create(
            user=self.user, sex="male", birth_date="1990-01-01", height_cm=180, activity_level="light", goal="lose",
        )
        BodyMeasurement.objects.create(user=self.user, weight_kg=80)
        response = self.client.get(self.dashboard)
        self.assertNotContains(response, "پروفایل سلامت خود را تکمیل کنید")
        self.assertContains(response, "24.7")  # BMI


class DeliveryServiceTests(TestCase):

    def setUp(self):
        self.user = make_user(first_name="سارا")
        mark_order_paid(make_order(self.user))
        self.request = DietRequest.objects.get()
        self.template = DietTemplate.objects.create(title="رژیم ۱۵۰۰ کالری", file=pdf_file())

    def test_deliver_from_template_copies_file(self):
        from .services import deliver_diet
        with self.captureOnCommitCallbacks(execute=True):
            diet = deliver_diet(self.request, template=self.template)

        self.request.refresh_from_db()
        self.assertEqual(self.request.status, DietRequest.STATUS_DELIVERED)
        self.assertIsNotNone(self.request.delivered_at)
        self.assertEqual(diet.title, "رژیم ۱۵۰۰ کالری")
        self.assertNotEqual(diet.file.name, self.template.file.name)
        with diet.file.open("rb") as f:
            self.assertEqual(f.read(), PDF_BYTES)

        # حذف رژیم آماده و فایلش، نسخه‌ی بیمار را از بین نمی‌برد
        self.template.file.delete(save=False)
        self.template.delete()
        diet.refresh_from_db()
        self.assertIsNone(diet.template)
        self.assertTrue(diet.file.storage.exists(diet.file.name))

    def test_deliver_uploaded_file(self):
        from .services import deliver_diet
        diet = deliver_diet(self.request, title="رژیم اختصاصی", uploaded_file=pdf_file(), note="روزی ۸ لیوان آب")
        self.assertEqual(diet.note, "روزی ۸ لیوان آب")
        self.assertTrue(diet.file.name.startswith("patient_diets/"))

    def test_exactly_one_source_required(self):
        from .services import DeliveryError, deliver_diet
        with self.assertRaises(DeliveryError):
            deliver_diet(self.request, title="x")
        with self.assertRaises(DeliveryError):
            deliver_diet(self.request, title="x", template=self.template, uploaded_file=pdf_file())
        with self.assertRaises(DeliveryError):
            deliver_diet(self.request, uploaded_file=pdf_file())  # بدون عنوان

    def test_sms_sent_after_commit_and_failure_does_not_break_delivery(self):
        from unittest import mock
        from apps.accounts.sms import SMSError
        from .services import deliver_diet

        with mock.patch("apps.accounts.sms.send_template") as send:
            with self.captureOnCommitCallbacks(execute=True):
                deliver_diet(self.request, template=self.template)
        send.assert_called_once_with("SMS_DIET_READY_TEMPLATE", "09120000001", "سارا")

        with mock.patch("apps.accounts.sms.send_template", side_effect=SMSError("down")):
            with self.captureOnCommitCallbacks(execute=True):
                deliver_diet(self.request, template=self.template)
        self.assertEqual(self.request.diets.count(), 2)

    def test_diet_ready_sms_skipped_without_template_on_real_backend(self):
        from unittest import mock
        from apps.accounts.sms import send_template
        with self.settings(SMS_BACKEND="apps.accounts.sms.KavenegarSMSBackend", SMS_DIET_READY_TEMPLATE=""):
            with mock.patch("urllib.request.urlopen") as urlopen:
                self.assertFalse(send_template("SMS_DIET_READY_TEMPLATE", "09120000001", "سارا"))
            urlopen.assert_not_called()

    def test_lookup_token_has_no_spaces(self):
        from apps.accounts.sms import lookup_token
        self.assertEqual(lookup_token("سارا احمدی"), "سارا‌احمدی")
        self.assertEqual(lookup_token(""), "مراجع")


class DietAdminTests(TestCase):

    def setUp(self):
        self.admin = make_user("09120000010", is_staff=True, is_superuser=True)
        self.patient = make_user()
        mark_order_paid(make_order(self.patient))
        self.request = DietRequest.objects.get()
        self.template = DietTemplate.objects.create(title="رژیم کاهش وزن", calories=1600, file=pdf_file())
        self.client.force_login(self.admin)
        self.url = reverse("admin:diet_dietrequest_change", args=[self.request.pk])

    def post_delivery(self, **delivery):
        data = {
            "doctor": "", "staff_note": "",
            "diets-TOTAL_FORMS": "1", "diets-INITIAL_FORMS": "0", "diets-MIN_NUM_FORMS": "0", "diets-MAX_NUM_FORMS": "1000",
            "diets-0-template": "", "diets-0-title": "", "diets-0-note": "",
        }
        data.update({f"diets-0-{k}": v for k, v in delivery.items()})
        return self.client.post(self.url, data)

    def test_queue_and_change_page_render(self):
        HealthProfile.objects.create(user=self.patient, height_cm=170, allergies="لاکتوز")
        self.assertContains(self.client.get(reverse("admin:diet_dietrequest_changelist")), "پکیج یک‌ماهه")
        response = self.client.get(self.url)
        self.assertContains(response, "لاکتوز")
        self.assertContains(response, "رژیم کاهش وزن")  # در فهرست رژیم‌های آماده

    def test_deliver_by_choosing_template(self):
        response = self.post_delivery(template=str(self.template.pk))
        self.assertEqual(response.status_code, 302)
        diet = self.request.diets.get()
        self.assertEqual(diet.title, "رژیم کاهش وزن")
        self.assertEqual(diet.delivered_by, self.admin)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, DietRequest.STATUS_DELIVERED)

    def test_deliver_by_upload(self):
        response = self.post_delivery(title="رژیم اختصاصی سارا", file=pdf_file())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.request.diets.get().title, "رژیم اختصاصی سارا")

    def test_both_or_neither_source_rejected(self):
        response = self.post_delivery(template=str(self.template.pk), title="x", file=pdf_file())
        self.assertEqual(response.status_code, 200)
        response = self.post_delivery(title="فقط عنوان")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PatientDiet.objects.exists())

    def test_upload_requires_title_and_real_pdf(self):
        self.assertEqual(self.post_delivery(file=pdf_file()).status_code, 200)
        self.assertEqual(self.post_delivery(title="x", file=pdf_file(content=b"MZ fake")).status_code, 200)
        self.assertFalse(PatientDiet.objects.exists())

    def test_empty_inline_just_saves_request(self):
        response = self.post_delivery()
        self.assertEqual(response.status_code, 302)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, DietRequest.STATUS_PENDING)

    def test_requests_cannot_be_added_or_deleted_manually(self):
        self.assertEqual(self.client.get(reverse("admin:diet_dietrequest_add")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:diet_dietrequest_delete", args=[self.request.pk])).status_code, 403)

    def test_template_admin_records_creator(self):
        self.client.post(
            reverse("admin:diet_diettemplate_add"),
            {"title": "رژیم گیاهی", "goal": "", "calories": "", "description": "", "file": pdf_file(), "is_active": "on"},
        )
        self.assertEqual(DietTemplate.objects.get(title="رژیم گیاهی").created_by, self.admin)


class MyDietsTests(TestCase):

    def setUp(self):
        from .services import deliver_diet
        self.user = make_user()
        mark_order_paid(make_order(self.user))
        mark_order_paid(make_order(self.user))  # دومی هنوز در انتظار
        first, self.pending = DietRequest.objects.order_by("created_at")
        self.diet = deliver_diet(first, title="رژیم ماه اول", uploaded_file=pdf_file(), note="شام سبک باشد")
        self.client.force_login(self.user)

    def test_page_lists_delivered_and_pending(self):
        response = self.client.get(reverse("diet:my_diets"))
        self.assertContains(response, "رژیم ماه اول")
        self.assertContains(response, "شام سبک باشد")
        self.assertContains(response, reverse("diet:download", args=[self.diet.pk]))
        self.assertContains(response, "در حال آماده‌سازی")
        self.assertNotContains(response, "منقضی")

    def test_owner_downloads_forever(self):
        from datetime import timedelta
        from django.utils import timezone
        # حتی سال‌ها بعد از پایان مدت برنامه
        Order.objects.update(paid_at=timezone.now() - timedelta(days=3650))
        response = self.client.get(reverse("diet:download", args=[self.diet.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), PDF_BYTES)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])

    def test_other_user_and_guest_cannot_download(self):
        url = reverse("diet:download", args=[self.diet.pk])
        self.client.force_login(make_user("09120000099"))
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotContains(self.client.get(reverse("diet:my_diets")), "رژیم ماه اول")
        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_private_file_not_reachable_via_media_url(self):
        response = self.client.get("/media/" + self.diet.file.name)
        self.assertEqual(response.status_code, 404)

    def test_old_packages_url_redirects(self):
        response = self.client.get(reverse("accounts:packages"))
        self.assertRedirects(response, reverse("diet:my_diets"), status_code=301)

    def test_dashboard_tile_counts(self):
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.context["diets_count"], 1)
        self.assertEqual(response.context["pending_diet_requests"], 1)

    def test_robots_blocks_diet_pages(self):
        self.assertContains(self.client.get("/robots.txt"), "Disallow: /diet/")
