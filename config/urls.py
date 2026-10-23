from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.core.views import favicon, health, robots_txt
from config.sitemaps import SITEMAPS
from utils.ratelimit import ratelimit

# ورود ادمین هم در برابر حدس رمز محدود می‌شود
admin.site.login = ratelimit("admin_login", limit=10, window=600)(admin.site.login)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("favicon.ico", favicon),
    path("robots.txt", robots_txt),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("health/", health, name="health"),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("appointments/", include("apps.appointments.urls")),
    path("shop/", include("apps.shop.urls")),
    path("payments/", include("apps.payments.urls")),
    path("blog/", include("apps.blog.urls")),
    path("diet/", include("apps.diet.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
