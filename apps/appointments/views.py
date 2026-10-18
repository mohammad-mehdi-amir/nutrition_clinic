from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Doctor
from .services import (
    book_appointment,
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

        try:

            book_appointment(
                patient=request.user,
                availability_id=availability_id,
                selected_date=selected_date,
            )

        except ValueError as error:

            messages.error(
                request,
                str(error)
            )

            return redirect(
                "appointments:select_time",
                doctor_id=doctor.id,
                date=date,
            )

        messages.success(
            request,
            "نوبت شما با موفقیت ثبت شد."
        )

        return redirect(
            "appointments:my_appointments"
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
        .order_by("-date", "-availability__time")
    )
    for appointment in appointments:

        appointment.can_cancel = can_cancel_appointment(

            appointment

        )
    return render(
        request,
        "appointments/my_appointments.html",
        {
            "appointments": appointments,
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
