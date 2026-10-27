"""اعلان‌های پیامکی نوبت، سفارش و رژیم (apps/core/notifications.py)."""
import json
from datetime import time, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.sms import SMSError
from apps.appointments.models import Appointment, Doctor, DoctorAvailability
from apps.appointments.services import book_appointment, cancel_appointment, cancel_by_clinic, confirm_manual_payment, mark_appointment_paid
from apps.appointments.tests import next_saturday
from apps.core.models import SiteSettings
from apps.shop.models import Order
from apps.shop.services import mark_order_paid
from utils.jalali import format_jalali


class NotificationTests(TestCase):

    def setUp(self):
        self.patient = get_user_model().objects.create_user(username="09120000001", phone_number="09120000001", first_name="سارا")
        self.doctor = Doctor.objects.create(name="Dr", specialty="x", visit_fee=300_000)
        self.slot = DoctorAvailability.objects.create(doctor=self.doctor, day_of_week=0, time=time(10, 0))
        self.date = next_saturday() + timedelta(days=7)
        patcher = mock.patch("apps.accounts.sms.send_template")
        self.send = patcher.start()
        self.addCleanup(patcher.stop)

    def sent(self):
        return [c.args for c in self.send.call_args_list]

    def appointment(self, **extra):
        defaults = dict(availability=self.slot, patient=self.patient, date=self.date, status="pending",
                        fee=300_000, payment_status="unpaid", payment_deadline=timezone.now() + timedelta(minutes=10))
        defaults.update(extra)
        return Appointment.objects.create(**defaults)

    def order(self, status=Order.STATUS_PENDING):
        return Order.objects.create(user=self.patient, status=status, recipient_name="x",
                                    recipient_phone="09121112233", subtotal=1, total=1)

    def test_gateway_payment_confirms_once_with_date_and_time(self):
        appointment = self.appointment()
        with self.captureOnCommitCallbacks(execute=True):
            mark_appointment_paid(appointment)
            mark_appointment_paid(appointment)  # callback تکراری
        self.assertEqual(self.sent(), [
            ("SMS_APPOINTMENT_CONFIRMED_TEMPLATE", "09120000001", "سارا", format_jalali(self.date), "10:00"),
        ])

    def test_free_booking_and_manual_payment_confirm(self):
        self.doctor.visit_fee = 0
        self.doctor.save()
        with self.captureOnCommitCallbacks(execute=True):
            book_appointment(self.patient, self.slot.pk, self.date)
        self.assertEqual(self.sent()[0][0], "SMS_APPOINTMENT_CONFIRMED_TEMPLATE")

        self.send.reset_mock()
        other_date = self.date + timedelta(days=7)
        with self.captureOnCommitCallbacks(execute=True):
            confirm_manual_payment(self.appointment(date=other_date))
        self.assertEqual(len(self.sent()), 1)

    def test_unpaid_booking_sends_nothing(self):
        with self.captureOnCommitCallbacks(execute=True):
            book_appointment(self.patient, self.slot.pk, self.date)
        self.assertEqual(self.sent(), [])

    def test_clinic_cancel_notifies_but_patient_cancel_does_not(self):
        with self.captureOnCommitCallbacks(execute=True):
            cancel_by_clinic(self.appointment(status="confirmed", payment_status="paid"))
        self.assertEqual(self.sent()[0][0], "SMS_APPOINTMENT_CANCELLED_TEMPLATE")

        self.send.reset_mock()
        own = self.appointment(date=self.date + timedelta(days=7))
        with self.captureOnCommitCallbacks(execute=True):
            cancel_appointment(self.patient, own.pk)
        self.assertEqual(self.sent(), [])

    def test_order_paid_once(self):
        order = self.order()
        with self.captureOnCommitCallbacks(execute=True):
            mark_order_paid(order)
            mark_order_paid(order)
        self.assertEqual(self.sent(), [("SMS_ORDER_PAID_TEMPLATE", "09120000001", "سارا", order.pk)])

    def test_order_shipped_from_admin(self):
        admin = get_user_model().objects.create_superuser(username="admin", password="x")
        self.client.force_login(admin)
        order = self.order(status=Order.STATUS_PAID)
        url = reverse("admin:shop_order_change", args=[order.pk])
        data = {
            "recipient_name": "x", "recipient_phone": "09121112233", "province": "", "city": "",
            "address": "", "postal_code": "", "note": "",
            "items-TOTAL_FORMS": "0", "items-INITIAL_FORMS": "0", "items-MIN_NUM_FORMS": "0", "items-MAX_NUM_FORMS": "0",
        }
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {**data, "status": Order.STATUS_PROCESSING})
        self.assertEqual(self.sent(), [])
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {**data, "status": Order.STATUS_SHIPPED})
        self.assertEqual(self.sent(), [("SMS_ORDER_SHIPPED_TEMPLATE", "09120000001", "سارا", order.pk)])

    def test_switch_off_in_site_settings(self):
        site = SiteSettings.load()
        site.phone = "1"
        site.sms_appointment_confirmed = False
        site.save()
        with self.captureOnCommitCallbacks(execute=True):
            mark_appointment_paid(self.appointment())
        self.assertEqual(self.sent(), [])

    def test_no_sms_when_transaction_rolls_back(self):
        appointment = self.appointment()
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    mark_appointment_paid(appointment)
                    raise RuntimeError("later step failed")
            except RuntimeError:
                pass
        self.assertEqual(self.sent(), [])

    def test_sms_failure_does_not_break_payment(self):
        self.send.side_effect = SMSError("down")
        order = self.order()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertTrue(mark_order_paid(order))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PAID)


@override_settings(SMS_BACKEND="apps.accounts.sms.KavenegarSMSBackend", SMS_API_KEY="k",
                   SMS_APPOINTMENT_CONFIRMED_TEMPLATE="appointment-ok")
class KavenegarTokensTests(TestCase):

    def test_three_tokens_sent_without_spaces(self):
        from apps.accounts.sms import send_template

        captured = {}

        class Response:
            def read(self):
                return json.dumps({"return": {"status": 200}}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        def fake_urlopen(request, timeout=None):
            from urllib.parse import parse_qs
            captured.update({k: v[0] for k, v in parse_qs(request.data.decode()).items()})
            return Response()

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            self.assertTrue(send_template("SMS_APPOINTMENT_CONFIRMED_TEMPLATE", "09120000001", "سارا احمدی", "1405/08/10", "10:00"))
        self.assertEqual(captured["template"], "appointment-ok")
        self.assertEqual((captured["token"], captured["token2"], captured["token3"]), ("سارا‌احمدی", "1405/08/10", "10:00"))
