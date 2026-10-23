from django import template

register = template.Library()

# (کلید بخش، نام URL، آیکون feather، عنوان) — تنها محل تعریف منوی پنل کاربری
PANEL_MENU = [
    ("dashboard", "accounts:dashboard", "icon-grid", "داشبورد"),
    ("appointments", "appointments:my_appointments", "icon-calendar", "نوبت‌های من"),
    ("orders", "shop:order_list", "icon-shopping-bag", "سفارش‌های من"),
    ("packages", "accounts:packages", "icon-clipboard", "پکیج‌های من"),
    ("health", "diet:health_profile", "icon-activity", "پروفایل سلامت"),
    ("payments", "accounts:payments", "icon-credit-card", "پرداخت‌ها"),
    ("profile", "accounts:profile", "icon-user", "اطلاعات حساب"),
    ("address", "accounts:address", "icon-map-pin", "نشانی پیش‌فرض"),
    ("password", "accounts:password_change", "icon-lock", "تغییر رمز عبور"),
]

EXTRA_TITLES = {"order_detail": "جزئیات سفارش"}


@register.simple_tag
def get_panel_menu():
    return PANEL_MENU


@register.simple_tag
def panel_title(section):
    for key, _, _, label in PANEL_MENU:
        if key == section:
            return label
    return EXTRA_TITLES.get(section, "حساب کاربری")
