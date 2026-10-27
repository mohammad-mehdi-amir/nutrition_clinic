import json
from datetime import time, timedelta
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.appointments.models import Appointment, Doctor, DoctorAvailability
from apps.appointments.tests import next_saturday
from apps.shop.models import Order, OrderItem, Product
from .models import Payment
from .services import PaymentError, handle_callback, start_payment

MERCHANT = "00000000-0000-0000-0000-000000000000"


class FakeHTTPResponse:
    def __init__(self, body):
        self._body = json.dumps(body).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def zarinpal_router(request_body=None, verify_body=None, calls=None):
    """جایگزین urlopen: بر اساس مسیر، پاسخ request یا verify را برمی‌گرداند."""
    request_body = request_body or {"data": {"code": 100, "authority": "S000000000000000000000000000000abcd"}, "errors": []}
    verify_body = verify_body or {"data": {"code": 100, "ref_id": 201, "card_pan": "502229******5995"}, "errors": []}

    def fake_urlopen(request, timeout=None):
        payload = json.loads(request.data.decode())
        if calls is not None:
            calls.append((request.full_url, payload))
        return FakeHTTPResponse(request_body if request.full_url.endswith("request.json") else verify_body)

    return fake_urlopen


class PaymentTestMixin:

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="09120000000", phone_number="09120000000", password="x")
        self.doctor = Doctor.objects.create(name="Dr", specialty="x", visit_fee=300_000)
        self.slot = DoctorAvailability.objects.create(doctor=self.doctor, day_of_week=0, time=time(10, 0))
        self.date = next_saturday() + timedelta(days=7)

    def make_appointment(self, **extra):
        defaults = dict(
            availability=self.slot, patient=self.user, date=self.date, status="pending",
            fee=300_000, payment_status="unpaid", payment_deadline=timezone.now() + timedelta(minutes=10),
        )
        defaults.update(extra)
        return Appointment.objects.create(**defaults)

    def callback_url(self, payment):
        return f"https://clinic.test/payments/callback/{payment.pk}/"


@override_settings(PAYMENT_GATEWAY="zarinpal", ZARINPAL_MERCHANT_ID=MERCHANT, ZARINPAL_SANDBOX=True)
class ZarinpalFlowTests(PaymentTestMixin, TestCase):

    def test_start_sends_rial_amount_to_sandbox_and_redirects(self):
        appointment = self.make_appointment()
        calls = []
        with mock.patch("urllib.request.urlopen", zarinpal_router(calls=calls)):
            payment, url = start_payment(self.user, appointment, self.callback_url)

        request_url, payload = calls[0]
        self.assertEqual(request_url, "https://sandbox.zarinpal.com/pg/v4/payment/request.json")
        self.assertEqual((payload["amount"], payload["currency"], payload["merchant_id"]), (3_000_000, "IRR", MERCHANT))
        self.assertEqual(payload["callback_url"], self.callback_url(payment))
        self.assertEqual(url, "https://sandbox.zarinpal.com/pg/StartPay/S000000000000000000000000000000abcd")
        self.assertEqual((payment.status, payment.amount), (Payment.STATUS_REDIRECTED, 300_000))

    @override_settings(ZARINPAL_SANDBOX=False)
    def test_production_host(self):
        calls = []
        with mock.patch("urllib.request.urlopen", zarinpal_router(calls=calls)):
            _, url = start_payment(self.user, self.make_appointment(), self.callback_url)
        self.assertTrue(calls[0][0].startswith("https://payment.zarinpal.com/pg/v4/"))
        self.assertTrue(url.startswith("https://payment.zarinpal.com/pg/StartPay/"))

    def test_gateway_rejection_raises_and_marks_failed(self):
        body = {"data": [], "errors": {"code": -10, "message": "Terminal is not valid"}}
        with mock.patch("urllib.request.urlopen", zarinpal_router(request_body=body)):
            with self.assertRaises(PaymentError):
                start_payment(self.user, self.make_appointment(), self.callback_url)
        self.assertEqual(Payment.objects.get().status, Payment.STATUS_FAILED)

    def _paid_flow(self, appointment, verify_body=None):
        calls = []
        with mock.patch("urllib.request.urlopen", zarinpal_router(verify_body=verify_body, calls=calls)):
            payment, _ = start_payment(self.user, appointment, self.callback_url)
            payment = handle_callback(payment.pk, {"Authority": payment.authority, "Status": "OK"})
        return payment, calls

    def test_successful_callback_confirms_appointment(self):
        appointment = self.make_appointment()
        payment, calls = self._paid_flow(appointment)

        verify_url, verify_payload = calls[1]
        self.assertTrue(verify_url.endswith("verify.json"))
        self.assertEqual((verify_payload["amount"], verify_payload["authority"]), (3_000_000, payment.authority))

        self.assertEqual((payment.status, payment.ref_id, payment.card_pan), (Payment.STATUS_PAID, "201", "502229******5995"))
        self.assertFalse(payment.needs_review)
        appointment.refresh_from_db()
        self.assertEqual((appointment.status, appointment.payment_status), ("confirmed", "paid"))

    def test_code_101_is_success(self):
        payment, _ = self._paid_flow(self.make_appointment(), verify_body={"data": {"code": 101, "ref_id": 7}, "errors": []})
        self.assertEqual(payment.status, Payment.STATUS_PAID)

    def test_verify_failure_marks_failed(self):
        body = {"data": [], "errors": {"code": -51, "message": "Session is not valid"}}
        appointment = self.make_appointment()
        payment, _ = self._paid_flow(appointment, verify_body=body)
        self.assertEqual(payment.status, Payment.STATUS_FAILED)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "pending")

    def test_user_cancel_does_not_call_verify(self):
        calls = []
        with mock.patch("urllib.request.urlopen", zarinpal_router(calls=calls)):
            payment, _ = start_payment(self.user, self.make_appointment(), self.callback_url)
            payment = handle_callback(payment.pk, {"Authority": payment.authority, "Status": "NOK"})
        self.assertEqual(payment.status, Payment.STATUS_CANCELLED)
        self.assertEqual(len(calls), 1)

    def test_duplicate_callback_is_idempotent(self):
        calls = []
        with mock.patch("urllib.request.urlopen", zarinpal_router(calls=calls)):
            payment, _ = start_payment(self.user, self.make_appointment(), self.callback_url)
            params = {"Authority": payment.authority, "Status": "OK"}
            handle_callback(payment.pk, params)
            again = handle_callback(payment.pk, params)
        self.assertEqual(again.status, Payment.STATUS_PAID)
        self.assertEqual(len(calls), 2)  # request + یک بار verify

    def test_authority_mismatch_rejected(self):
        with mock.patch("urllib.request.urlopen", zarinpal_router()):
            payment, _ = start_payment(self.user, self.make_appointment(), self.callback_url)
            payment = handle_callback(payment.pk, {"Authority": "S-forged", "Status": "OK"})
        self.assertEqual(payment.status, Payment.STATUS_FAILED)

    def test_network_error_on_verify_keeps_payment_pending(self):
        import urllib.error
        with mock.patch("urllib.request.urlopen", zarinpal_router()):
            payment, _ = start_payment(self.user, self.make_appointment(), self.callback_url)
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            payment = handle_callback(payment.pk, {"Authority": payment.authority, "Status": "OK"})
        self.assertEqual(payment.status, Payment.STATUS_REDIRECTED)

    def test_expired_appointment_reactivated_if_slot_free(self):
        appointment = self.make_appointment()
        with mock.patch("urllib.request.urlopen", zarinpal_router()):
            payment, _ = start_payment(self.user, appointment, self.callback_url)
            Appointment.objects.filter(pk=appointment.pk).update(status="cancelled")
            payment = handle_callback(payment.pk, {"Authority": payment.authority, "Status": "OK"})
        appointment.refresh_from_db()
        self.assertEqual((appointment.status, appointment.payment_status), ("confirmed", "paid"))
        self.assertFalse(payment.needs_review)

    def test_expired_appointment_slot_taken_needs_review(self):
        appointment = self.make_appointment()
        with mock.patch("urllib.request.urlopen", zarinpal_router()):
            payment, _ = start_payment(self.user, appointment, self.callback_url)
            Appointment.objects.filter(pk=appointment.pk).update(status="cancelled")
            other = get_user_model().objects.create_user(username="other")
            Appointment.objects.create(availability=self.slot, patient=other, date=self.date, status="confirmed")
            payment = handle_callback(payment.pk, {"Authority": payment.authority, "Status": "OK"})
        appointment.refresh_from_db()
        self.assertTrue(payment.needs_review)
        self.assertEqual((appointment.status, appointment.payment_status), ("cancelled", "refund_requested"))

    def test_start_extends_deadline_during_payment(self):
        appointment = self.make_appointment(payment_deadline=timezone.now() + timedelta(minutes=1))
        with mock.patch("urllib.request.urlopen", zarinpal_router()):
            start_payment(self.user, appointment, self.callback_url)
        appointment.refresh_from_db()
        self.assertGreater(appointment.payment_deadline, timezone.now() + timedelta(minutes=14))

    def test_cannot_pay_confirmed_or_expired_appointment(self):
        with self.assertRaises(PaymentError):
            start_payment(self.user, self.make_appointment(status="confirmed", payment_status="paid"), self.callback_url)
        Appointment.objects.all().delete()
        with self.assertRaises(PaymentError):
            start_payment(self.user, self.make_appointment(payment_deadline=timezone.now() - timedelta(minutes=1)), self.callback_url)


@override_settings(PAYMENT_GATEWAY="zarinpal", ZARINPAL_MERCHANT_ID=MERCHANT)
class OrderPaymentTests(PaymentTestMixin, TestCase):

    def make_order(self, quantity=2, stock_after=3):
        product = Product.objects.create(product_type="physical", name="p", slug="p", short_description="x", price=100_000, stock=stock_after)
        order = Order.objects.create(
            user=self.user, recipient_name="x", recipient_phone="09120000000",
            subtotal=200_000, total=200_000, payment_deadline=timezone.now() + timedelta(minutes=30),
        )
        OrderItem.objects.create(order=order, product=product, product_name="p", product_type="physical", unit_price=100_000, quantity=quantity, line_total=200_000)
        return order, product

    def test_order_paid(self):
        order, _ = self.make_order()
        with mock.patch("urllib.request.urlopen", zarinpal_router()):
            payment, _ = start_payment(self.user, order, self.callback_url)
            handle_callback(payment.pk, {"Authority": payment.authority, "Status": "OK"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PAID)

    def test_expired_order_restocks_if_possible(self):
        order, product = self.make_order(quantity=2, stock_after=5)
        with mock.patch("urllib.request.urlopen", zarinpal_router()):
            payment, _ = start_payment(self.user, order, self.callback_url)
            Order.objects.filter(pk=order.pk).update(status=Order.STATUS_CANCELLED)  # موجودی قبلاً برگشته
            payment = handle_callback(payment.pk, {"Authority": payment.authority, "Status": "OK"})
        order.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual((order.status, product.stock, payment.needs_review), (Order.STATUS_PAID, 3, False))

    def test_expired_order_without_stock_needs_review(self):
        order, product = self.make_order(quantity=2, stock_after=1)
        with mock.patch("urllib.request.urlopen", zarinpal_router()):
            payment, _ = start_payment(self.user, order, self.callback_url)
            Order.objects.filter(pk=order.pk).update(status=Order.STATUS_CANCELLED)
            payment = handle_callback(payment.pk, {"Authority": payment.authority, "Status": "OK"})
        order.refresh_from_db()
        self.assertTrue(payment.needs_review)
        self.assertEqual(order.status, Order.STATUS_CANCELLED)


@override_settings(PAYMENT_GATEWAY="fake", PAYMENT_ALLOW_FAKE_GATEWAY=True)
class PaymentViewTests(PaymentTestMixin, TestCase):

    def test_pay_appointment_redirects_to_gateway_and_callback_shows_result(self):
        appointment = self.make_appointment()
        self.client.force_login(self.user)

        response = self.client.post(reverse("payments:pay_appointment", args=[appointment.pk]))
        payment = Payment.objects.get()
        self.assertRedirects(response, f"{reverse('payments:fake_gateway', args=[payment.pk])}?authority={payment.authority}")

        self.client.logout()  # بازگشت از درگاه بدون نیاز به session
        result = self.client.get(reverse("payments:callback", args=[payment.pk]), {"Authority": payment.authority, "Status": "OK"})
        self.assertContains(result, "پرداخت موفق")
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "confirmed")

    def test_cannot_pay_someone_elses_appointment(self):
        appointment = self.make_appointment()
        other = get_user_model().objects.create_user(username="other")
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse("payments:pay_appointment", args=[appointment.pk])).status_code, 404)
        self.assertFalse(Payment.objects.exists())

    def test_pay_requires_post(self):
        appointment = self.make_appointment()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("payments:pay_appointment", args=[appointment.pk])).status_code, 405)

    def test_booking_confirmation_goes_straight_to_gateway(self):
        from utils.jalali import format_jalali
        self.client.force_login(self.user)
        date = format_jalali(self.date, "-")
        url = reverse("appointments:confirm_appointment", kwargs={"doctor_id": self.doctor.pk, "date": date})
        response = self.client.post(url, {"availability": self.slot.pk})
        payment = Payment.objects.get()
        self.assertEqual(payment.amount, 300_000)
        self.assertTrue(response["Location"].startswith(reverse("payments:fake_gateway", args=[payment.pk])))

    @override_settings(PAYMENT_ALLOW_FAKE_GATEWAY=False)
    def test_fake_gateway_disabled_without_debug(self):
        appointment = self.make_appointment()
        self.client.force_login(self.user)
        response = self.client.post(reverse("payments:pay_appointment", args=[appointment.pk]), follow=True)
        self.assertContains(response, "درگاه آزمایشی در محیط اصلی فعال نیست")


@override_settings(PAYMENT_GATEWAY="zarinpal", ZARINPAL_MERCHANT_ID=MERCHANT, ZARINPAL_SANDBOX=True,
                   PAYMENT_RECONCILE_AFTER_MINUTES=20, PAYMENT_RECONCILE_GIVE_UP_MINUTES=120)
class ReconcileTests(PaymentTestMixin, TestCase):
    """تراکنش‌هایی که callback آن‌ها نرسیده (کاربر برنگشت / خطای شبکه)."""

    NOT_PAID = {"data": [], "errors": {"code": -51, "message": "Session is not valid"}}

    def abandoned_payment(self, minutes_ago=30, target=None):
        target = target or self.make_appointment()
        authority = f"S{Payment.objects.count():035d}"  # Authority در دیتابیس یکتاست
        request_body = {"data": {"code": 100, "authority": authority}, "errors": []}
        with mock.patch("urllib.request.urlopen", zarinpal_router(request_body=request_body)):
            payment, _ = start_payment(self.user, target, self.callback_url)
        Payment.objects.filter(pk=payment.pk).update(created_at=timezone.now() - timedelta(minutes=minutes_ago))
        return payment

    def reconcile(self, verify_body=None, side_effect=None, calls=None):
        from .services import reconcile_payments
        patch = (mock.patch("urllib.request.urlopen", side_effect=side_effect) if side_effect
                 else mock.patch("urllib.request.urlopen", zarinpal_router(verify_body=verify_body, calls=calls)))
        with patch:
            return reconcile_payments()

    def test_paid_but_user_never_returned_is_confirmed(self):
        payment = self.abandoned_payment()
        calls = []
        counts = self.reconcile(calls=calls)

        self.assertEqual(counts["paid"], 1)
        self.assertTrue(calls[0][0].endswith("verify.json"))
        self.assertEqual(calls[0][1]["amount"], 3_000_000)  # مبلغ از دیتابیس
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.ref_id), (Payment.STATUS_PAID, "201"))
        appointment = payment.appointment
        appointment.refresh_from_db()
        self.assertEqual((appointment.status, appointment.payment_status), ("confirmed", "paid"))

    def test_order_paid_via_reconcile_creates_paid_order(self):
        product = Product.objects.create(product_type="physical", name="p", slug="p", short_description="x", price=100_000, stock=3)
        order = Order.objects.create(user=self.user, recipient_name="x", recipient_phone="09120000000",
                                     subtotal=100_000, total=100_000, payment_deadline=timezone.now() + timedelta(minutes=30))
        OrderItem.objects.create(order=order, product=product, product_name="p", product_type="physical",
                                 unit_price=100_000, quantity=1, line_total=100_000)
        self.abandoned_payment(target=order)
        self.reconcile()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PAID)

    def test_recent_payment_is_not_inquired(self):
        self.abandoned_payment(minutes_ago=5)  # کاربر احتمالاً هنوز در درگاه است
        calls = []
        counts = self.reconcile(calls=calls)
        self.assertEqual(calls, [])
        self.assertEqual(sum(counts.values()), 0)

    def test_unpaid_stays_pending_until_give_up_time(self):
        payment = self.abandoned_payment(minutes_ago=30)
        counts = self.reconcile(verify_body=self.NOT_PAID)
        self.assertEqual(counts["pending"], 1)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS_REDIRECTED)

    def test_unpaid_after_give_up_time_is_failed(self):
        payment = self.abandoned_payment(minutes_ago=180)
        counts = self.reconcile(verify_body=self.NOT_PAID)
        self.assertEqual(counts["failed"], 1)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS_FAILED)
        payment.appointment.refresh_from_db()
        self.assertEqual(payment.appointment.payment_status, "unpaid")

    def test_network_error_never_fails_payment(self):
        import urllib.error
        payment = self.abandoned_payment(minutes_ago=600)
        counts = self.reconcile(side_effect=urllib.error.URLError("down"))
        self.assertEqual(counts["pending"], 1)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS_REDIRECTED)

    def test_callback_after_reconcile_does_not_fulfil_twice(self):
        payment = self.abandoned_payment()
        self.reconcile()
        calls = []
        with mock.patch("urllib.request.urlopen", zarinpal_router(calls=calls)):
            again = handle_callback(payment.pk, {"Authority": payment.authority, "Status": "OK"})
        self.assertEqual(again.status, Payment.STATUS_PAID)
        self.assertEqual(calls, [])  # تراکنش نهایی‌شده دوباره verify نمی‌شود
        self.assertEqual(Payment.objects.filter(status=Payment.STATUS_PAID).count(), 1)

    def test_finished_payments_are_skipped(self):
        payment = self.abandoned_payment()
        Payment.objects.filter(pk=payment.pk).update(status=Payment.STATUS_CANCELLED)
        calls = []
        self.reconcile(calls=calls)
        self.assertEqual(calls, [])

    @override_settings(PAYMENT_GATEWAY="fake", PAYMENT_ALLOW_FAKE_GATEWAY=True)
    def test_abandoned_fake_payment_is_not_treated_as_paid(self):
        payment = start_payment(self.user, self.make_appointment(), self.callback_url)[0]
        Payment.objects.filter(pk=payment.pk).update(created_at=timezone.now() - timedelta(minutes=180))
        from .services import reconcile_payments
        reconcile_payments()
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS_FAILED)

    def test_management_command_and_admin_action(self):
        from io import StringIO
        from django.core.management import call_command
        payment = self.abandoned_payment()
        out = StringIO()
        with mock.patch("urllib.request.urlopen", zarinpal_router()):
            call_command("reconcile_payments", stdout=out)
        self.assertIn("موفق: 1", out.getvalue())

        other = self.abandoned_payment(target=self.make_appointment(date=self.date + timedelta(days=7)))
        admin = get_user_model().objects.create_superuser(username="admin", password="x")
        self.client.force_login(admin)
        with mock.patch("urllib.request.urlopen", zarinpal_router()):
            response = self.client.post(reverse("admin:payments_payment_changelist"), {
                "action": "inquire_from_gateway", "_selected_action": [str(other.pk), str(payment.pk)],
            }, follow=True)
        self.assertContains(response, "1 تراکنش استعلام شد: 1 موفق")
        other.refresh_from_db()
        self.assertEqual(other.status, Payment.STATUS_PAID)
