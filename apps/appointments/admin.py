from django.contrib import admin
from .models import Doctor, DoctorAvailability, Appointment


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "specialty",
        "is_active",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "specialty",
    )


@admin.register(DoctorAvailability)
class DoctorAvailabilityAdmin(admin.ModelAdmin):
    list_display = (
        "doctor",
        "day_of_week",
        "time",
        "is_active",
    )

    list_filter = (
        "doctor",
        "day_of_week",
        "is_active",
    )
    actions = ["go_to_schedule"]
    @admin.action(description="ساخت شیفت پزشکان")
    
    def go_to_schedule(self, request, queryset):

        from django.shortcuts import redirect

        return redirect("appointments:schedule")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
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
        return obj.availability.time