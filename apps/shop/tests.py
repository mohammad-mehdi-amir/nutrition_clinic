from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import SiteSettings
from .cart import CartLine
from .models import Category, Order, Product
from .services import calculate_totals, expire_pending_orders

SHIPPING = {
    "recipient_name": "سارا احمدی",
    "recipient_phone": "09121234567",
    "province": "تهران",
    "city": "تهران",
    "address": "خیابان آزادی، پلاک ۱",
    "postal_code": "1234567890",
}


def make_physical(name="مکمل", price=100_000, stock=5, **extra):
    return Product.objects.create(
        product_type=Product.TYPE_PHYSICAL,
        name=name,
        slug=name,
        short_description="توضیح",
        price=price,
        stock=stock,
        **extra,
    )


def make_package(name="پکیج", price=500_000, **extra):
    return Product.objects.create(
        product_type=Product.TYPE_PACKAGE,
        name=name,
        slug=name,
        short_description="توضیح",
        price=price,
        duration_days=30,
        **extra,
    )


class ProductModelTests(TestCase):

    def test_clean_rules(self):
        with self.assertRaises(ValidationError):
            Product(product_type="physical", name="x", slug="x", short_description="x", price=10).full_clean()
        with self.assertRaises(ValidationError):
            Product(product_type="package", name="x", slug="x", short_description="x", price=10, stock=3, duration_days=30).full_clean()
        with self.assertRaises(ValidationError):
            Product(product_type="physical", name="x", slug="x", short_description="x", price=10, stock=1, discount_price=10).full_clean()

    def test_db_constraints(self):
        with transaction.atomic(), self.assertRaises(IntegrityError):
            Product.objects.create(product_type="physical", name="a", slug="a", short_description="x", price=10, stock=None)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            Product.objects.create(product_type="physical", name="b", slug="b", short_description="x", price=10, stock=1, discount_price=20)

    def test_inactive_category_hides_products(self):
        category = Category.objects.create(name="مکمل", slug="supplements", is_active=False)
        make_physical(category=category)
        self.assertFalse(Product.objects.available().exists())


class TotalsTests(TestCase):

    def setUp(self):
        self.settings = SiteSettings.objects.create(clinic_name="c", phone="1", shipping_cost=50_000, free_shipping_threshold=300_000)

    def test_shipping_only_for_physical(self):
        package = make_package()
        totals = calculate_totals([CartLine(package, 1)], self.settings)
        self.assertEqual((totals.subtotal, totals.shipping_cost, totals.total), (500_000, 0, 500_000))
        self.assertFalse(totals.needs_shipping)

    def test_shipping_and_free_threshold(self):
        product = make_physical(price=100_000, discount_price=80_000)
        self.assertEqual(calculate_totals([CartLine(product, 2)], self.settings).total, 160_000 + 50_000)
        self.assertEqual(calculate_totals([CartLine(product, 4)], self.settings).shipping_cost, 0)


class CartViewTests(TestCase):

    def test_add_respects_stock_and_package_limit(self):
        product = make_physical(stock=2)
        package = make_package()

        self.client.post(reverse("shop:cart_add", args=[product.pk]), {"quantity": 10})
        self.client.post(reverse("shop:cart_add", args=[package.pk]), {"quantity": 3})

        self.assertEqual(self.client.session["cart"], {str(product.pk): 2, str(package.pk): 1})

    def test_cannot_add_inactive_or_out_of_stock(self):
        inactive = make_physical(name="غیرفعال", is_active=False)
        empty = make_physical(name="تمام‌شده", stock=0)

        self.assertEqual(self.client.post(reverse("shop:cart_add", args=[inactive.pk])).status_code, 404)
        self.client.post(reverse("shop:cart_add", args=[empty.pk]))
        self.assertFalse(self.client.session.get("cart"))

    def test_cart_requires_post(self):
        product = make_physical()
        self.assertEqual(self.client.get(reverse("shop:cart_add", args=[product.pk])).status_code, 405)

    def test_update_to_zero_removes(self):
        product = make_physical()
        self.client.post(reverse("shop:cart_add", args=[product.pk]))
        self.client.post(reverse("shop:cart_update", args=[product.pk]), {"quantity": 0})
        self.assertEqual(self.client.session["cart"], {})

    def test_pages_render(self):
        product = make_physical()
        make_package()
        for url in [reverse("shop:product_list"), product.get_absolute_url(), reverse("shop:packages"), reverse("shop:cart")]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_search_and_type_filter(self):
        make_physical(name="پروتئین")
        make_package(name="رژیم کتو")
        response = self.client.get(reverse("shop:product_list"), {"q": "پروتئین"})
        self.assertContains(response, "پروتئین")
        self.assertNotContains(response, "رژیم کتو")
        response = self.client.get(reverse("shop:product_list"), {"type": "package"})
        self.assertContains(response, "رژیم کتو")
        self.assertNotContains(response, "پروتئین")


class CheckoutTests(TestCase):

    def setUp(self):
        SiteSettings.objects.create(clinic_name="c", phone="1", shipping_cost=40_000, order_payment_timeout_minutes=30)
        self.user = get_user_model().objects.create_user(username="09120000000", phone_number="09120000000", password="x")
        self.client.force_login(self.user)

    def _add(self, product, quantity=1):
        self.client.post(reverse("shop:cart_add", args=[product.pk]), {"quantity": quantity})

    def test_checkout_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("shop:checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_order_created_with_db_prices_and_stock_reserved(self):
        product = make_physical(price=100_000, stock=5)
        self._add(product, 2)

        response = self.client.post(reverse("shop:checkout"), {**SHIPPING, "total": 1})

        order = Order.objects.get()
        self.assertRedirects(response, order.get_absolute_url())
        self.assertEqual((order.subtotal, order.shipping_cost, order.total), (200_000, 40_000, 240_000))
        self.assertEqual(order.status, Order.STATUS_PENDING)
        self.assertAlmostEqual(order.payment_deadline, timezone.now() + timedelta(minutes=30), delta=timedelta(seconds=30))
        product.refresh_from_db()
        self.assertEqual(product.stock, 3)
        self.assertEqual(self.client.session["cart"], {})

    def test_price_snapshot_survives_price_change(self):
        product = make_physical(price=100_000)
        self._add(product)
        self.client.post(reverse("shop:checkout"), SHIPPING)

        product.price = 999_000
        product.save()

        item = Order.objects.get().items.get()
        self.assertEqual((item.unit_price, item.line_total, item.product_name), (100_000, 100_000, "مکمل"))

    def test_insufficient_stock_rejected(self):
        product = make_physical(stock=3)
        self._add(product, 3)
        Product.objects.filter(pk=product.pk).update(stock=1)  # کسی دیگر خرید کرد

        response = self.client.post(reverse("shop:checkout"), SHIPPING, follow=True)

        self.assertFalse(Order.objects.exists())
        self.assertContains(response, "کافی نیست")
        product.refresh_from_db()
        self.assertEqual(product.stock, 1)

    def test_package_only_order_needs_no_address(self):
        self._add(make_package())
        self.client.post(reverse("shop:checkout"), {"recipient_name": "سارا", "recipient_phone": "09121234567"})
        order = Order.objects.get()
        self.assertEqual((order.address, order.shipping_cost), ("", 0))

    def test_physical_order_requires_address(self):
        self._add(make_physical())
        response = self.client.post(reverse("shop:checkout"), {"recipient_name": "سارا", "recipient_phone": "09121234567"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())

    def test_cancel_restores_stock(self):
        product = make_physical(stock=5)
        self._add(product, 2)
        self.client.post(reverse("shop:checkout"), SHIPPING)
        order = Order.objects.get()

        self.client.post(reverse("shop:order_cancel", args=[order.pk]))

        order.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CANCELLED)
        self.assertEqual(product.stock, 5)

    def test_other_users_order_is_404(self):
        product = make_physical()
        self._add(product)
        self.client.post(reverse("shop:checkout"), SHIPPING)
        order = Order.objects.get()

        other = get_user_model().objects.create_user(username="other")
        self.client.force_login(other)

        self.assertEqual(self.client.get(order.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.post(reverse("shop:order_cancel", args=[order.pk])).status_code, 404)
        self.assertEqual(Order.objects.get().status, Order.STATUS_PENDING)

    def test_expired_orders_cancelled_and_stock_released(self):
        product = make_physical(stock=5)
        self._add(product, 2)
        self.client.post(reverse("shop:checkout"), SHIPPING)
        Order.objects.update(payment_deadline=timezone.now() - timedelta(minutes=1))

        call_command("expire_pending_orders", stdout=open("/dev/null", "w"))

        product.refresh_from_db()
        self.assertEqual(Order.objects.get().status, Order.STATUS_CANCELLED)
        self.assertEqual(product.stock, 5)
        self.assertEqual(expire_pending_orders(), 0)

    def test_order_pages_render(self):
        self._add(make_physical())
        self.client.post(reverse("shop:checkout"), SHIPPING)
        order = Order.objects.get()
        self.assertContains(self.client.get(reverse("shop:order_list")), f"#{order.pk}")
        self.assertContains(self.client.get(order.get_absolute_url()), "مکمل")


class CheckoutLocationTests(TestCase):

    def setUp(self):
        from .forms import CheckoutForm
        self.Form = CheckoutForm

    def _data(self, **overrides):
        return {**SHIPPING, **overrides}

    def test_locations_data_loaded(self):
        from .locations import get_locations, is_valid_city
        locations = get_locations()
        self.assertEqual(len(locations), 31)
        self.assertTrue(is_valid_city("خراسان رضوی", "مشهد"))
        self.assertTrue(is_valid_city("سیستان و بلوچستان", "زاهدان"))
        self.assertFalse(is_valid_city("تهران", "مشهد"))

    def test_valid_province_and_city(self):
        form = self.Form(self._data(province="خراسان رضوی", city="مشهد"))
        self.assertTrue(form.is_valid(), form.errors)

    def test_city_from_another_province_rejected(self):
        form = self.Form(self._data(province="تهران", city="مشهد"))
        self.assertFalse(form.is_valid())
        self.assertIn("city", form.errors)

    def test_unknown_province_rejected(self):
        form = self.Form(self._data(province="استان ناموجود", city="تهران"))
        self.assertFalse(form.is_valid())
        self.assertIn("province", form.errors)

    def test_city_choices_follow_selected_province(self):
        form = self.Form(self._data(province="قم", city=""))
        cities = [value for value, _ in form.fields["city"].choices if value]
        self.assertIn("قم", cities)
        self.assertNotIn("تهران", cities)

    def test_checkout_page_embeds_locations_json(self):
        user = get_user_model().objects.create_user(username="u1")
        self.client.force_login(user)
        product = make_physical()
        self.client.post(reverse("shop:cart_add", args=[product.pk]))
        response = self.client.get(reverse("shop:checkout"))
        self.assertContains(response, 'id="iran-locations"')
        self.assertContains(response, "data-province-select")
        self.assertContains(response, "js/province-city.js")
