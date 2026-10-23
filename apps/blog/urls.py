from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.post_list, name="post_list"),
    path("category/<str:slug>/", views.post_list, name="category"),
    path("<str:slug>/", views.post_detail, name="post_detail"),
]
