"""
راهنمای پنل ادمین کامل بماند: هر فیلد توضیح دارد، هر بخش کادر راهنما دارد و همه‌ی صفحات باز می‌شوند.
اگر فیلد یا بخش جدیدی بدون توضیح اضافه شود، این تست شکست می‌خورد.
"""
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import NoReverseMatch, reverse

from apps.core.admin_guides import get_guide

# فیلدهایی که در فرم یا فهرست ادمین دیده نمی‌شوند (شناسه‌های داخلی)
IGNORED = {"id"}


def admin_models():
    """همه‌ی مدل‌های ثبت‌شده در ادمین به‌همراه مدل‌های inline آن‌ها."""
    seen = {}
    for model, model_admin in admin.site._registry.items():
        seen[model] = model_admin
        for inline in model_admin.inlines:
            seen.setdefault(inline.model, None)
    return seen


class AdminHelpCompletenessTests(TestCase):

    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(username="admin", password="x")
        self.client.force_login(self.admin_user)
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.admin_user

    def test_every_field_has_help_text(self):
        missing = []
        for model, model_admin in admin_models().items():
            if model._meta.app_label == "auth" or model is get_user_model():
                # مدل‌های خود Django: توضیح‌ها روی فرم ادمین اعمال می‌شود (فرم افزودن و فرم ویرایش)
                obj = self.admin_user if model is get_user_model() else None
                forms = [model_admin.get_form(self.request), model_admin.get_form(self.request, obj)]
                for form in forms:
                    missing += [f"{model.__name__}.{name}" for name, field in form.base_fields.items() if not field.help_text]
                continue
            fields = [f for f in model._meta.get_fields() if getattr(f, "concrete", False) and not f.auto_created]
            missing += [f"{model.__name__}.{f.name}" for f in fields if f.name not in IGNORED and not f.help_text]
        self.assertEqual(missing, [], "فیلد بدون توضیح در ادمین")

    def test_every_section_has_a_guide(self):
        missing = [model.__name__ for model in admin.site._registry if not get_guide(model._meta)]
        self.assertEqual(missing, [], "بخش بدون کادر راهنما")

    def test_every_section_renders_with_guide(self):
        for model, model_admin in admin.site._registry.items():
            info = (model._meta.app_label, model._meta.model_name)
            with self.subTest(model=model.__name__):
                changelist = self.client.get(reverse("admin:%s_%s_changelist" % info))
                self.assertEqual(changelist.status_code, 200)
                self.assertContains(changelist, "راهنمای این بخش")
                if model_admin.has_add_permission(self.request):
                    try:
                        add_url = reverse("admin:%s_%s_add" % info)
                    except NoReverseMatch:
                        continue
                    self.assertEqual(self.client.get(add_url).status_code, 200)

    def test_index_shows_daily_tasks_with_links(self):
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "کارهای امروز")
        self.assertContains(response, "درخواست‌های رژیم در انتظار")
        self.assertContains(response, reverse("admin:diet_dietrequest_changelist") + "?status__exact=pending")

    def test_daily_tasks_respect_permissions(self):
        from django.contrib.auth.models import Permission
        staff = get_user_model().objects.create_user(username="staff", password="x", is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename="view_dietrequest"))
        self.client.force_login(staff)
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "درخواست‌های رژیم در انتظار")
        self.assertNotContains(response, "سفارش‌های پرداخت‌شده‌ی منتظر ارسال")

    def test_daily_task_links_filter_lists(self):
        for url in (
            reverse("admin:appointments_appointment_changelist") + "?payment_status__exact=refund_requested",
            reverse("admin:shop_order_changelist") + "?status__exact=paid",
            reverse("admin:core_contactmessage_changelist") + "?is_read__exact=0",
            reverse("admin:payments_payment_changelist") + "?needs_review__exact=1",
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "?e=1")  # Django برای فیلتر نامعتبر به ?e=1 هدایت می‌کند
