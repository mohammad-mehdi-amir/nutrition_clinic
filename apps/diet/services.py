from .models import DietRequest


def create_requests_for_order(order):
    """
    برای هر پکیج سفارش پرداخت‌شده یک درخواست رژیم می‌سازد.
    idempotent است (callback تکراری یا ذخیره‌ی دوباره‌ی ادمین درخواست تکراری نمی‌سازد).
    """
    from apps.shop.models import Product

    created = []
    for item in order.items.filter(product_type=Product.TYPE_PACKAGE):
        diet_request, is_new = DietRequest.objects.get_or_create(
            order_item=item,
            defaults={"user_id": order.user_id, "package_name": item.product_name},
        )
        if is_new:
            created.append(diet_request)
    return created
