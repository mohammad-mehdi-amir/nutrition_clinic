from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from jalali_date.admin import ModelAdminJalaliMixin

from apps.core.admin_guides import GROUP_FIELD_HELP, USER_FIELD_HELP

from .models import ShippingAddress, User


def apply_field_help(form, texts):
    """متن راهنمای فیلدهای مدل‌های خود Django روی فرم ادمین."""
    for name, text in texts.items():
        if name in form.base_fields:
            form.base_fields[name].help_text = text
    return form


class ShippingAddressInline(admin.StackedInline):
    model = ShippingAddress
    extra = 0
    can_delete = True


@admin.register(User)
class UserAdmin(ModelAdminJalaliMixin, BaseUserAdmin):
    inlines = [ShippingAddressInline]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("اطلاعات تماس", {
            "fields": ("phone_number",),
            "description": "شماره‌ی موبایل برای ورود، بازیابی رمز و پیامک‌های سایت استفاده می‌شود.",
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("اطلاعات تماس", {
            "fields": ("phone_number",),
            "description": "برای بیماران، نام کاربری و شماره‌ی موبایل را یکسان وارد کنید (مثال: 09121234567).",
        }),
    )
    list_display = (
        "username",
        "first_name",
        "last_name",
        "phone_number",
        "is_staff",
        "is_active",
        "date_joined",
    )
    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
        "phone_number",
    )

    def get_form(self, request, obj=None, **kwargs):
        return apply_field_help(super().get_form(request, obj, **kwargs), USER_FIELD_HELP)


admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin):
    def get_form(self, request, obj=None, **kwargs):
        return apply_field_help(super().get_form(request, obj, **kwargs), GROUP_FIELD_HELP)
