from django.contrib import admin
from .models import Doctor, WorkingSchedule, Appointment


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("name", "specialty", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "specialty")


@admin.register(WorkingSchedule)
class WorkingScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "doctor",
        "day_of_week",
        "start_time",
        "end_time",
        "slot_duration",
        "is_active",
    )
    list_filter = ("day_of_week", "is_active", "doctor")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "doctor",
        "patient",
        "date",
        "start_time",
        "status",
        "created_at",
    )

    list_filter = ("status", "date", "doctor")
    search_fields = (
        "doctor__name",
        "patient__username",
    )