from django.urls import path

from .views import *


app_name = "appointments"


urlpatterns = [
    path("schedule/", schedule, name="schedule"),
    path("book/",book_appointment_view,name="book_appointment",),
    path("book/<int:doctor_id>/<str:date>/",select_time,name="select_time",),
]
