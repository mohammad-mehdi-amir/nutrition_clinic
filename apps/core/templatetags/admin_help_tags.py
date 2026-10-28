"""راهنمای پنل ادمین: کادر راهنمای هر فهرست و کارهای روزانه در صفحه‌ی اول."""
from datetime import timedelta

from django import template
from django.urls import reverse
from django.utils import timezone

from apps.core.admin_guides import get_guide

register = template.Library()


@register.simple_tag
def admin_guide(opts):
    return get_guide(opts)


@register.simple_tag(takes_context=True)
def admin_daily_tasks(context):
    """کارهای روزانه با تعداد و لینک فهرست فیلترشده؛ فقط بخش‌هایی که کاربر اجازه‌ی دیدنشان را دارد."""
    from apps.appointments.models import Appointment
    from apps.core.models import ContactMessage
    from apps.diet.models import DietRequest
    from apps.payments.models import Payment
    from apps.shop.models import Order

    user = context["request"].user
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)

    rows = [
        ("appointments.view_appointment", "نوبت‌های تأییدشده‌ی امروز",
         Appointment.objects.filter(status="confirmed", date=today),
         "admin:appointments_appointment_changelist",
         f"status__exact=confirmed&date__gte={today}&date__lt={tomorrow}"),
        ("appointments.view_appointment", "نوبت‌های در انتظار بازپرداخت",
         Appointment.objects.filter(payment_status=Appointment.PAYMENT_REFUND_REQUESTED),
         "admin:appointments_appointment_changelist", "payment_status__exact=refund_requested"),
        ("shop.view_order", "سفارش‌های پرداخت‌شده‌ی منتظر ارسال",
         Order.objects.filter(status=Order.STATUS_PAID),
         "admin:shop_order_changelist", f"status__exact={Order.STATUS_PAID}"),
        ("diet.view_dietrequest", "درخواست‌های رژیم در انتظار",
         DietRequest.objects.filter(status=DietRequest.STATUS_PENDING),
         "admin:diet_dietrequest_changelist", "status__exact=pending"),
        ("core.view_contactmessage", "پیام‌های تماس خوانده‌نشده",
         ContactMessage.objects.filter(is_read=False),
         "admin:core_contactmessage_changelist", "is_read__exact=0"),
        ("payments.view_payment", "پرداخت‌های نیازمند بررسی (بازپرداخت)",
         Payment.objects.filter(needs_review=True),
         "admin:payments_payment_changelist", "needs_review__exact=1"),
    ]
    return [
        {"label": label, "count": queryset.count(), "url": f"{reverse(url_name)}?{query}"}
        for perm, label, queryset, url_name, query in rows
        if user.has_perm(perm)
    ]
