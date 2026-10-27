from django import forms
from django.contrib import admin, messages
from django.db.models import Count
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from jalali_date import datetime2jalali
from jalali_date.admin import ModelAdminJalaliMixin

from .models import DietRequest, DietTemplate, PatientDiet
from .services import DeliveryError, deliver_diet, get_health_stats


def download_link(field_file, label="دانلود PDF"):
    if not field_file:
        return "—"
    return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', field_file.url, label)


@admin.register(DietTemplate)
class DietTemplateAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("title", "goal", "calories", "deliveries_count", "is_active", "file_link")
    list_editable = ("is_active",)
    list_filter = ("is_active", "goal")
    search_fields = ("title", "description")
    readonly_fields = ("created_by", "created_at", "updated_at")
    fields = ("title", "goal", "calories", "description", "file", "is_active", "created_by", "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(deliveries_total=Count("deliveries"))

    @admin.display(description="تعداد ارسال", ordering="deliveries_total")
    def deliveries_count(self, obj):
        return obj.deliveries_total

    @admin.display(description="فایل")
    def file_link(self, obj):
        return download_link(obj.file)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class PatientDietInlineForm(forms.ModelForm):
    """تحویل رژیم: یا آپلود PDF یا انتخاب از رژیم‌های آماده (دقیقاً یکی)."""

    class Meta:
        model = PatientDiet
        fields = ("template", "file", "title", "note")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["template"].queryset = DietTemplate.objects.filter(is_active=True)
        self.fields["template"].label = "انتخاب از رژیم‌های آماده"
        self.fields["file"].required = False
        self.fields["file"].label = "یا آپلود PDF جدید"
        self.fields["title"].required = False
        self.fields["title"].help_text = "خالی ⇒ عنوان رژیم آماده. این عنوان را بیمار می‌بیند."
        self.fields["note"].widget.attrs["rows"] = 2

    def clean(self):
        cleaned = super().clean()
        # pk از نوع UUID با مقدار پیش‌فرض است؛ «جدید بودن» را از _state می‌خوانیم
        if not self.instance._state.adding or not self.has_changed():
            return cleaned

        template, uploaded = cleaned.get("template"), cleaned.get("file")
        if bool(template) == bool(uploaded):
            raise forms.ValidationError("یا یک رژیم آماده انتخاب کنید یا یک فایل PDF آپلود کنید (فقط یکی).")
        if uploaded and not cleaned.get("title"):
            self.add_error("title", "برای فایل آپلودی، عنوان رژیم را وارد کنید.")
        return cleaned


class PatientDietInline(admin.StackedInline):
    """فرم تحویل رژیم جدید؛ ردیف‌های قبلی در DeliveredDietInline نمایش داده می‌شوند."""

    model = PatientDiet
    form = PatientDietInlineForm
    fields = ("template", "file", "title", "note")
    can_delete = False
    verbose_name = "رژیم"
    verbose_name_plural = "ارسال رژیم (بیمار برای همیشه به آن دسترسی دارد)"

    def get_extra(self, request, obj=None, **kwargs):
        # درخواست در انتظار ⇒ یک فرم خالی آماده؛ در غیر این صورت با «افزودن» (مثلاً نسخه‌ی اصلاحی)
        return 1 if obj and obj.status == DietRequest.STATUS_PENDING else 0


class DeliveredDietInline(admin.TabularInline):
    """
    رژیم‌های تحویل‌شده، فقط‌خواندنی (برای اصلاح، نسخه‌ی جدید بفرستید).
    حذف فقط برای مدیر کل، مثلاً اگر فایل اشتباهی برای بیمار ارسال شده باشد.
    """

    model = PatientDiet
    extra = 0
    verbose_name_plural = "سابقه‌ی تحویل"
    fields = ("title", "file_link", "template", "delivered_by", "delivered_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description="فایل")
    def file_link(self, obj):
        return download_link(obj.file)


@admin.register(DietRequest)
class DietRequestAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ("package_name", "patient", "doctor", "status", "created_at", "waiting", "delivered_at")
    list_filter = ("status", "doctor", "created_at")
    list_select_related = ("user", "doctor")
    search_fields = ("user__username", "user__phone_number", "user__first_name", "user__last_name", "package_name")
    ordering = ("-status", "created_at")  # «در انتظار» اول، قدیمی‌ترین اول
    readonly_fields = ("patient", "order_link", "package_name", "status", "created_at", "delivered_at", "health_summary")
    fieldsets = (
        (None, {"fields": ("patient", "package_name", "order_link", "status", "created_at", "delivered_at")}),
        ("کارشناس", {"fields": ("doctor", "staff_note")}),
        ("پروفایل سلامت بیمار", {"fields": ("health_summary",)}),
    )
    inlines = [DeliveredDietInline, PatientDietInline]

    def has_add_permission(self, request):
        # درخواست فقط پس از پرداخت پکیج به‌طور خودکار ساخته می‌شود
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_inlines(self, request, obj):
        return [DeliveredDietInline, PatientDietInline] if obj and obj.diets.exists() else [PatientDietInline]

    @admin.display(description="بیمار", ordering="user__username")
    def patient(self, obj):
        name = obj.user.get_full_name()
        phone = obj.user.phone_number or obj.user.username
        return f"{name} ({phone})" if name else phone

    @admin.display(description="سفارش")
    def order_link(self, obj):
        order = obj.order_item.order
        url = reverse("admin:shop_order_change", args=[order.pk])
        return format_html('<a href="{}">سفارش #{}</a> — پرداخت: {}', url, order.pk,
                           datetime2jalali(timezone.localtime(order.paid_at)).strftime("%Y/%m/%d %H:%M") if order.paid_at else "—")

    @admin.display(description="انتظار")
    def waiting(self, obj):
        if obj.status == DietRequest.STATUS_DELIVERED:
            return "—"
        days = (timezone.now() - obj.created_at).days
        return "امروز" if days == 0 else f"{days} روز"

    @admin.display(description="اطلاعات سلامت")
    def health_summary(self, obj):
        stats = get_health_stats(obj.user)
        return render_to_string("admin/diet/health_summary.html", {"stats": stats, "profile": stats["profile"]})

    def get_formset_kwargs(self, request, obj, inline, prefix):
        kwargs = super().get_formset_kwargs(request, obj, inline, prefix)
        if isinstance(inline, PatientDietInline):
            # ردیف‌های قبلی در DeliveredDietInline نمایش داده می‌شوند؛ این فرم فقط برای تحویل جدید است
            kwargs["queryset"] = PatientDiet.objects.none()
        return kwargs

    def save_formset(self, request, form, formset, change):
        if not issubclass(formset.form, PatientDietInlineForm):
            # «سابقه‌ی تحویل»: فقط حذف (برای مدیر کل)
            return super().save_formset(request, form, formset, change)

        # به‌جای formset.save()، تحویل از مسیر سرویس (کپی فایل، وضعیت درخواست، پیامک)
        formset.new_objects, formset.changed_objects, formset.deleted_objects = [], [], []
        for inline_form in formset.forms:
            if not inline_form.instance._state.adding or not inline_form.has_changed() or not inline_form.cleaned_data:
                continue
            data = inline_form.cleaned_data
            try:
                diet = deliver_diet(
                    form.instance,
                    title=data.get("title", ""),
                    uploaded_file=data.get("file"),
                    template=data.get("template"),
                    note=data.get("note", ""),
                    by=request.user,
                )
            except DeliveryError as error:
                messages.error(request, str(error))
            else:
                formset.new_objects.append(diet)
                messages.success(request, "رژیم در پنل بیمار قرار گرفت و پیامک اطلاع‌رسانی ارسال شد.")
