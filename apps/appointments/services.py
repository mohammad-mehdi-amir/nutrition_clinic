from datetime import date, datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import SiteSettings
from .models import (
    ACTIVE_APPOINTMENT_STATUSES,
    Appointment,
    DoctorAvailability,
)


def get_payment_timeout():
    settings = SiteSettings.objects.first()

    if not settings:
        return 10

    return settings.payment_timeout_minutes


def is_slot_in_past(selected_date, slot_time):
    today = timezone.localdate()

    if selected_date < today:
        return True

    if selected_date == today:
        return slot_time <= timezone.localtime().time()

    return False


def book_appointment(
    patient,
    availability_id,
    selected_date,
):
    expire_pending_appointments()

    if selected_date < timezone.localdate():
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
    if DoctorAvailability.day_of_week_for(selected_date) != availability.day_of_week:
        raise ValueError(
            "این زمان برای تاریخ انتخاب شده معتبر نیست."
        )

    # اگر امروز است، ساعت هم نباید گذشته باشد
    if is_slot_in_past(selected_date, availability.time):
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
                payment_deadline=timezone.now() + timedelta(
                    minutes=get_payment_timeout()
                ),
            )

    except IntegrityError:
        raise ValueError(
            "این زمان هم‌اکنون توسط شخص دیگری رزرو شد."
        )

    return appointment


def expire_pending_appointments():
    now = timezone.now()

    # نوبت‌های قدیمی که payment_deadline ندارند بر اساس created_at منقضی می‌شوند
    legacy_expire_before = now - timedelta(minutes=get_payment_timeout())

    Appointment.objects.filter(
        Q(payment_deadline__lte=now)
        | Q(
            payment_deadline__isnull=True,
            created_at__lte=legacy_expire_before,
        ),
        status="pending",
    ).update(status="cancelled")


def get_available_slots(doctor, selected_date):
    expire_pending_appointments()

    if selected_date < timezone.localdate():
        return []

    availabilities = DoctorAvailability.objects.filter(
        doctor=doctor,
        day_of_week=DoctorAvailability.day_of_week_for(selected_date),
        is_active=True,
    ).order_by("time")

    booked_ids = set(
        Appointment.objects.filter(
            availability__in=availabilities,
            date=selected_date,
            status__in=ACTIVE_APPOINTMENT_STATUSES,
        ).values_list("availability_id", flat=True)
    )

    return [
        {
            "availability": availability,
            "is_booked": availability.id in booked_ids,
        }
        for availability in availabilities
        if not is_slot_in_past(selected_date, availability.time)
    ]


def can_cancel_appointment(appointment):
    return (
        appointment.status == "confirmed"
        and not is_slot_in_past(
            appointment.date,
            appointment.availability.time,
        )
    )


def cancel_appointment(patient, appointment_id):
    appointment = (
        Appointment.objects
        .select_related("availability")
        .filter(
            id=appointment_id,
            patient=patient,
        )
        .first()
    )

    if not appointment:
        raise ValueError(
            "نوبت مورد نظر پیدا نشد."
        )

    if not can_cancel_appointment(appointment):
        raise ValueError(
            "فقط نوبت‌های تایید شده‌ای که زمانشان نگذشته قابل لغو هستند."
        )

    appointment.status = "cancelled"
    appointment.payment_deadline = None

    appointment.save(
        update_fields=[
            "status",
            "payment_deadline",
        ]
    )

    return appointment


# ---------- برنامه‌ی هفتگی پزشک (صفحه‌ی ادمین) ----------

SCHEDULE_SLOT_MINUTES = 30
SCHEDULE_DEFAULT_START = time(8, 0)
SCHEDULE_DEFAULT_END = time(21, 0)


def schedule_slot_key(day, slot_time):
    return f"{day}_{slot_time.strftime('%H:%M')}"


def get_schedule_time_slots():
    """اسلات‌های نیم‌ساعته بین ساعت شروع و پایان کار کلینیک (یا ۸ تا ۲۱)."""
    site_settings = SiteSettings.load()
    start = site_settings.open_at or SCHEDULE_DEFAULT_START
    end = site_settings.close_at or SCHEDULE_DEFAULT_END

    current = datetime.combine(date.today(), start)
    last = datetime.combine(date.today(), end)
    slots = []

    while current <= last:
        slots.append(current.time())
        current += timedelta(minutes=SCHEDULE_SLOT_MINUTES)

    return slots


def save_weekly_schedule(doctor, selected_keys):
    """
    همگام‌سازی شیفت‌های پزشک با اسلات‌های انتخاب‌شده.
    شیفت‌ها حذف نمی‌شوند (نوبت‌های قبلی PROTECT هستند)، فقط فعال/غیرفعال می‌شوند.
    """
    selected_keys = set(selected_keys)
    existing = {
        (item.day_of_week, item.time): item
        for item in doctor.availabilities.all()
    }

    to_create = []
    to_activate = []
    to_deactivate = []

    for day, _ in DoctorAvailability.DAYS_OF_WEEK:
        for slot_time in get_schedule_time_slots():
            availability = existing.get((day, slot_time))

            if schedule_slot_key(day, slot_time) in selected_keys:
                if not availability:
                    to_create.append(
                        DoctorAvailability(doctor=doctor, day_of_week=day, time=slot_time, is_active=True)
                    )
                elif not availability.is_active:
                    to_activate.append(availability.id)

            elif availability and availability.is_active:
                to_deactivate.append(availability.id)

    with transaction.atomic():
        DoctorAvailability.objects.bulk_create(to_create)
        DoctorAvailability.objects.filter(id__in=to_activate).update(is_active=True)
        DoctorAvailability.objects.filter(id__in=to_deactivate).update(is_active=False)

    affected_appointments = Appointment.objects.filter(
        availability_id__in=to_deactivate,
        date__gte=timezone.localdate(),
        status__in=["pending", "confirmed"],
    ).count()

    return {
        "created": len(to_create),
        "activated": len(to_activate),
        "deactivated": len(to_deactivate),
        "affected_appointments": affected_appointments,
    }


def get_active_slot_keys(doctor):
    return {
        schedule_slot_key(item.day_of_week, item.time)
        for item in doctor.availabilities.filter(is_active=True)
    }
