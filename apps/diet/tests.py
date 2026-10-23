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

from .models import DietRequest, DietTemplate
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
