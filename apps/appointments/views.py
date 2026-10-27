from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.core.models import SiteSettings
from apps.payments.views import redirect_to_gateway
from utils.ratelimit import ratelimit

from .models import Doctor
from .services import (
    book_appointment,
    cancellation_deadline,
    get_payment_timeout,
    validate_slot,
    can_cancel_appointment,
    cancel_appointment,
    expire_pending_appointments,
    get_available_slots,
)
from django.views.decorators.http import require_POST
from utils.jalali import format_jalali, jalali_to_gregorian
from .forms import AppointmentDateForm


def doctor_list(request):
    return render(
        request,
        "appointments/doctors.html",
        {"doctors": Doctor.objects.filter(is_active=True)},
    )


@login_required
def book_appointment_view(request):

    if request.method == "POST":

        form = AppointmentDateForm(request.POST)

        if form.is_valid():

            return redirect(
                "appointments:select_time",
                doctor_id=form.cleaned_data["doctor"].id,
                date=format_jalali(form.cleaned_data["date"], "-"),
            )

    else:
        form = AppointmentDateForm()

    return render(
        request,
        "appointments/book_appointment.html",
        {"form": form},
    )


@login_required
def select_time(request, doctor_id, date):

    doctor = get_object_or_404(
        Doctor,
        id=doctor_id,
        is_active=True,
    )

    try:
        selected_date = jalali_to_gregorian(date)

    except (ValueError, TypeError):
        messages.error(
            request,
            "تاریخ انتخاب شده معتبر نیست."
        )

        return redirect(
            "appointments:book_appointment"
        )

    slots = get_available_slots(
        doctor=doctor,
        selected_date=selected_date,
    )

    if request.method == "POST":

        availability_id = request.POST.get(
            "availability"
        )

        if not availability_id:
            messages.error(
                request,
                "لطفاً یک ساعت را انتخاب کنید."
            )

            return redirect(
                "appointments:select_time",
                doctor_id=doctor.id,
                date=date,
            )

        return redirect(
            f"{reverse('appointments:confirm_appointment', kwargs={'doctor_id': doctor.id, 'date': date})}"
            f"?availability={availability_id}"
        )

    has_available_slots = any(
        not slot["is_booked"]
        for slot in slots
    )

    return render(
        request,
        "appointments/select_time.html",
        {
            "doctor": doctor,
            "selected_date": selected_date,
            "selected_date_jalali": format_jalali(
                selected_date
            ),
            "slots": slots,
            "has_available_slots": has_available_slots,
            "fee": doctor.get_visit_fee(),
            "deposit": doctor.get_deposit(),
        },
    )
    
    
@login_required
@ratelimit("book", limit=20, window=3600)
def confirm_appointment(request, doctor_id, date):
    """خلاصه‌ی نوبت (پزشک، تاریخ، ساعت، هزینه) و ثبت نهایی."""
    doctor = get_object_or_404(Doctor, id=doctor_id, is_active=True)
    select_url = reverse("appointments:select_time", kwargs={"doctor_id": doctor.id, "date": date})

    try:
        selected_date = jalali_to_gregorian(date)
    except (ValueError, TypeError):
        messages.error(request, "تاریخ انتخاب شده معتبر نیست.")
        return redirect("appointments:book_appointment")

    try:
        availability_id = int(request.POST.get("availability") or request.GET.get("availability"))
    except (TypeError, ValueError):
        messages.error(request, "لطفاً یک ساعت را انتخاب کنید.")
        return redirect(select_url)

    try:
        availability = validate_slot(request.user, availability_id, selected_date)
        if availability.doctor_id != doctor.id:
            raise ValueError("این زمان متعلق به پزشک انتخاب‌شده نیست.")
    except ValueError as error:
        messages.error(request, str(error))
        return redirect(select_url)

    fee = doctor.get_visit_fee()
    deposit = doctor.get_deposit()
    cancellation_hours = SiteSettings.load().cancellation_deadline_hours
    start = timezone.make_aware(datetime.combine(selected_date, availability.time))

    if request.method == "POST":
        # پذیرش قانون لغو و بیعانه فقط وقتی پرداختی در کار است (سمت سرور هم بررسی می‌شود)
        if deposit and request.POST.get("accept_terms") != "on":
            messages.error(request, "برای ادامه، لطفاً قوانین لغو نوبت و بیعانه را تأیید کنید.")
            return redirect(f"{request.path}?availability={availability.id}")

        try:
            appointment = book_appointment(
                patient=request.user,
                availability_id=availability.id,
                selected_date=selected_date,
            )
        except ValueError as error:
            messages.error(request, str(error))
            return redirect(select_url)

        if appointment.status == "confirmed":
            messages.success(request, "نوبت شما ثبت و تأیید شد.")
            return redirect("appointments:my_appointments")

        # نوبت پولی: مستقیم به درگاه؛ در صورت خطا دکمه‌ی پرداخت در «نوبت‌های من» هست
        return redirect_to_gateway(request, appointment, reverse("appointments:my_appointments"))

    return render(
        request,
        "appointments/confirm_appointment.html",
        {
            "doctor": doctor,
            "availability": availability,
            "selected_date_jalali": format_jalali(selected_date),
            "date": date,
            "fee": fee,
            "deposit": deposit,
            "remaining": fee - deposit,
            "cancellation_hours": cancellation_hours,
            "cancel_until": start - timedelta(hours=cancellation_hours),
            "payment_timeout": get_payment_timeout(),
            "select_url": select_url,
        },
    )


@login_required
def my_appointments(request):
    expire_pending_appointments()
    appointments = (
        request.user.appointments
        .select_related(
            "availability",
            "availability__doctor",
        )
        .order_by("-date", "-start_time")
    )
    for appointment in appointments:
        appointment.can_cancel = can_cancel_appointment(appointment)
        appointment.cancel_until = cancellation_deadline(appointment)
    return render(
        request,
        "appointments/my_appointments.html",
        {
            "appointments": appointments,
            "panel_section": "appointments",
        },
    )
    
@login_required
@require_POST
def cancel_appointment_view(request, appointment_id):

    try:
        cancel_appointment(
            patient=request.user,
            appointment_id=appointment_id,
        )

    except ValueError as error:
        messages.error(
            request,
            str(error),
        )

    else:
        messages.success(
            request,
            "نوبت با موفقیت لغو شد.",
        )

    return redirect(
        "appointments:my_appointments"
    )
