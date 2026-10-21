from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.models import SiteSettings
from .cart import CartLine
from .models import Order, OrderItem, Product


class OrderError(Exception):
    """خطای قابل نمایش به کاربر در فرایند سفارش."""


@dataclass
class Totals:
    subtotal: int
    shipping_cost: int
    total: int
    needs_shipping: bool


def calculate_totals(lines, site_settings=None):
    """
    تنها محل محاسبه‌ی مبلغ سفارش. lines: اشیای دارای product و quantity.
    هزینه‌ی ارسال فقط وقتی اعمال می‌شود که کالای فیزیکی در سبد باشد.
    """
    site_settings = site_settings or SiteSettings.load()

    subtotal = sum(line.product.final_price * line.quantity for line in lines)
    needs_shipping = any(not line.product.is_package for line in lines)

    shipping_cost = 0
    if needs_shipping:
        threshold = site_settings.free_shipping_threshold
        if not (threshold and subtotal >= threshold):
            shipping_cost = site_settings.shipping_cost

    return Totals(
        subtotal=subtotal,
        shipping_cost=shipping_cost,
        total=subtotal + shipping_cost,
        needs_shipping=needs_shipping,
    )


def create_order(user, cart, shipping_data):
    """
    ثبت سفارش از روی سبد. قیمت‌ها از دیتابیس و موجودی با قفل ردیف کسر می‌شود.
    shipping_data: cleaned_data فرم تسویه‌حساب.
    """
    requested = {line.product.pk: line.quantity for line in cart.lines()}

    if not requested:
        raise OrderError("سبد خرید شما خالی است.")

    site_settings = SiteSettings.load()

    with transaction.atomic():
        products = {
            p.pk: p
            for p in Product.objects.select_for_update().filter(pk__in=requested.keys())
        }

        lines = []
        for product_id, quantity in requested.items():
            product = products.get(product_id)

            if product is None or not product.is_active:
                raise OrderError("یکی از محصولات سبد دیگر موجود نیست. سبد را بررسی کنید.")

            if quantity > product.max_quantity:
                raise OrderError(f"موجودی «{product.name}» کافی نیست. سبد را بررسی کنید.")

            lines.append((product, quantity))

        totals = calculate_totals([CartLine(p, q) for p, q in lines], site_settings)

        order = Order.objects.create(
            user=user,
            recipient_name=shipping_data["recipient_name"],
            recipient_phone=shipping_data["recipient_phone"],
            province=shipping_data.get("province", "") if totals.needs_shipping else "",
            city=shipping_data.get("city", "") if totals.needs_shipping else "",
            address=shipping_data.get("address", "") if totals.needs_shipping else "",
            postal_code=shipping_data.get("postal_code", "") if totals.needs_shipping else "",
            note=shipping_data.get("note", ""),
            subtotal=totals.subtotal,
            shipping_cost=totals.shipping_cost,
            total=totals.total,
            payment_deadline=timezone.now() + timedelta(minutes=site_settings.order_payment_timeout_minutes),
        )

        OrderItem.objects.bulk_create([
            OrderItem(
                order=order,
                product=product,
                product_name=product.name,
                product_type=product.product_type,
                unit_price=product.final_price,
                quantity=quantity,
                line_total=product.final_price * quantity,
            )
            for product, quantity in lines
        ])

        for product, quantity in lines:
            if not product.is_package:
                product.stock -= quantity
                product.save(update_fields=["stock", "updated_at"])

    cart.clear()
    return order


def cancel_order(order):
    """لغو سفارش در انتظار پرداخت و برگرداندن موجودی رزروشده."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)

        if order.status != Order.STATUS_PENDING:
            raise OrderError("فقط سفارش‌های در انتظار پرداخت قابل لغو هستند.")

        items = list(order.items.filter(product__isnull=False, product_type=Product.TYPE_PHYSICAL))
        products = {
            p.pk: p
            for p in Product.objects.select_for_update().filter(pk__in=[i.product_id for i in items])
        }

        for item in items:
            product = products[item.product_id]
            product.stock = (product.stock or 0) + item.quantity
            product.save(update_fields=["stock", "updated_at"])

        order.status = Order.STATUS_CANCELLED
        order.payment_deadline = None
        order.save(update_fields=["status", "payment_deadline", "updated_at"])

    return order


def expire_pending_orders():
    """لغو سفارش‌هایی که مهلت پرداختشان گذشته. تعداد لغوشده‌ها را برمی‌گرداند."""
    expired = Order.objects.filter(
        status=Order.STATUS_PENDING,
        payment_deadline__lte=timezone.now(),
    ).values_list("pk", flat=True)

    count = 0
    for pk in list(expired):
        try:
            cancel_order(Order(pk=pk))
            count += 1
        except OrderError:
            # وضعیت هم‌زمان تغییر کرده (مثلاً پرداخت شده)
            continue

    return count


def mark_order_paid(order):
    """
    اعمال پرداخت موفق درگاه. True یعنی سفارش پرداخت‌شده شد؛
    False یعنی سفارش منقضی شده و موجودی دیگر کافی نبود (نیاز به بازپرداخت توسط ادمین).
    """
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)

        if order.status == Order.STATUS_PAID:
            return True

        if order.status == Order.STATUS_PENDING:
            order.status = Order.STATUS_PAID
            order.payment_deadline = None
            order.save(update_fields=["status", "payment_deadline", "updated_at"])
            return True

        if order.status != Order.STATUS_CANCELLED:
            return False

        # سفارش هنگام پرداخت منقضی شده و موجودی آزاد شده؛ در صورت امکان دوباره رزرو می‌کنیم
        items = list(order.items.filter(product__isnull=False, product_type=Product.TYPE_PHYSICAL))
        products = {
            p.pk: p
            for p in Product.objects.select_for_update().filter(pk__in=[i.product_id for i in items])
        }

        if any((products[i.product_id].stock or 0) < i.quantity for i in items):
            return False

        for item in items:
            product = products[item.product_id]
            product.stock -= item.quantity
            product.save(update_fields=["stock", "updated_at"])

        order.status = Order.STATUS_PAID
        order.save(update_fields=["status", "updated_at"])
        return True
