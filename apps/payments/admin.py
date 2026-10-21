from django.contrib import admin
from jalali_date.admin import ModelAdminJalaliMixin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("created_at", "user", "target_display", "gateway", "amount", "status", "ref_id", "needs_review")
    list_filter = ("status", "gateway", "needs_review", "created_at")
    list_select_related = ("user", "appointment", "order")
    search_fields = ("ref_id", "authority", "user__username", "user__phone_number")
    readonly_fields = [f.name for f in Payment._meta.fields if f.name != "needs_review"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="بابت")
    def target_display(self, obj):
        return obj.description
