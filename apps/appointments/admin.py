from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from jalali_date.admin import ModelAdminJalaliMixin

from .models import Doctor, DoctorAvailability, Appointment
from .services import (
    get_active_slot_keys,
    get_schedule_time_slots,
    save_weekly_schedule,
    schedule_slot_key,
)


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "specialty",
        "is_active",
        "schedule_link",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "specialty",
    )

    change_form_template = "admin/appointments/doctor/change_form.html"

    def get_urls(self):
        return [
            path(
                "<int:doctor_id>/schedule/",
                self.admin_site.admin_view(self.schedule_view),
                name="appointments_doctor_schedule",
            ),
        ] + super().get_urls()

    @admin.display(description="برنامه‌ی هفتگی")
    def schedule_link(self, obj):
        url = reverse("admin:appointments_doctor_schedule", args=[obj.pk])
        return format_html('<a href="{}">ویرایش شیفت‌ها</a>', url)

    def schedule_view(self, request, doctor_id):
        if not request.user.has_perm("appointments.change_doctoravailability"):
            raise PermissionDenied

        doctor = get_object_or_404(Doctor, pk=doctor_id)

        if request.method == "POST":
            result = save_weekly_schedule(doctor, request.POST.getlist("slots"))
            messages.success(
                request,
                f"برنامه‌ی {doctor.name} ذخیره شد "
                f"({result['created'] + result['activated']} شیفت فعال شد، {result['deactivated']} شیفت غیرفعال شد).",
            )

            if result["affected_appointments"]:
                messages.warning(
                    request,
                    f"{result['affected_appointments']} نوبت آینده روی شیفت‌های غیرفعال‌شده ثبت شده است. "
                    "این نوبت‌ها لغو نشده‌اند؛ لطفاً با بیماران هماهنگ کنید.",
                )

            return redirect(request.path)

        active_keys = get_active_slot_keys(doctor)
        days = DoctorAvailability.DAYS_OF_WEEK
        rows = [
            {
                "time": slot_time,
                "cells": [
                    {
                        "day": day,
                        "key": schedule_slot_key(day, slot_time),
                        "checked": schedule_slot_key(day, slot_time) in active_keys,
                    }
                    for day, _ in days
                ],
            }
            for slot_time in get_schedule_time_slots()
        ]

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": f"برنامه‌ی هفتگی {doctor.name}",
            "doctor": doctor,
            "days": days,
            "rows": rows,
            "active_count": len(active_keys),
        }
        return TemplateResponse(request, "admin/appointments/doctor/schedule.html", context)


@admin.register(DoctorAvailability)
class DoctorAvailabilityAdmin(admin.ModelAdmin):
    list_display = (
        "doctor",
        "day_of_week",
        "get_time",
        "is_active",
    )

    list_filter = (
        "doctor",
        "day_of_week",
        "is_active",
    )

    list_select_related = ("doctor",)

    @admin.display(description="ساعت")
    def get_time(self, obj):
        return obj.time.strftime("%H:%M")


@admin.register(Appointment)
class AppointmentAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_select_related = ("patient", "availability", "availability__doctor")

    list_display = (
        "patient",
        "get_doctor",
        "get_time",
        "date",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "date",
        "availability__doctor",
    )

    search_fields = (
        "patient__username",
        "patient__first_name",
        "patient__last_name",
        "availability__doctor__name",
    )

    @admin.display(description="دکتر")
    def get_doctor(self, obj):
        return obj.availability.doctor

    @admin.display(description="ساعت")
    def get_time(self, obj):
        return obj.availability.time.strftime("%H:%M")