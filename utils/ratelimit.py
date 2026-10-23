"""
محدودیت نرخ درخواست ساده (پنجره‌ی ثابت) روی کش جنگو، بدون پکیج اضافه.

- شناسه‌ی کاربر: IP. پشت Nginx فقط وقتی RATELIMIT_IP_HEADER (مثلاً HTTP_X_REAL_IP) تنظیم شود به هدر اعتماد می‌شود؛
  در غیر این صورت REMOTE_ADDR (تا کاربر نتواند IP جعلی بفرستد).
- با چند پروسس gunicorn کش باید مشترک باشد (CACHE_BACKEND=database یا Redis).
"""
import logging
import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render

logger = logging.getLogger(__name__)


def client_ip(request):
    header = getattr(settings, "RATELIMIT_IP_HEADER", "")
    if header and request.META.get(header):
        return request.META[header].split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def is_limited(key, request, limit, window):
    """True اگر این درخواست از سقف مجاز پنجره‌ی فعلی بیشتر باشد (و شمارنده را افزایش می‌دهد)."""
    if not getattr(settings, "RATELIMIT_ENABLED", True):
        return False

    window_start = int(time.time() // window)
    cache_key = f"rl:{key}:{client_ip(request)}:{window_start}"

    if cache.add(cache_key, 1, timeout=window):
        return False

    try:
        count = cache.incr(cache_key)
    except ValueError:  # کلید همین لحظه منقضی شد
        cache.add(cache_key, 1, timeout=window)
        return False

    return count > limit


def ratelimit(key, limit, window, methods=("POST",)):
    """
    @ratelimit("login", limit=10, window=600) — حداکثر ۱۰ درخواست POST در ۱۰ دقیقه از هر IP.
    """
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method in methods and is_limited(key, request, limit, window):
                logger.warning("Rate limit hit: %s from %s", key, client_ip(request))
                minutes = max(1, window // 60)
                return render(request, "429.html", {"retry_minutes": minutes}, status=429)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
