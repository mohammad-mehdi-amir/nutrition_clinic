from django.urls import path

from . import views

app_name = "diet"

urlpatterns = [
    path("staff/file/<path:path>", views.staff_file, name="staff_file"),
]
