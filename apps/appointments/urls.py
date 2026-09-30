from django.urls import path

from .views import schedule


app_name = "appointments"


urlpatterns = [
    path("schedule/",schedule,name="schedule"),
]