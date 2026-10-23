from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(RATELIMIT_ENABLED=True)
class RateLimitTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_login_limited_after_ten_posts(self):
        url = reverse("accounts:login")
        for _ in range(10):
            self.assertEqual(self.client.post(url, {"username": "x", "password": "y"}).status_code, 200)

        blocked = self.client.post(url, {"username": "x", "password": "y"})
        self.assertEqual(blocked.status_code, 429)
        self.assertContains(blocked, "تعداد درخواست‌ها بیش از حد مجاز است", status_code=429)

        # GET محدود نمی‌شود
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_limit_is_per_ip(self):
        url = reverse("core:contact")
        data = {"name": "a", "phone": "123", "message": "x"}  # نامعتبر؛ فقط شمارش مهم است
        for _ in range(5):
            self.client.post(url, data, REMOTE_ADDR="10.0.0.1")

        self.assertEqual(self.client.post(url, data, REMOTE_ADDR="10.0.0.1").status_code, 429)
        self.assertEqual(self.client.post(url, data, REMOTE_ADDR="10.0.0.2").status_code, 200)

    def test_forwarded_header_ignored_unless_configured(self):
        url = reverse("core:contact")
        data = {"name": "a", "phone": "123", "message": "x"}
        # کاربر با عوض کردن X-Real-IP نمی‌تواند محدودیت را دور بزند
        for i in range(6):
            response = self.client.post(url, data, HTTP_X_REAL_IP=f"1.1.1.{i}")
        self.assertEqual(response.status_code, 429)

    @override_settings(RATELIMIT_IP_HEADER="HTTP_X_REAL_IP")
    def test_proxy_header_used_when_configured(self):
        url = reverse("core:contact")
        data = {"name": "a", "phone": "123", "message": "x"}
        for _ in range(5):
            self.client.post(url, data, HTTP_X_REAL_IP="5.5.5.5")
        self.assertEqual(self.client.post(url, data, HTTP_X_REAL_IP="5.5.5.5").status_code, 429)
        self.assertEqual(self.client.post(url, data, HTTP_X_REAL_IP="6.6.6.6").status_code, 200)

    def test_admin_login_limited(self):
        url = reverse("admin:login")
        for _ in range(10):
            self.client.post(url, {"username": "x", "password": "y"})
        self.assertEqual(self.client.post(url, {"username": "x", "password": "y"}).status_code, 429)

    @override_settings(RATELIMIT_ENABLED=False)
    def test_can_be_disabled(self):
        url = reverse("accounts:login")
        for _ in range(12):
            response = self.client.post(url, {"username": "x", "password": "y"})
        self.assertEqual(response.status_code, 200)
