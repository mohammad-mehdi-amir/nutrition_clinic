from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from jalali_date.admin import ModelAdminJalaliMixin

from .models import Doctor, DoctorAvailability, Appointment
from .services import (
    book_appointment,
    cancel_by_clinic,
    confirm_manual_payment,
    mark_completed,
    mark_no_show,
    settle_remaining,
    validate_slot,
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


class AppointmentAddForm(forms.ModelForm):
    """ثبت نوبت از ادمین (مثلاً رزرو تلفنی) با همان قواعد رزرو سایت."""

    class Meta:
        model = Appointment
        fields = ("patient", "availability", "date")

    def clean(self):
        cleaned = super().clean()
        patient, availability, date = cleaned.get("patient"), cleaned.get("availability"), cleaned.get("date")
        if patient and availability and date:
            try:
                validate_slot(patient, availability.pk, date)
            except ValueError as error:
                raise forms.ValidationError(str(error))
        return cleaned


@admin.register(Appointment)
class AppointmentAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_select_related = ("patient", "availability", "availability__doctor")

    list_display = (
        "patient",
        "get_doctor",
        "date",
        "get_time",
        "fee",
        "deposit",
        "paid_amount",
        "get_remaining",
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

    # وضعیت‌ها فقط از مسیر اکشن‌ها (services) تغییر می‌کنند تا قوانین لغو، پرداخت و بازپرداخت دور زده نشود
    readonly_fields = (
        "patient", "availability", "date", "start_time", "fee", "deposit", "paid_amount", "get_remaining",
        "status", "payment_status", "payment_deadline", "created_at",
    )

    actions = [
        "confirm_payment", "settle_remaining_at_clinic", "mark_as_completed", "mark_as_no_show",
        "cancel_selected_by_clinic", "mark_as_refunded",
    ]

    @admin.display(description="مابقی (تومان)")
    def get_remaining(self, obj):
        return obj.remaining

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = AppointmentAddForm
        return super().get_form(request, obj, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        return () if obj is None else self.readonly_fields

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                ("ثبت نوبت (مثلاً رزرو تلفنی)", {
                    "fields": ("patient", "availability", "date"),
                    "description": (
                        "بیمار، شیفت پزشک و تاریخ را انتخاب کنید. روز هفته‌ی تاریخ باید با روز شیفت یکی باشد. "
                        "نوبت با همان قوانین سایت ثبت می‌شود: ویزیت رایگان فوراً تأیید می‌شود و ویزیت پولی "
                        "«در انتظار پرداخت» می‌ماند؛ اگر بیمار حضوری پرداخت کرد، از عملیات «تأیید پرداخت دستی» استفاده کنید."
                    ),
                }),
            )
        return (
            ("نوبت", {"fields": ("patient", "availability", "date", "start_time", "created_at")}),
            ("وضعیت", {
                "fields": ("status", "payment_status", "payment_deadline"),
                "description": "برای تغییر وضعیت، به فهرست نوبت‌ها برگردید، این نوبت را تیک بزنید و از «عملیات» استفاده کنید.",
            }),
            ("مبالغ (تومان)", {
                "fields": ("fee", "deposit", "paid_amount", "get_remaining"),
                "description": "هزینه‌ی ویزیت و بیعانه در لحظه‌ی رزرو ثبت شده‌اند. «مابقی» مبلغی است که بیمار باید در مطب بپردازد.",
            }),
        )

    def save_model(self, request, obj, form, change):
        if change:
            return  # همه‌ی فیلدها فقط‌خواندنی‌اند؛ تغییر فقط با اکشن‌ها
        try:
            appointment = book_appointment(obj.patient, obj.availability_id, obj.date)
        except ValueError as error:  # رزرو هم‌زمان بین اعتبارسنجی فرم و ثبت
            raise forms.ValidationError(str(error))
        obj.pk = appointment.pk
        obj.refresh_from_db()

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

    @admin.action(description="تأیید پرداخت دستی (بیمار کل هزینه را حضوری پرداخت کرده است)")
    def confirm_payment(self, request, queryset):
        self._run(request, queryset, confirm_manual_payment, "تأیید شد")

    @admin.action(description="تسویه‌ی مابقی در مطب (بیمار مابقی هزینه را در مطب پرداخت کرده است)")
    def settle_remaining_at_clinic(self, request, queryset):
        self._run(request, queryset, settle_remaining, "به‌عنوان پرداخت کامل ثبت شد")

    @admin.action(description="ثبت «عدم حضور» (بیمار در زمان نوبت نیامده؛ بیعانه بازگردانده نمی‌شود)")
    def mark_as_no_show(self, request, queryset):
        self._run(request, queryset, mark_no_show, "عدم حضور ثبت شد")

    @admin.action(description="ثبت «انجام‌شده» (بیمار در زمان نوبت مراجعه کرده است)")
    def mark_as_completed(self, request, queryset):
        self._run(request, queryset, mark_completed, "انجام‌شده ثبت شد")

    @admin.action(description="لغو توسط کلینیک (اگر بیمار پرداخت کرده، به «در انتظار بازپرداخت» می‌رود)")
    def cancel_selected_by_clinic(self, request, queryset):
        self._run(request, queryset, cancel_by_clinic, "لغو شد")

    @admin.action(description="ثبت بازپرداخت انجام‌شده (پس از واریز وجه به بیمار)")
    def mark_as_refunded(self, request, queryset):
        self._run(request, queryset, mark_refunded, "به‌عنوان بازپرداخت‌شده ثبت شد")
