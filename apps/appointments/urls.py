from django.urls import path

from .views import (
    book_appointment_view,
    cancel_appointment_view,
    confirm_appointment,
    doctor_list,
    my_appointments,
    select_time,
)


app_name = "appointments"


urlpatterns = [
    path("doctors/", doctor_list, name="doctors"),
    path("book/",book_appointment_view,name="book_appointment",),
    path("book/<int:doctor_id>/<str:date>/",select_time,name="select_time",),
    path("book/<int:doctor_id>/<str:date>/confirm/", confirm_appointment, name="confirm_appointment"),
    path("my/",my_appointments,name="my_appointments",),
    path("my/<int:appointment_id>/cancel/",cancel_appointment_view,name="cancel_appointment",),
]
