from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .models import Doctor, DoctorAvailability


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