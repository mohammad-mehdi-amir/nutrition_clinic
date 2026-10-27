from datetime import date, datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core import notifications
from apps.core.models import SiteSettings
from .models import (
    ACTIVE_APPOINTMENT_STATUSES,
    Appointment,
    DoctorAvailability,
)


def get_payment_timeout():
    return SiteSettings.load().payment_timeout_minutes


def is_slot_in_past(selected_date, slot_time):
    today = timezone.localdate()

    if selected_date < today:
        return True

    if selected_date == today:
        return slot_time <= timezone.localtime().time()

    return False


def appointment_start(appointment):
    """زمان شروع نوبت (aware، منطقه‌ی زمانی پروژه)."""
    return timezone.make_aware(datetime.combine(appointment.date, appointment.start_time))


def validate_slot(patient, availability_id, selected_date):
    """
    بررسی قابل رزرو بودن اسلات برای بیمار؛ در صورت معتبر بودن availability را برمی‌گرداند.
    (بررسی اولیه برای پیام مناسب؛ ضمانت نهایی با قیدهای یکتای دیتابیس است.)
    """
    if selected_date < timezone.localdate():
        raise ValueError("امکان رزرو برای تاریخ گذشته وجود ندارد.")

    availability = (
        DoctorAvailability.objects
        .filter(id=availability_id, is_active=True, doctor__is_active=True)
        .select_related("doctor")
        .first()
    )

    if not availability:
        raise ValueError("این زمان دیگر قابل رزرو نیست.")

    if DoctorAvailability.day_of_week_for(selected_date) != availability.day_of_week:
        raise ValueError("این زمان برای تاریخ انتخاب شده معتبر نیست.")

    if is_slot_in_past(selected_date, availability.time):
        raise ValueError("این زمان گذشته است.")

    if Appointment.objects.filter(
        availability=availability,
        date=selected_date,
        status__in=ACTIVE_APPOINTMENT_STATUSES,
    ).exists():
        raise ValueError("این زمان قبلاً رزرو شده است.")

    if Appointment.objects.filter(
        patient=patient,
        date=selected_date,
        start_time=availability.time,
        status__in=ACTIVE_APPOINTMENT_STATUSES,
    ).exists():
        raise ValueError("شما در این تاریخ و ساعت نوبت دیگری دارید.")

    return availability


def book_appointment(patient, availability_id, selected_date):
    expire_pending_appointments()

    availability = validate_slot(patient, availability_id, selected_date)
    fee = availability.doctor.get_visit_fee()
    deposit = availability.doctor.get_deposit()

    if fee:
        status = "pending"
        payment_status = Appointment.PAYMENT_UNPAID
        payment_deadline = timezone.now() + timedelta(minutes=get_payment_timeout())
    else:
        # ویزیت رایگان نیازی به پرداخت ندارد و مستقیم تأیید می‌شود
        status = "confirmed"
        payment_status = Appointment.PAYMENT_NOT_REQUIRED
        payment_deadline = None

    try:
        with transaction.atomic():
            appointment = Appointment.objects.create(
                availability=availability,
                patient=patient,
                date=selected_date,
                start_time=availability.time,
                fee=fee,
                deposit=deposit,
                status=status,
                payment_status=payment_status,
                payment_deadline=payment_deadline,
            )
    except IntegrityError:
        # درخواست هم‌زمان: همین اسلات یا همین ساعت برای بیمار در همین لحظه ثبت شد
        raise ValueError("این زمان هم‌اکنون رزرو شد؛ لطفاً زمان دیگری انتخاب کنید.")

    if appointment.status == "confirmed":
        notifications.appointment_confirmed(appointment)

    return appointment


def expire_pending_appointments():
    """لغو نوبت‌های پرداخت‌نشده‌ای که مهلتشان گذشته؛ تعداد را برمی‌گرداند."""
    now = timezone.now()

    # نوبت‌های قدیمی که payment_deadline ندارند بر اساس created_at منقضی می‌شوند
    legacy_expire_before = now - timedelta(minutes=get_payment_timeout())

    return Appointment.objects.filter(
        Q(payment_deadline__lte=now)
        | Q(
            payment_deadline__isnull=True,
            created_at__lte=legacy_expire_before,
        ),
        status="pending",
    ).update(status="cancelled", payment_deadline=None)


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


def cancellation_deadline(appointment):
    """آخرین زمانی که بیمار می‌تواند نوبت را لغو کند."""
    hours = SiteSettings.load().cancellation_deadline_hours
    return appointment_start(appointment) - timedelta(hours=hours)


def can_cancel_appointment(appointment):
    return (
        appointment.status in ("pending", "confirmed")
        and timezone.now() <= cancellation_deadline(appointment)
    )


def cancel_appointment(patient, appointment_id):
    with transaction.atomic():
        appointment = (
            Appointment.objects
            .select_for_update()
            .filter(id=appointment_id, patient=patient)
            .first()
        )

        if not appointment:
            raise ValueError("نوبت مورد نظر پیدا نشد.")

        if not can_cancel_appointment(appointment):
            hours = SiteSettings.load().cancellation_deadline_hours
            raise ValueError(
                f"این نوبت قابل لغو نیست. لغو فقط تا {hours} ساعت قبل از شروع نوبت امکان‌پذیر است؛ "
                "برای هماهنگی با کلینیک تماس بگیرید."
            )

        appointment.status = "cancelled"
        appointment.payment_deadline = None

        # لغو در مهلت مجاز ⇒ مبلغ دریافت‌شده (بیعانه یا کل) بازپرداخت می‌شود
        if appointment.paid_amount:
            appointment.payment_status = Appointment.PAYMENT_REFUND_REQUESTED

        appointment.save(update_fields=["status", "payment_deadline", "payment_status"])

    return appointment


def confirm_manual_payment(appointment):
    """تأیید پرداخت دستی توسط ادمین (تا قبل از اتصال درگاه)."""
    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)

        if appointment.status != "pending":
            raise ValueError("فقط نوبت‌های در انتظار پرداخت قابل تأیید هستند.")

        # پرداخت کامل هزینه به‌صورت حضوری
        appointment.status = "confirmed"
        appointment.payment_status = Appointment.PAYMENT_PAID
        appointment.paid_amount = appointment.fee
        appointment.payment_deadline = None
        appointment.save(update_fields=["status", "payment_status", "paid_amount", "payment_deadline"])
        notifications.appointment_confirmed(appointment)

    return appointment


def mark_completed(appointment):
    """ثبت انجام شدن نوبت تأییدشده‌ای که زمانش رسیده (ادمین)."""
    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)

        if appointment.status != "confirmed":
            raise ValueError("فقط نوبت‌های تأییدشده را می‌توان انجام‌شده ثبت کرد.")
        if appointment_start(appointment) > timezone.now():
            raise ValueError("زمان این نوبت هنوز نرسیده است.")

        appointment.status = "completed"
        appointment.save(update_fields=["status"])

    return appointment


def settle_remaining(appointment):
    """دریافت مابقی هزینه در مطب (پس از پرداخت بیعانه)."""
    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)

        if appointment.payment_status != Appointment.PAYMENT_DEPOSIT_PAID:
            raise ValueError("فقط برای نوبت‌هایی که بیعانه‌ی آن‌ها پرداخت شده قابل ثبت است.")
        if appointment.status not in ("confirmed", "completed"):
            raise ValueError("این نوبت تأییدشده یا انجام‌شده نیست.")

        appointment.payment_status = Appointment.PAYMENT_PAID
        appointment.paid_amount = appointment.fee
        appointment.save(update_fields=["payment_status", "paid_amount"])

    return appointment


def mark_no_show(appointment):
    """بیمار در زمان نوبت مراجعه نکرده است؛ بیعانه بازپرداخت نمی‌شود."""
    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)

        if appointment.status not in ("confirmed", "completed"):
            raise ValueError("فقط برای نوبت‌های تأییدشده قابل ثبت است.")
        if appointment_start(appointment) > timezone.now():
            raise ValueError("زمان این نوبت هنوز نرسیده است.")

        appointment.status = "no_show"
        appointment.save(update_fields=["status"])

    return appointment


def cancel_by_clinic(appointment):
    """
    لغو نوبت توسط کلینیک (بدون محدودیت مهلت لغو بیمار).
    نوبت پرداخت‌شده «در انتظار بازپرداخت» می‌شود تا ادمین وجه را برگرداند.
    """
    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)

        if appointment.status not in ("pending", "confirmed"):
            raise ValueError("فقط نوبت‌های در انتظار پرداخت یا تأییدشده قابل لغو هستند.")

        appointment.status = "cancelled"
        appointment.payment_deadline = None
        if appointment.paid_amount:
            appointment.payment_status = Appointment.PAYMENT_REFUND_REQUESTED
        appointment.save(update_fields=["status", "payment_deadline", "payment_status"])
        notifications.appointment_cancelled_by_clinic(appointment)

    return appointment


def complete_past_appointments():
    """
    نوبت‌های تأییدشده‌ی روزهای گذشته «انجام‌شده» می‌شوند (برای cron)؛ تعداد را برمی‌گرداند.
    نوبت امروز تا پایان روز تأییدشده می‌ماند تا ادمین در صورت لزوم آن را لغو کند.
    """
    return Appointment.objects.filter(status="confirmed", date__lt=timezone.localdate()).update(status="completed")


def mark_refunded(appointment):
    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)

        if appointment.payment_status != Appointment.PAYMENT_REFUND_REQUESTED:
            raise ValueError("این نوبت در انتظار بازپرداخت نیست.")

        appointment.payment_status = Appointment.PAYMENT_REFUNDED
        appointment.save(update_fields=["payment_status"])

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


def _apply_online_payment(appointment):
    """پرداخت آنلاین همیشه به اندازه‌ی بیعانه است؛ اگر بیعانه کمتر از هزینه باشد مابقی در مطب گرفته می‌شود."""
    appointment.paid_amount = appointment.deposit
    appointment.payment_status = (
        Appointment.PAYMENT_DEPOSIT_PAID if appointment.deposit < appointment.fee else Appointment.PAYMENT_PAID
    )


def mark_appointment_paid(appointment):
    """
    اعمال پرداخت موفق درگاه. True یعنی نوبت تأیید شد؛
    False یعنی نوبت قابل فعال‌سازی نبود و درخواست بازپرداخت ثبت شد.
    """
    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)

        if appointment.status == "confirmed" and appointment.payment_status in (
            Appointment.PAYMENT_PAID, Appointment.PAYMENT_DEPOSIT_PAID,
        ):
            return True

        if appointment.status == "pending":
            appointment.status = "confirmed"
            _apply_online_payment(appointment)
            appointment.payment_deadline = None
            appointment.save(update_fields=["status", "payment_status", "paid_amount", "payment_deadline"])
            notifications.appointment_confirmed(appointment)
            return True

        # نوبت هنگام حضور کاربر در درگاه منقضی شده؛ اگر اسلات هنوز آزاد است دوباره فعالش می‌کنیم
        if appointment.status == "cancelled" and appointment.payment_status == Appointment.PAYMENT_UNPAID:
            try:
                with transaction.atomic():
                    appointment.status = "confirmed"
                    _apply_online_payment(appointment)
                    appointment.payment_deadline = None
                    appointment.save(update_fields=["status", "payment_status", "paid_amount", "payment_deadline"])
                notifications.appointment_confirmed(appointment)
                return True
            except IntegrityError:
                appointment.refresh_from_db()

        appointment.payment_status = Appointment.PAYMENT_REFUND_REQUESTED
        appointment.save(update_fields=["payment_status"])
        return False
