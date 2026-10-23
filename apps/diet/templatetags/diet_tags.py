from django import template

from apps.diet.models import DietRequest
from apps.diet.services import NOTICE_SESSION_KEY, is_profile_complete, trim_number

register = template.Library()


@register.filter
def num(value):
    return trim_number(value)


@register.inclusion_tag("diet/_health_notice.html", takes_context=True)
def health_profile_notice(context):
    """
    اعلان تکمیل پروفایل سلامت (اختیاری). با درخواست رژیم در انتظار پررنگ و همیشه نمایش داده می‌شود؛
    در غیر این صورت قابل بستن است.
    """
    request = context["request"]
    user = request.user

    if not user.is_authenticated or is_profile_complete(user):
        return {"show": False}

    has_pending = DietRequest.objects.filter(user=user, status=DietRequest.STATUS_PENDING).exists()
    if not has_pending and request.session.get(NOTICE_SESSION_KEY):
        return {"show": False}

    return {"show": True, "urgent": has_pending, "next": request.get_full_path(), "csrf_token": context.get("csrf_token")}
