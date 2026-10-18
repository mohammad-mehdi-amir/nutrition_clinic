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
            name="Dr", specialty="Nutrition"
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
            date=self.saturday,
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
