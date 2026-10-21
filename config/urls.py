from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core.views import favicon

urlpatterns = [
    path("admin/", admin.site.urls),
    path("favicon.ico", favicon),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("appointments/", include("apps.appointments.urls")),
    path("shop/", include("apps.shop.urls")),
    path("payments/", include("apps.payments.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
