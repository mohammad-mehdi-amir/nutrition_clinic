from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from jalali_date.admin import ModelAdminJalaliMixin

from .models import Doctor, DoctorAvailability, Appointment
from .services import (
    confirm_manual_payment,
    get_active_slot_keys,
    mark_refunded,
    get_schedule_time_slots,
    save_weekly_schedule,
    schedule_slot_key,
)


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "specialty",
        "visit_fee",
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
    change_list_template = "admin/appointments/doctor/change_list.html"

    def get_urls(self):
        return [
            path(
                "schedule/",
                self.admin_site.admin_view(self.schedule_view),
                name="appointments_doctor_schedule",
            ),
        ] + super().get_urls()

    @admin.display(description="برنامه‌ی هفتگی")
    def schedule_link(self, obj):
        url = reverse("admin:appointments_doctor_schedule")
        return format_html('<a href="{}?doctor={}">ویرایش شیفت‌ها</a>', url, obj.pk)

    def schedule_view(self, request):
        """صفحه‌ی برنامه‌ی کاری: انتخاب پزشک از لیست بالای صفحه + جدول شیفت‌ها."""
        if not request.user.has_perm("appointments.change_doctoravailability"):
            raise PermissionDenied

        doctor = None
        doctor_id = request.POST.get("doctor") or request.GET.get("doctor")
        if doctor_id:
            doctor = get_object_or_404(Doctor, pk=doctor_id)

        if request.method == "POST" and doctor:
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

            return redirect(f"{request.path}?doctor={doctor.pk}")

        rows = []
        if doctor:
            active_keys = get_active_slot_keys(doctor)
            rows = [
                {
                    "time": slot_time,
                    "cells": [
                        {
                            "key": schedule_slot_key(day, slot_time),
                            "checked": schedule_slot_key(day, slot_time) in active_keys,
                        }
                        for day, _ in DoctorAvailability.DAYS_OF_WEEK
                    ],
                }
                for slot_time in get_schedule_time_slots()
            ]

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "برنامه کاری پزشک",
            "doctors": Doctor.objects.all(),
            "doctor": doctor,
            "days": DoctorAvailability.DAYS_OF_WEEK,
            "rows": rows,
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
        "date",
        "get_time",
        "fee",
        "status",
        "payment_status",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_status",
        "date",
        "availability__doctor",
    )

    search_fields = (
        "patient__username",
        "patient__phone_number",
        "patient__first_name",
        "patient__last_name",
        "availability__doctor__name",
    )

    readonly_fields = ("start_time", "fee", "created_at", "payment_deadline")

    actions = ["confirm_payment", "mark_as_refunded"]

    @admin.display(description="دکتر")
    def get_doctor(self, obj):
        return obj.availability.doctor

    @admin.display(description="ساعت")
    def get_time(self, obj):
        return obj.start_time.strftime("%H:%M")

    def _run(self, request, queryset, func, done_message):
        done = 0
        for appointment in queryset:
            try:
                func(appointment)
                done += 1
            except ValueError:
                continue
        skipped = queryset.count() - done
        self.message_user(request, f"{done} نوبت {done_message}." + (f" {skipped} مورد قابل انجام نبود." if skipped else ""))

    @admin.action(description="تأیید پرداخت دستی (نوبت‌های در انتظار پرداخت)")
    def confirm_payment(self, request, queryset):
        self._run(request, queryset, confirm_manual_payment, "تأیید شد")

    @admin.action(description="ثبت بازپرداخت انجام‌شده")
    def mark_as_refunded(self, request, queryset):
        self._run(request, queryset, mark_refunded, "به‌عنوان بازپرداخت‌شده ثبت شد")
