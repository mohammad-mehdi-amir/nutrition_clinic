"""
تست‌های هم‌زمانی واقعی (چند thread، هر کدام اتصال دیتابیس جدا).
فقط روی PostgreSQL اجرا می‌شوند؛ SQLite قفل ردیف ندارد و کل دیتابیس را قفل می‌کند.

اجرا:
DB_ENGINE=postgres DB_NAME=... DB_USER=... DB_HOST=... DB_PORT=... python manage.py test apps.core.tests_concurrency
"""
import threading
import unittest
from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase

from apps.appointments.models import Appointment, Doctor, DoctorAvailability
from apps.appointments.services import book_appointment
from apps.appointments.tests import next_saturday
from apps.shop.cart import CartLine
from apps.shop.models import Order, Product
from apps.shop.services import OrderError, create_order


def run_concurrently(funcs):
    """همه‌ی توابع را هم‌زمان (پشت یک barrier) اجرا می‌کند و نتیجه یا استثنا را برمی‌گرداند."""
    barrier = threading.Barrier(len(funcs))
    results = [None] * len(funcs)

    def worker(index, func):
        try:
            barrier.wait()
            results[index] = ("ok", func())
        except Exception as error:  # noqa: BLE001 — نتیجه بررسی می‌شود
            results[index] = ("error", error)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker, args=(i, f)) for i, f in enumerate(funcs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


class StubCart:
    def __init__(self, product, quantity):
        self._lines = [CartLine(product, quantity)]

    def lines(self):
        return self._lines

    def clear(self):
        self._lines = []


@unittest.skipUnless(connection.vendor == "postgresql", "concurrency tests need PostgreSQL")
class ConcurrencyTests(TransactionTestCase):

    def test_same_slot_booked_concurrently_only_once(self):
        doctor = Doctor.objects.create(name="Dr", specialty="x", visit_fee=0)
        slot = DoctorAvailability.objects.create(doctor=doctor, day_of_week=0, time=time(10, 0))
        date = next_saturday() + timedelta(days=7)
        patients = [get_user_model().objects.create_user(username=f"p{i}") for i in range(5)]

        results = run_concurrently([
            (lambda p=p: book_appointment(p, slot.id, date)) for p in patients
        ])

        successes = [r for r in results if r[0] == "ok"]
        failures = [r for r in results if r[0] == "error"]
        self.assertEqual(len(successes), 1)
        self.assertTrue(all(isinstance(e, ValueError) for _, e in failures))
        self.assertEqual(Appointment.objects.filter(status__in=Appointment.ACTIVE_STATUSES).count(), 1)

    def test_last_item_sold_only_once(self):
        product = Product.objects.create(
            product_type="physical", name="آخرین", slug="last", short_description="x", price=100_000, stock=1,
        )
        buyers = [get_user_model().objects.create_user(username=f"b{i}") for i in range(5)]
        shipping = {
            "recipient_name": "x", "recipient_phone": "09120000000",
            "province": "تهران", "city": "تهران", "address": "x", "postal_code": "1234567890",
        }

        results = run_concurrently([
            (lambda u=u: create_order(u, StubCart(Product.objects.get(pk=product.pk), 1), shipping)) for u in buyers
        ])

        successes = [r for r in results if r[0] == "ok"]
        self.assertEqual(len(successes), 1)
        self.assertTrue(all(isinstance(e, OrderError) for kind, e in results if kind == "error"))
        product.refresh_from_db()
        self.assertEqual(product.stock, 0)
        self.assertEqual(Order.objects.count(), 1)
