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
        appointment = self._appointment(days_ahead=3, fee=150_000, payment_status="paid")
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

        response = self.client.post(self.confirm_url, {"availability": self.slot.id})
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
