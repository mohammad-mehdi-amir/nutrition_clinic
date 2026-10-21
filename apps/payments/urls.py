from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("appointment/<int:appointment_id>/", views.pay_appointment, name="pay_appointment"),
    path("order/<int:order_id>/", views.pay_order, name="pay_order"),
    path("callback/<uuid:payment_id>/", views.callback, name="callback"),
    path("fake-gateway/<uuid:payment_id>/", views.fake_gateway, name="fake_gateway"),
]
