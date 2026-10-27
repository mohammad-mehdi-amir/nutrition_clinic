from django.contrib import admin, messages
from jalali_date.admin import ModelAdminJalaliMixin

from .models import Payment
from .services import RECONCILE_FAILED, RECONCILE_PAID, reconcile_payment


@admin.register(Payment)
class PaymentAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("created_at", "user", "target_display", "gateway", "amount", "status", "ref_id", "needs_review")
    list_filter = ("status", "gateway", "needs_review", "created_at")
    list_select_related = ("user", "appointment", "order")
    search_fields = ("ref_id", "authority", "user__username", "user__phone_number")
    readonly_fields = [f.name for f in Payment._meta.fields if f.name != "needs_review"]
    actions = ["inquire_from_gateway"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="بابت")
    def target_display(self, obj):
        return obj.description

    @admin.action(description="استعلام وضعیت از درگاه (تراکنش‌های «در حال پرداخت»)")
    def inquire_from_gateway(self, request, queryset):
        results = [reconcile_payment(pk) for pk in queryset.filter(status=Payment.STATUS_REDIRECTED).values_list("pk", flat=True)]
        self.message_user(
            request,
            f"{len(results)} تراکنش استعلام شد: {results.count(RECONCILE_PAID)} موفق، "
            f"{results.count(RECONCILE_FAILED)} ناموفق، بقیه هنوز نامشخص.",
            messages.INFO,
        )
