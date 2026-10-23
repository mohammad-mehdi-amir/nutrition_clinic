from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from utils.ratelimit import ratelimit

from .models import Payment
from .services import PaymentError, handle_callback, start_payment


def _callback_url(request):
    return lambda payment: request.build_absolute_uri(reverse("payments:callback", args=[payment.pk]))


def redirect_to_gateway(request, target, failure_url):
    """شروع پرداخت و انتقال به درگاه؛ در صورت خطا پیام و بازگشت به failure_url."""
    try:
        _, redirect_url = start_payment(request.user, target, _callback_url(request))
    except PaymentError as error:
        messages.error(request, str(error))
        return redirect(failure_url)
    return redirect(redirect_url)


@login_required
@require_POST
@ratelimit("pay", limit=30, window=3600)
def pay_appointment(request, appointment_id):
    appointment = get_object_or_404(request.user.appointments, pk=appointment_id)
    return redirect_to_gateway(request, appointment, reverse("appointments:my_appointments"))


@login_required
@require_POST
@ratelimit("pay", limit=30, window=3600)
def pay_order(request, order_id):
    order = get_object_or_404(request.user.orders, pk=order_id)
    return redirect_to_gateway(request, order, order.get_absolute_url())


def callback(request, payment_id):
    """
    بازگشت از درگاه. ورود کاربر لازم نیست (ممکن است session در مرورگر درگاه از بین رفته باشد)؛
    تراکنش با UUID تصادفی و تطبیق Authority شناسایی و سمت سرور verify می‌شود.
    """
    get_object_or_404(Payment, pk=payment_id)
    payment = handle_callback(payment_id, request.GET)
    return render(request, "payments/result.html", {"payment": payment})


def fake_gateway(request, payment_id):
    if not (settings.DEBUG or getattr(settings, "PAYMENT_ALLOW_FAKE_GATEWAY", False)):
        raise Http404
    payment = get_object_or_404(Payment, pk=payment_id, gateway=Payment.GATEWAY_FAKE)
    callback_url = reverse("payments:callback", args=[payment.pk])
    return render(
        request,
        "payments/fake_gateway.html",
        {"payment": payment, "callback_url": callback_url, "authority": request.GET.get("authority", "")},
    )
