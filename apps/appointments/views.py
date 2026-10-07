from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .models import Doctor, DoctorAvailability
from .services import (
    get_available_slots,
    book_appointment,
    cancel_appointment,
    expire_pending_appointments,
    can_cancel_appointment
)
from django.views.decorators.http import require_POST

@staff_member_required
def schedule(request):

    doctors = Doctor.objects.filter(is_active=True)

    doctor_id = request.GET.get("doctor") or request.POST.get("doctor")

    doctor = None

    if doctor_id:
        doctor = get_object_or_404(
            Doctor,
            id=doctor_id,
            is_active=True
        )

    time_slots = []

    current = datetime.combine(
        datetime.today(),
        time(8, 0)
    )

    end = datetime.combine(
        datetime.today(),
        time(21, 0)
    )

    while current <= end:

        time_slots.append(
            current.time()
        )

        current += timedelta(minutes=30)

    # ساخت جدول برای Template
    schedule_rows = []

    for slot_time in time_slots:

        cells = []

        for day in range(7):

            cells.append({
                "day": day,
                "time": slot_time,
                "key": f"{day}_{slot_time.strftime('%H:%M')}",
            })

        schedule_rows.append({
            "time": slot_time,
            "cells": cells,
        })

    if request.method == "POST" and doctor:

        selected_slots = set(
            request.POST.getlist("slots")
        )

        with transaction.atomic():

            for day in range(7):

                for slot_time in time_slots:

                    key = f"{day}_{slot_time.strftime('%H:%M')}"

                    availability = (
                        DoctorAvailability.objects
                        .filter(
                            doctor=doctor,
                            day_of_week=day,
                            time=slot_time
                        )
                        .first()
                    )

                    if key in selected_slots:

                        if availability:

                            if not availability.is_active:

                                availability.is_active = True

                                availability.save(
                                    update_fields=["is_active"]
                                )

                        else:

                            DoctorAvailability.objects.create(
                                doctor=doctor,
                                day_of_week=day,
                                time=slot_time,
                                is_active=True
                            )

                    else:

                        if availability and availability.is_active:

                            availability.is_active = False

                            availability.save(
                                update_fields=["is_active"]
                            )

        messages.success(
            request,
            "برنامه کاری پزشک با موفقیت ذخیره شد."
        )

        return redirect(
            f"{request.path}?doctor={doctor.id}"
        )

    active_slots = set()

    if doctor:

        active_slots = {
            f"{item.day_of_week}_{item.time.strftime('%H:%M')}"
            for item in doctor.availabilities.filter(
                is_active=True
            )
        }

    context = {
        "doctors": doctors,
        "doctor": doctor,
        "schedule_rows": schedule_rows,
        "active_slots": active_slots,
    }

    return render(
        request,
        "appointments/schedule.html",
        context
    )
    
    


@login_required
def book_appointment_view(request):

    doctors = Doctor.objects.filter(is_active=True)

    if request.method == "POST":

        doctor_id = request.POST.get("doctor")
        selected_date = request.POST.get("date")

        if not doctor_id or not selected_date:
            messages.error(
                request,
                "لطفاً پزشک و تاریخ را انتخاب کنید."
            )

            return redirect(
                "appointments:book_appointment"
            )

        return redirect(
            "appointments:select_time",
            doctor_id=doctor_id,
            date=selected_date,
        )

    return render(
        request,
        "appointments/book_appointment.html",
        {
            "doctors": doctors,
        },
    )
    
    
@login_required

def select_time(request, doctor_id, date):

    doctor = get_object_or_404(

        Doctor,

        id=doctor_id,

        is_active=True,

    )

    try:

        selected_date = datetime.strptime(

            date,

            "%Y-%m-%d",

        ).date()

    except ValueError:

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

        try:

            book_appointment(

                patient=request.user,

                availability_id=availability_id,

                selected_date=selected_date,

            )

        except ValueError as error:

            messages.error(

                request,

                str(error),

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

            "appointments:book_appointment"

        )

    return render(

        request,

        "appointments/select_time.html",

        {

            "doctor": doctor,

            "selected_date": selected_date,

            "slots": slots,

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
