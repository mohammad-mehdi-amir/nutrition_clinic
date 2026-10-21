from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.UserLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("password/reset/", views.password_reset_request, name="password_reset"),
    path("password/reset/verify/", views.password_reset_verify, name="password_reset_verify"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name="profile"),
    path("password/change/", views.UserPasswordChangeView.as_view(), name="password_change"),
    path("address/", views.address, name="address"),
    path("packages/", views.packages, name="packages"),
    path("payments/", views.payments, name="payments"),
]
