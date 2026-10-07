from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Appointment, DoctorAvailability
from datetime import timedelta
from apps.core.models import SiteSettings




ACTIVE_APPOINTMENT_STATUSES = [
    "pending",
    "confirmed",
    "completed",
]


def get_payment_timeout():
    settings = SiteSettings.objects.first()

    if not settings:
        return 10

    return settings.payment_timeout_minutes

def book_appointment(
    patient,
    availability_id,
    selected_date,
):
    expire_pending_appointments()
    today = timezone.localdate()

    if selected_date < today:
        raise ValueError(
            "امکان رزرو برای تاریخ گذشته وجود ندارد."
        )

    availability = DoctorAvailability.objects.filter(
        id=availability_id,
        is_active=True,
    ).select_related("doctor").first()

    if not availability:
        raise ValueError(
            "این زمان دیگر قابل رزرو نیست."
        )

    # بررسی روز هفته
    if selected_date.weekday() != availability.day_of_week:
        raise ValueError(
            "این زمان برای تاریخ انتخاب شده معتبر نیست."
        )

    # اگر امروز است، ساعت هم نباید گذشته باشد
    if selected_date == today:

        current_time = timezone.localtime().time()

        if availability.time <= current_time:
            raise ValueError(
                "این زمان گذشته است."
            )

    # بررسی اینکه اسلات قبلاً رزرو نشده باشد
    slot_booked = Appointment.objects.filter(
        availability=availability,
        date=selected_date,
        status__in=ACTIVE_APPOINTMENT_STATUSES,
    ).exists()

    if slot_booked:
        raise ValueError(
            "این زمان قبلاً رزرو شده است."
        )

    # بررسی تداخل بیمار با پزشک دیگر
    patient_has_conflict = Appointment.objects.filter(
        patient=patient,
        date=selected_date,
        availability__time=availability.time,
        status__in=ACTIVE_APPOINTMENT_STATUSES,
    ).exists()

    if patient_has_conflict:
        raise ValueError(
            "شما در این تاریخ و ساعت نوبت دیگری دارید."
        )

    try:
        with transaction.atomic():

            appointment = Appointment.objects.create(
                availability=availability,
                patient=patient,
                date=selected_date,
                status="pending",
                payment_deadline=timezone.now() + timedelta(seconds=10),
            )

    except IntegrityError:
        raise ValueError(
            "این زمان هم‌اکنون توسط شخص دیگری رزرو شد."
        )

    return appointment


def expire_pending_appointments():
    now = timezone.now()
    timeout_minutes = get_payment_timeout()
    expire_before = now - timedelta(minutes=timeout_minutes)
    Appointment.objects.filter(status="pending",created_at__lte=expire_before,).update(status="cancelled",)


def get_available_slots(doctor, selected_date):
    expire_pending_appointments()
    today = timezone.localdate()

    if selected_date < today:
        return []

    availabilities = DoctorAvailability.objects.filter(
        doctor=doctor,
        day_of_week=selected_date.weekday(),
        is_active=True,
    ).order_by("time")

    slots = []

    for availability in availabilities:

        is_booked = Appointment.objects.filter(
            availability=availability,
            date=selected_date,
            status__in=ACTIVE_APPOINTMENT_STATUSES,
        ).exists()

        if selected_date == today:

            current_time = timezone.localtime().time()

            if availability.time <= current_time:
                continue

        slots.append({
            "availability": availability,
            "is_booked": is_booked,
        })

    return slots