from django.urls import path

from . import views

app_name = "diet"

urlpatterns = [
    path("my/", views.my_diets, name="my_diets"),
    path("my/<uuid:pk>/download/", views.download_diet, name="download"),
    path("health/", views.health_profile, name="health_profile"),
    path("health/weight/", views.add_measurement_view, name="add_measurement"),
    path("health/notice/dismiss/", views.dismiss_health_notice, name="dismiss_health_notice"),
    path("staff/file/<path:path>", views.staff_file, name="staff_file"),
]
