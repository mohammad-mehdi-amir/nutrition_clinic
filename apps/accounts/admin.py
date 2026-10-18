from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("اطلاعات تماس", {"fields": ("phone_number",)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("اطلاعات تماس", {"fields": ("phone_number",)}),
    )
    list_display = (
        "username",
        "first_name",
        "last_name",
        "phone_number",
        "is_staff",
        "is_active",
    )
    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
        "phone_number",
    )
