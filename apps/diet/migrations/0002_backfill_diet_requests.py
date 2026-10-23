from django.db import migrations

PAID_ORDER_STATUSES = ("paid", "processing", "shipped", "completed")


def create_requests_for_paid_packages(apps, schema_editor):
    """برای پکیج‌هایی که قبل از این قابلیت پرداخت شده‌اند هم درخواست رژیم ساخته می‌شود."""
    OrderItem = apps.get_model("shop", "OrderItem")
    DietRequest = apps.get_model("diet", "DietRequest")

    items = OrderItem.objects.filter(
        product_type="package",
        order__status__in=PAID_ORDER_STATUSES,
        diet_request__isnull=True,
    ).select_related("order")

    for item in items:
        diet_request = DietRequest.objects.create(
            user_id=item.order.user_id,
            order_item=item,
            package_name=item.product_name,
        )
        # زمان ثبت = زمان پرداخت (auto_now_add هنگام create مقدار را بازنویسی می‌کند)
        DietRequest.objects.filter(pk=diet_request.pk).update(
            created_at=item.order.paid_at or item.order.created_at
        )


class Migration(migrations.Migration):

    dependencies = [
        ("diet", "0001_initial"),
        ("shop", "0002_order_paid_at"),
    ]

    operations = [
        migrations.RunPython(create_requests_for_paid_packages, migrations.RunPython.noop),
    ]
