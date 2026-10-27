from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from utils.jalali import format_jalali
from .forms import AppointmentDateForm
from .models import Appointment, Doctor, DoctorAvailability
from .services import (
    book_appointment,
    cancel_appointment,
    expire_pending_appointments,
    get_available_slots,
)


def next_saturday():
    today = timezone.localdate()
    # weekday پایتون: شنبه = 5
    return today + timedelta(days=(5 - today.weekday()) % 7 or 7)


class AppointmentServiceTests(TestCase):

    def setUp(self):
        self.patient = get_user_model().objects.create_user(
            username="patient",
            password="pass",
        )
        self.doctor = Doctor.objects.create(
            name="Dr", specialty="Nutrition", visit_fee=300_000
        )
        # 0 = شنبه
        self.saturday_slot = DoctorAvailability.objects.create(
            doctor=self.doctor, day_of_week=0, time=time(10, 0)
        )
        self.saturday = next_saturday()

    def test_day_of_week_for_saturday(self):
        self.assertEqual(
            DoctorAvailability.day_of_week_for(date(2026, 10, 17)),  # شنبه
            0,
        )

    def test_saturday_slot_shown_on_saturday(self):
        slots = get_available_slots(self.doctor, self.saturday)
        self.assertEqual(
            [s["availability"] for s in slots],
            [self.saturday_slot],
        )

    def test_saturday_slot_not_shown_on_thursday(self):
        thursday = self.saturday + timedelta(days=5)
        self.assertEqual(get_available_slots(self.doctor, thursday), [])

    def test_book_sets_payment_deadline_from_settings(self):
        appointment = book_appointment(
            self.patient, self.saturday_slot.id, self.saturday
        )
        remaining = appointment.payment_deadline - timezone.now()
        self.assertGreater(remaining, timedelta(minutes=9))

    def test_double_booking_rejected(self):
        book_appointment(self.patient, self.saturday_slot.id, self.saturday)
        other = get_user_model().objects.create_user(username="other")
        with self.assertRaises(ValueError):
            book_appointment(other, self.saturday_slot.id, self.saturday)

    def test_cancelled_slot_can_be_rebooked(self):
        appointment = book_appointment(
            self.patient, self.saturday_slot.id, self.saturday
        )
        appointment.status = "cancelled"
        appointment.save()
        book_appointment(self.patient, self.saturday_slot.id, self.saturday)

    def test_expired_pending_is_cancelled(self):
        appointment = book_appointment(
            self.patient, self.saturday_slot.id, self.saturday
        )
        Appointment.objects.filter(id=appointment.id).update(
            payment_deadline=timezone.now() - timedelta(seconds=1)
        )
        expire_pending_appointments()
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "cancelled")

    def test_cannot_cancel_past_appointment(self):
        past_saturday = self.saturday - timedelta(days=7)
        appointment = Appointment.objects.create(
            availability=self.saturday_slot,
            patient=self.patient,
            date=past_saturday,
            status="confirmed",
        )
        with self.assertRaises(ValueError):
            cancel_appointment(self.patient, appointment.id)

    def test_can_cancel_future_confirmed(self):
        appointment = Appointment.objects.create(
            availability=self.saturday_slot,
            patient=self.patient,
            date=self.saturday + timedelta(days=7),
            status="confirmed",
        )
        cancel_appointment(self.patient, appointment.id)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "cancelled")


class BookAppointmentViewTests(TestCase):

    def test_redirect_uses_jalali_date(self):
        user = get_user_model().objects.create_user(
            username="patient", password="pass"
        )
        doctor = Doctor.objects.create(name="Dr", specialty="Nutrition")
        self.client.force_login(user)

        saturday = next_saturday()
        jalali = format_jalali(saturday, "-")

        response = self.client.post(
            reverse("appointments:book_appointment"),
            {"doctor": doctor.id, "date": jalali},
        )

        self.assertRedirects(
            response,
            reverse(
                "appointments:select_time",
                kwargs={"doctor_id": doctor.id, "date": jalali},
            ),
            fetch_redirect_response=False,
        )


class AdminScheduleTests(TestCase):

    def setUp(self):
        self.doctor = Doctor.objects.create(name="Dr", specialty="Nutrition")
        self.base_url = reverse("admin:appointments_doctor_schedule")
        self.url = f"{self.base_url}?doctor={self.doctor.pk}"

    def _staff(self, **extra):
        return get_user_model().objects.create_user(
            username="staff", password="pass", is_staff=True, **extra
        )

    def test_superuser_saves_schedule(self):
        old = DoctorAvailability.objects.create(doctor=self.doctor, day_of_week=1, time=time(9, 0))
        self.client.force_login(self._staff(is_superuser=True))

        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "برنامه کاری پزشک")
        self.assertContains(page, 'name="slots"')

        self.client.post(self.base_url, {"doctor": self.doctor.pk, "slots": ["0_10:00", "0_10:30"]})

        old.refresh_from_db()
        self.assertFalse(old.is_active)
        self.assertEqual(
            set(self.doctor.availabilities.filter(is_active=True).values_list("day_of_week", "time")),
            {(0, time(10, 0)), (0, time(10, 30))},
        )

    def test_warns_about_future_appointments_on_deactivated_slots(self):
        slot = DoctorAvailability.objects.create(doctor=self.doctor, day_of_week=0, time=time(10, 0))
        patient = get_user_model().objects.create_user(username="p")
        Appointment.objects.create(availability=slot, patient=patient, date=next_saturday(), status="confirmed")
        self.client.force_login(self._staff(is_superuser=True))

        response = self.client.post(self.base_url, {"doctor": self.doctor.pk, "slots": []}, follow=True)

        self.assertContains(response, "1 نوبت آینده")
        self.assertEqual(Appointment.objects.get().status, "confirmed")

    def test_page_without_doctor_shows_selector_only(self):
        self.client.force_login(self._staff(is_superuser=True))
        page = self.client.get(self.base_url)
        self.assertContains(page, 'id="doctor"')
        self.assertContains(page, "Dr")
        self.assertNotContains(page, 'name="slots"')

    def test_staff_without_permission_denied(self):
        self.client.force_login(self._staff())
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_non_staff_redirected_to_admin_login(self):
        user = get_user_model().objects.create_user(username="u", password="pass")
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])


class AppointmentDateFormTests(TestCase):

    def setUp(self):
        self.doctor = Doctor.objects.create(name="Dr", specialty="Nutrition")

    def test_accepts_slash_dash_and_persian_digits(self):
        expected = date(2026, 10, 7)  # 1405/07/15
        for raw in ["1405/07/15", "1405-07-15", "۱۴۰۵/۰۷/۱۵"]:
            with self.subTest(raw=raw):
                form = AppointmentDateForm({"doctor": self.doctor.pk, "date": raw})
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data["date"], expected)

    def test_rejects_inactive_doctor(self):
        self.doctor.is_active = False
        self.doctor.save()
        form = AppointmentDateForm({"doctor": self.doctor.pk, "date": "1405/07/15"})
        self.assertFalse(form.is_valid())
        self.assertIn("doctor", form.errors)



class FeeAndCancellationTests(TestCase):

    def setUp(self):
        from apps.core.models import SiteSettings
        self.settings = SiteSettings.objects.create(
            clinic_name="c", phone="1", default_visit_fee=150_000, cancellation_deadline_hours=12
        )
        self.patient = get_user_model().objects.create_user(username="patient", password="pass")
        self.doctor = Doctor.objects.create(name="Dr", specialty="Nutrition")
        self.slot = DoctorAvailability.objects.create(doctor=self.doctor, day_of_week=0, time=time(10, 0))
        self.saturday = next_saturday() + timedelta(days=7)

    def test_fee_falls_back_to_site_default(self):
        self.assertEqual(self.doctor.get_visit_fee(), 150_000)
        self.doctor.visit_fee = 0
        self.assertEqual(self.doctor.get_visit_fee(), 0)

    def test_paid_booking_snapshots_fee_and_waits_for_payment(self):
        appointment = book_appointment(self.patient, self.slot.id, self.saturday)
        self.assertEqual((appointment.status, appointment.payment_status, appointment.fee), ("pending", "unpaid", 150_000))
        self.assertIsNotNone(appointment.payment_deadline)
        self.assertEqual(appointment.start_time, time(10, 0))

    def test_free_booking_is_confirmed_immediately(self):
        self.doctor.visit_fee = 0
        self.doctor.save()
        appointment = book_appointment(self.patient, self.slot.id, self.saturday)
        self.assertEqual((appointment.status, appointment.payment_status), ("confirmed", "not_required"))
        self.assertIsNone(appointment.payment_deadline)

    def test_patient_time_conflict_enforced_by_database(self):
        from django.db import IntegrityError, transaction
        other_doctor = Doctor.objects.create(name="Dr2", specialty="x")
        other_slot = DoctorAvailability.objects.create(doctor=other_doctor, day_of_week=0, time=time(10, 0))
        Appointment.objects.create(availability=self.slot, patient=self.patient, date=self.saturday, status="confirmed")
        with transaction.atomic(), self.assertRaises(IntegrityError):
            Appointment.objects.create(availability=other_slot, patient=self.patient, date=self.saturday, status="pending")

    def test_concurrent_booking_race_returns_friendly_error(self):
        """بین بررسی اولیه و ثبت، شخص دیگری همان اسلات را می‌گیرد ⇒ IntegrityError ⇒ پیام مناسب."""
        from unittest import mock
        other = get_user_model().objects.create_user(username="other")
        with mock.patch("apps.appointments.services.validate_slot", return_value=self.slot):
            Appointment.objects.create(availability=self.slot, patient=other, date=self.saturday, status="pending")
            with self.assertRaisesMessage(ValueError, "هم‌اکنون رزرو شد"):
                book_appointment(self.patient, self.slot.id, self.saturday)

    def _appointment(self, days_ahead=None, hours_ahead=None, **extra):
        start = timezone.localtime() + (timedelta(hours=hours_ahead) if hours_ahead is not None else timedelta(days=days_ahead))
        slot = DoctorAvailability.objects.create(
            doctor=self.doctor, day_of_week=DoctorAvailability.day_of_week_for(start.date()), time=start.time().replace(second=0, microsecond=0)
        )
        return Appointment.objects.create(availability=slot, patient=self.patient, date=start.date(), status="confirmed", **extra)

    def test_cannot_cancel_within_deadline(self):
        appointment = self._appointment(hours_ahead=6)
        with self.assertRaisesMessage(ValueError, "12 ساعت"):
            cancel_appointment(self.patient, appointment.id)

    def test_can_cancel_before_deadline_and_paid_becomes_refund_request(self):
        appointment = self._appointment(days_ahead=3, fee=150_000, payment_status="paid", paid_amount=150_000)
        cancel_appointment(self.patient, appointment.id)
        appointment.refresh_from_db()
        self.assertEqual((appointment.status, appointment.payment_status), ("cancelled", "refund_requested"))

    def test_pending_unpaid_can_be_cancelled(self):
        appointment = book_appointment(self.patient, self.slot.id, self.saturday)
        cancel_appointment(self.patient, appointment.id)
        appointment.refresh_from_db()
        self.assertEqual((appointment.status, appointment.payment_status), ("cancelled", "unpaid"))

    def test_expire_command(self):
        from django.core.management import call_command
        from io import StringIO
        appointment = book_appointment(self.patient, self.slot.id, self.saturday)
        Appointment.objects.filter(pk=appointment.pk).update(payment_deadline=timezone.now() - timedelta(minutes=1))
        out = StringIO()
        call_command("expire_pending_appointments", stdout=out)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "cancelled")
        self.assertIn("1", out.getvalue())

    def test_admin_actions_confirm_payment_and_refund(self):
        from .services import confirm_manual_payment, mark_refunded
        appointment = book_appointment(self.patient, self.slot.id, self.saturday)
        confirm_manual_payment(appointment)
        appointment.refresh_from_db()
        self.assertEqual((appointment.status, appointment.payment_status), ("confirmed", "paid"))

        cancel_appointment(self.patient, appointment.id)
        mark_refunded(appointment)
        appointment.refresh_from_db()
        self.assertEqual(appointment.payment_status, "refunded")
        with self.assertRaises(ValueError):
            confirm_manual_payment(appointment)


class ConfirmFlowTests(TestCase):

    def setUp(self):
        self.patient = get_user_model().objects.create_user(username="patient", password="pass")
        self.client.force_login(self.patient)
        self.doctor = Doctor.objects.create(name="دکتر نمونه", specialty="تغذیه", visit_fee=250_000)
        self.slot = DoctorAvailability.objects.create(doctor=self.doctor, day_of_week=0, time=time(10, 0))
        self.date = format_jalali(next_saturday() + timedelta(days=7), "-")
        self.select_url = reverse("appointments:select_time", kwargs={"doctor_id": self.doctor.id, "date": self.date})
        self.confirm_url = reverse("appointments:confirm_appointment", kwargs={"doctor_id": self.doctor.id, "date": self.date})

    def test_select_time_redirects_to_summary_without_booking(self):
        response = self.client.post(self.select_url, {"availability": self.slot.id})
        self.assertRedirects(response, f"{self.confirm_url}?availability={self.slot.id}")
        self.assertFalse(Appointment.objects.exists())

    def test_summary_shows_fee_then_books(self):
        page = self.client.get(self.confirm_url, {"availability": self.slot.id})
        self.assertContains(page, "250,000 تومان")
        self.assertContains(page, "10:00")

        response = self.client.post(self.confirm_url, {"availability": self.slot.id, "accept_terms": "on"})
        self.assertRedirects(response, reverse("appointments:my_appointments"))
        self.assertEqual(Appointment.objects.get().fee, 250_000)

    def test_invalid_availability_param(self):
        response = self.client.get(self.confirm_url, {"availability": "abc"})
        self.assertRedirects(response, self.select_url, fetch_redirect_response=False)

    def test_slot_of_other_doctor_rejected(self):
        other = Doctor.objects.create(name="x", specialty="y")
        other_slot = DoctorAvailability.objects.create(doctor=other, day_of_week=0, time=time(11, 0))
        response = self.client.post(self.confirm_url, {"availability": other_slot.id})
        self.assertRedirects(response, self.select_url, fetch_redirect_response=False)
        self.assertFalse(Appointment.objects.exists())


class AppointmentLifecycleAdminTests(TestCase):
    """وضعیت نوبت فقط از مسیر services تغییر می‌کند: انجام‌شده، لغو توسط کلینیک، رزرو از ادمین."""

    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username="admin", password="x")
        self.patient = get_user_model().objects.create_user(username="09120000001", phone_number="09120000001")
        self.doctor = Doctor.objects.create(name="Dr", specialty="x", visit_fee=300_000)
        self.slot = DoctorAvailability.objects.create(doctor=self.doctor, day_of_week=0, time=time(10, 0))
        self.client.force_login(self.admin)

    def make(self, days=7, **extra):
        defaults = dict(availability=self.slot, patient=self.patient, date=next_saturday() + timedelta(days=days),
                        status="confirmed", fee=300_000, deposit=300_000, payment_status="paid", paid_amount=300_000)
        defaults.update(extra)
        return Appointment.objects.create(**defaults)

    def action(self, name, *appointments):
        return self.client.post(reverse("admin:appointments_appointment_changelist"), {
            "action": name, "_selected_action": [str(a.pk) for a in appointments],
        }, follow=True)

    def test_mark_completed_only_after_start(self):
        from .services import mark_completed
        past = self.make(days=-14)
        future = self.make(days=7)
        mark_completed(past)
        past.refresh_from_db()
        self.assertEqual(past.status, "completed")
        with self.assertRaises(ValueError):
            mark_completed(future)
        with self.assertRaises(ValueError):
            mark_completed(self.make(days=-21, status="cancelled"))

    def test_clinic_cancel_requests_refund_for_paid_and_ignores_deadline(self):
        from .services import cancel_by_clinic
        tomorrowish = self.make(days=0)  # حتی نزدیک به زمان نوبت (بیمار دیگر نمی‌تواند لغو کند)
        cancel_by_clinic(tomorrowish)
        tomorrowish.refresh_from_db()
        self.assertEqual((tomorrowish.status, tomorrowish.payment_status), ("cancelled", "refund_requested"))

        free = self.make(days=14, payment_status="not_required", fee=0, deposit=0, paid_amount=0)
        cancel_by_clinic(free)
        free.refresh_from_db()
        self.assertEqual(free.payment_status, "not_required")
        with self.assertRaises(ValueError):
            cancel_by_clinic(free)

    def test_complete_past_appointments_for_cron(self):
        from .services import complete_past_appointments
        past = self.make(days=-14)
        pending_past = self.make(days=-21, status="pending", payment_status="unpaid")
        future = self.make(days=7)
        self.assertEqual(complete_past_appointments(), 1)
        for obj, expected in ((past, "completed"), (pending_past, "pending"), (future, "confirmed")):
            obj.refresh_from_db()
            self.assertEqual(obj.status, expected)

    def test_admin_actions(self):
        past = self.make(days=-14)
        future = self.make(days=7)
        response = self.action("mark_as_completed", past, future)
        self.assertContains(response, "1 نوبت انجام‌شده ثبت شد. 1 مورد قابل انجام نبود.")
        self.action("cancel_selected_by_clinic", future)
        future.refresh_from_db()
        self.assertEqual((future.status, future.payment_status), ("cancelled", "refund_requested"))
        self.action("mark_as_refunded", future)
        future.refresh_from_db()
        self.assertEqual(future.payment_status, "refunded")

    def test_status_cannot_be_edited_directly_in_change_form(self):
        appointment = self.make(days=7)
        url = reverse("admin:appointments_appointment_change", args=[appointment.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="status"')
        self.assertNotContains(response, 'name="payment_status"')
        self.client.post(url, {"status": "cancelled", "payment_status": "unpaid"})
        appointment.refresh_from_db()
        self.assertEqual((appointment.status, appointment.payment_status), ("confirmed", "paid"))

    def test_admin_booking_uses_site_rules(self):
        from utils.jalali import gregorian_to_jalali
        date = next_saturday() + timedelta(days=7)
        jalali = gregorian_to_jalali(date).strftime("%Y-%m-%d")
        url = reverse("admin:appointments_appointment_add")
        self.assertEqual(self.client.get(url).status_code, 200)

        response = self.client.post(url, {"patient": self.patient.pk, "availability": self.slot.pk, "date": jalali})
        self.assertEqual(response.status_code, 302, response.content[:3000] if response.status_code != 302 else "")
        booked = Appointment.objects.get()
        self.assertEqual((booked.status, booked.payment_status, booked.fee), ("pending", "unpaid", 300_000))
        self.assertIsNotNone(booked.payment_deadline)

        # همان اسلات دوباره ⇒ خطای فرم، نه نوبت دوم
        other = get_user_model().objects.create_user(username="09120000002")
        response = self.client.post(url, {"patient": other.pk, "availability": self.slot.pk, "date": jalali})
        self.assertContains(response, "این زمان قبلاً رزرو شده است")
        self.assertEqual(Appointment.objects.count(), 1)


class DepositTests(TestCase):
    """بیعانه: درصدی از هزینه‌ی ویزیت آنلاین، مابقی در مطب؛ لغو به‌موقع ⇒ بازپرداخت."""

    def setUp(self):
        from apps.core.models import SiteSettings
        self.site = SiteSettings.objects.create(clinic_name="c", phone="1", deposit_percent=30, cancellation_deadline_hours=12)
        self.patient = get_user_model().objects.create_user(username="09120000001", phone_number="09120000001", password="x")
        self.doctor = Doctor.objects.create(name="Dr", specialty="x", visit_fee=300_000)
        self.slot = DoctorAvailability.objects.create(doctor=self.doctor, day_of_week=0, time=time(10, 0))
        self.date = next_saturday() + timedelta(days=7)

    def test_calculation(self):
        from .models import calculate_deposit
        self.assertEqual(calculate_deposit(300_000, 30), 90_000)
        self.assertEqual(calculate_deposit(250_000, 33), 83_000)   # ۸۲٬۵۰۰ ⇒ گرد به بالا تا هزار
        self.assertEqual(calculate_deposit(300_000, 100), 300_000)
        self.assertEqual(calculate_deposit(500, 50), 500)            # هرگز بیشتر از هزینه
        self.assertEqual(calculate_deposit(0, 30), 0)
        self.assertEqual(self.doctor.get_deposit(), 90_000)

    def test_booking_snapshots_deposit_and_payment_records_it(self):
        from .services import book_appointment, mark_appointment_paid
        appointment = book_appointment(self.patient, self.slot.pk, self.date)
        self.assertEqual((appointment.fee, appointment.deposit, appointment.paid_amount), (300_000, 90_000, 0))

        self.site.deposit_percent = 50   # تغییر بعدی تنظیمات روی نوبت ثبت‌شده اثر ندارد
        self.site.save()
        mark_appointment_paid(appointment)
        appointment.refresh_from_db()
        self.assertEqual((appointment.status, appointment.payment_status), ("confirmed", "deposit_paid"))
        self.assertEqual((appointment.paid_amount, appointment.remaining), (90_000, 210_000))

    def test_full_percent_behaves_like_before(self):
        from .services import book_appointment, mark_appointment_paid
        self.site.deposit_percent = 100
        self.site.save()
        appointment = book_appointment(self.patient, self.slot.pk, self.date)
        mark_appointment_paid(appointment)
        appointment.refresh_from_db()
        self.assertEqual((appointment.payment_status, appointment.paid_amount, appointment.remaining), ("paid", 300_000, 0))

    def test_gateway_receives_deposit_only(self):
        from apps.payments.services import _payable_amount
        from .services import book_appointment
        self.assertEqual(_payable_amount(book_appointment(self.patient, self.slot.pk, self.date)), 90_000)

    def test_timely_cancel_refunds_deposit_late_cancel_impossible(self):
        from .services import book_appointment, cancel_appointment, mark_appointment_paid
        appointment = book_appointment(self.patient, self.slot.pk, self.date)
        mark_appointment_paid(appointment)
        cancel_appointment(self.patient, appointment.pk)
        appointment.refresh_from_db()
        self.assertEqual((appointment.status, appointment.payment_status, appointment.paid_amount),
                         ("cancelled", "refund_requested", 90_000))

        start = timezone.localtime() + timedelta(hours=5)
        late_slot = DoctorAvailability.objects.create(
            doctor=self.doctor, day_of_week=DoctorAvailability.day_of_week_for(start.date()), time=start.time().replace(second=0, microsecond=0))
        late = Appointment.objects.create(availability=late_slot, patient=self.patient, date=start.date(), status="confirmed",
                                          fee=300_000, deposit=90_000, paid_amount=90_000, payment_status="deposit_paid")
        with self.assertRaises(ValueError):
            cancel_appointment(self.patient, late.pk)

    def test_unpaid_cancel_has_nothing_to_refund(self):
        from .services import book_appointment, cancel_appointment
        appointment = book_appointment(self.patient, self.slot.pk, self.date)
        cancel_appointment(self.patient, appointment.pk)
        appointment.refresh_from_db()
        self.assertEqual(appointment.payment_status, "unpaid")

    def test_settle_remaining_and_no_show(self):
        from .services import mark_no_show, settle_remaining
        past = Appointment.objects.create(availability=self.slot, patient=self.patient, date=next_saturday() - timedelta(days=7),
                                          status="confirmed", fee=300_000, deposit=90_000, paid_amount=90_000,
                                          payment_status="deposit_paid")
        settle_remaining(past)
        past.refresh_from_db()
        self.assertEqual((past.payment_status, past.paid_amount, past.remaining), ("paid", 300_000, 0))
        with self.assertRaises(ValueError):
            settle_remaining(past)   # دوباره نه

        absent = Appointment.objects.create(availability=self.slot, patient=self.patient, date=next_saturday() - timedelta(days=14),
                                            status="confirmed", fee=300_000, deposit=90_000, paid_amount=90_000,
                                            payment_status="deposit_paid")
        mark_no_show(absent)
        absent.refresh_from_db()
        self.assertEqual((absent.status, absent.payment_status), ("no_show", "deposit_paid"))
        future = Appointment.objects.create(availability=self.slot, patient=self.patient, date=self.date + timedelta(days=7),
                                            status="confirmed", fee=300_000, deposit=90_000, paid_amount=90_000,
                                            payment_status="deposit_paid")
        with self.assertRaises(ValueError):
            mark_no_show(future)

    def test_confirm_page_shows_breakdown_and_requires_terms(self):
        from utils.jalali import format_jalali
        self.client.force_login(self.patient)
        date = format_jalali(self.date, separator="-")
        url = reverse("appointments:confirm_appointment", args=[self.doctor.pk, date]) + f"?availability={self.slot.pk}"
        page = self.client.get(url)
        self.assertContains(page, "پرداخت بیعانه و ثبت نوبت")
        self.assertContains(page, "90,000 تومان")
        self.assertContains(page, "210,000 تومان")
        self.assertContains(page, 'name="accept_terms"')

        response = self.client.post(url, {"availability": self.slot.pk})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Appointment.objects.exists())   # بدون پذیرش قوانین ثبت نمی‌شود

        with self.settings(PAYMENT_GATEWAY="fake"):
            response = self.client.post(url, {"availability": self.slot.pk, "accept_terms": "on"})
        appointment = Appointment.objects.get()
        self.assertEqual(appointment.deposit, 90_000)
        self.assertEqual(response.status_code, 302)

    def test_free_visit_needs_no_terms_or_payment(self):
        from utils.jalali import format_jalali
        self.doctor.visit_fee = 0
        self.doctor.save()
        self.client.force_login(self.patient)
        url = reverse("appointments:confirm_appointment", args=[self.doctor.pk, format_jalali(self.date, separator="-")])
        self.client.post(url, {"availability": self.slot.pk})
        appointment = Appointment.objects.get()
        self.assertEqual((appointment.status, appointment.payment_status, appointment.deposit), ("confirmed", "not_required", 0))

    def test_admin_settle_and_no_show_actions(self):
        admin = get_user_model().objects.create_superuser(username="admin", password="x")
        self.client.force_login(admin)
        past = Appointment.objects.create(availability=self.slot, patient=self.patient, date=next_saturday() - timedelta(days=7),
                                          status="confirmed", fee=300_000, deposit=90_000, paid_amount=90_000,
                                          payment_status="deposit_paid")
        changelist = reverse("admin:appointments_appointment_changelist")
        self.assertContains(self.client.get(changelist), "210000")
        self.client.post(changelist, {"action": "settle_remaining_at_clinic", "_selected_action": [past.pk]})
        past.refresh_from_db()
        self.assertEqual(past.payment_status, "paid")
