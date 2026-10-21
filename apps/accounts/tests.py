from django.test import TestCase
from django.urls import reverse

from .models import User


class RegisterTests(TestCase):

    def _data(self, **overrides):
        data = {
            "first_name": "سارا",
            "last_name": "احمدی",
            "phone_number": "09121234567",
            "password1": "Str0ng-Pass-9876",
            "password2": "Str0ng-Pass-9876",
        }
        data.update(overrides)
        return data

    def test_register_creates_user_with_phone_as_username_and_logs_in(self):
        response = self.client.post(reverse("accounts:register"), self._data())

        self.assertRedirects(response, reverse("accounts:dashboard"))
        user = User.objects.get()
        self.assertEqual(user.username, "09121234567")
        self.assertEqual(user.phone_number, "09121234567")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_persian_digits_normalized(self):
        self.client.post(reverse("accounts:register"), self._data(phone_number="۰۹۱۲۱۲۳۴۵۶۷"))
        self.assertEqual(User.objects.get().phone_number, "09121234567")

    def test_duplicate_phone_rejected(self):
        User.objects.create_user(username="09121234567", phone_number="09121234567", password="x")
        response = self.client.post(reverse("accounts:register"), self._data())
        self.assertContains(response, "قبلاً ثبت‌نام شده است")
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_phone_rejected(self):
        response = self.client.post(reverse("accounts:register"), self._data(phone_number="0912"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_safe_next_redirect(self):
        response = self.client.post(
            reverse("accounts:register"),
            self._data(next=reverse("appointments:book_appointment")),
        )
        self.assertRedirects(response, reverse("appointments:book_appointment"))

    def test_external_next_ignored(self):
        response = self.client.post(
            reverse("accounts:register"),
            self._data(next="https://evil.example.com/"),
        )
        self.assertRedirects(response, reverse("accounts:dashboard"))


class LoginLogoutTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="09121234567",
            phone_number="09121234567",
            password="Str0ng-Pass-9876",
        )

    def test_protected_page_redirects_to_login(self):
        response = self.client.get(reverse("appointments:my_appointments"))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('appointments:my_appointments')}",
        )

    def test_login_with_persian_digit_phone(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "۰۹۱۲۱۲۳۴۵۶۷", "password": "Str0ng-Pass-9876"},
        )
        self.assertRedirects(response, reverse("accounts:dashboard"))

    def test_logout_requires_post(self):
        self.client.force_login(self.user)

        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)

        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("core:home"))
        self.assertNotIn("_auth_user_id", self.client.session)


from datetime import timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from .models import PasswordResetCode
from .services import MAX_ATTEMPTS


@override_settings(SMS_BACKEND="apps.accounts.sms.ConsoleSMSBackend")
class PasswordResetTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="09121234567", phone_number="09121234567", password="Old-Pass-1234"
        )
        self.sent = []
        patcher = mock.patch(
            "apps.accounts.services.send_verification_code",
            side_effect=lambda phone, code: self.sent.append((phone, code)),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _request(self, phone="09121234567"):
        return self.client.post(reverse("accounts:password_reset"), {"phone_number": phone})

    def _verify(self, code, password="New-Pass-98765"):
        return self.client.post(
            reverse("accounts:password_reset_verify"),
            {"code": code, "new_password1": password, "new_password2": password},
        )

    def test_full_flow_changes_password(self):
        response = self._request("۰۹۱۲۱۲۳۴۵۶۷")
        self.assertRedirects(response, reverse("accounts:password_reset_verify"))
        phone, code = self.sent[0]
        self.assertEqual(phone, "09121234567")

        response = self._verify(code)

        self.assertRedirects(response, reverse("accounts:login"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("New-Pass-98765"))
        self.assertTrue(self.client.login(username="09121234567", password="New-Pass-98765"))

    def test_code_is_stored_hashed(self):
        self._request()
        code = self.sent[0][1]
        self.assertNotIn(code, PasswordResetCode.objects.get().code_hash)

    def test_unknown_phone_gets_same_response_without_sms(self):
        response = self._request("09350000000")
        self.assertRedirects(response, reverse("accounts:password_reset_verify"))
        self.assertEqual(self.sent, [])

    def test_resend_rate_limited(self):
        self._request()
        response = self._request()
        self.assertContains(response, "دو دقیقه بعد")
        self.assertEqual(len(self.sent), 1)

    def test_wrong_code_counts_attempts_and_locks(self):
        self._request()
        real = self.sent[0][1]
        wrong = "000000" if real != "000000" else "111111"

        for _ in range(MAX_ATTEMPTS):
            self.assertContains(self._verify(wrong), "صحیح نیست")

        self.assertEqual(PasswordResetCode.objects.get().attempts, MAX_ATTEMPTS)
        self.assertContains(self._verify(real), "تلاش‌های ناموفق")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Old-Pass-1234"))

    def test_expired_code_rejected(self):
        self._request()
        PasswordResetCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertContains(self._verify(self.sent[0][1]), "منقضی")

    def test_code_is_single_use(self):
        self._request()
        code = self.sent[0][1]
        self._verify(code)
        session = self.client.session
        session["password_reset_phone"] = "09121234567"
        session.save()
        self.assertContains(self._verify(code, "Another-Pass-555"), "منقضی")

    def test_weak_password_rejected(self):
        self._request()
        response = self._verify(self.sent[0][1], password="123")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Old-Pass-1234"))

    def test_verify_without_session_redirects(self):
        response = self.client.get(reverse("accounts:password_reset_verify"))
        self.assertRedirects(response, reverse("accounts:password_reset"))

    def test_login_page_links_to_reset(self):
        self.assertContains(self.client.get(reverse("accounts:login")), reverse("accounts:password_reset"))



class AccountPanelTests(TestCase):

    PANEL_URLS = ["dashboard", "profile", "password_change", "address", "packages", "payments"]

    def setUp(self):
        self.user = User.objects.create_user(
            username="09121112233", phone_number="09121112233", password="Old-Pass-1234",
            first_name="سارا", last_name="احمدی",
        )
        self.other = User.objects.create_user(username="09124445566", phone_number="09124445566", password="x")

    def test_panel_pages_require_login(self):
        for name in self.PANEL_URLS:
            with self.subTest(page=name):
                response = self.client.get(reverse(f"accounts:{name}"))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response["Location"])

    def test_panel_pages_render(self):
        self.client.force_login(self.user)
        for name in self.PANEL_URLS + []:
            with self.subTest(page=name):
                response = self.client.get(reverse(f"accounts:{name}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "منوی حساب کاربری")
        for url in [reverse("appointments:my_appointments"), reverse("shop:order_list")]:
            self.assertContains(self.client.get(url), "منوی حساب کاربری")

    def test_profile_update_cannot_change_phone(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), {
            "first_name": "مریم", "last_name": "رضایی", "email": "m@example.com",
            "phone_number": "09350000000", "username": "hacker",
        })
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.email), ("مریم", "m@example.com"))
        self.assertEqual((self.user.phone_number, self.user.username), ("09121112233", "09121112233"))

    def test_password_change(self):
        self.client.force_login(self.user)
        url = reverse("accounts:password_change")

        wrong = self.client.post(url, {"old_password": "bad", "new_password1": "New-Pass-98765", "new_password2": "New-Pass-98765"})
        self.assertEqual(wrong.status_code, 200)

        weak = self.client.post(url, {"old_password": "Old-Pass-1234", "new_password1": "123", "new_password2": "123"})
        self.assertEqual(weak.status_code, 200)

        ok = self.client.post(url, {"old_password": "Old-Pass-1234", "new_password1": "New-Pass-98765", "new_password2": "New-Pass-98765"})
        self.assertRedirects(ok, reverse("accounts:profile"))
        # session معتبر می‌ماند
        self.assertEqual(self.client.get(reverse("accounts:dashboard")).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("New-Pass-98765"))

    def test_address_saved_and_city_validated(self):
        from .models import ShippingAddress
        self.client.force_login(self.user)
        data = {"recipient_name": "سارا", "recipient_phone": "09121112233", "province": "تهران", "city": "مشهد", "address": "خیابان یک", "postal_code": "1234567890"}

        bad = self.client.post(reverse("accounts:address"), data)
        self.assertEqual(bad.status_code, 200)
        self.assertFalse(ShippingAddress.objects.exists())

        data["city"] = "تهران"
        self.assertRedirects(self.client.post(reverse("accounts:address"), data), reverse("accounts:address"))
        self.assertEqual(ShippingAddress.objects.get(user=self.user).city, "تهران")

    def test_payments_page_shows_only_own_payments(self):
        from apps.payments.models import Payment
        from apps.shop.models import Order
        mine = Order.objects.create(user=self.user, recipient_name="a", recipient_phone="09121112233", subtotal=1, total=111_111)
        theirs = Order.objects.create(user=self.other, recipient_name="b", recipient_phone="09124445566", subtotal=1, total=999_999)
        Payment.objects.create(user=self.user, order=mine, gateway="fake", amount=111_111, status="paid", ref_id="MINE1")
        Payment.objects.create(user=self.other, order=theirs, gateway="fake", amount=999_999, status="paid", ref_id="THEIRS1")

        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:payments"))
        self.assertContains(response, "MINE1")
        self.assertNotContains(response, "THEIRS1")
