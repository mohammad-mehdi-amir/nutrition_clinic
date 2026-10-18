from dataclasses import dataclass

from .models import Product

CART_SESSION_KEY = "cart"


@dataclass
class CartLine:
    product: Product
    quantity: int

    @property
    def unit_price(self):
        return self.product.final_price

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class Cart:
    """
    سبد خرید در session. فقط شناسه‌ی محصول و تعداد ذخیره می‌شود؛
    قیمت و موجودی همیشه از دیتابیس خوانده می‌شود.
    """

    def __init__(self, request):
        self.session = request.session
        raw = self.session.get(CART_SESSION_KEY) or {}
        self._items = {str(k): int(v) for k, v in raw.items() if str(v).isdigit()}

    def _save(self):
        self.session[CART_SESSION_KEY] = self._items
        self.session.modified = True

    def quantity_of(self, product_id):
        return self._items.get(str(product_id), 0)

    def set(self, product, quantity):
        quantity = max(0, min(int(quantity), product.max_quantity))

        if quantity:
            self._items[str(product.pk)] = quantity
        else:
            self._items.pop(str(product.pk), None)

        self._save()
        return quantity

    def remove(self, product_id):
        self._items.pop(str(product_id), None)
        self._save()

    def clear(self):
        self._items = {}
        self._save()

    def lines(self):
        """اقلام معتبر سبد؛ محصولات حذف/غیرفعال‌شده کنار گذاشته می‌شوند."""
        products = Product.objects.available().filter(pk__in=self._items.keys()).select_related("category")
        by_id = {str(p.pk): p for p in products}

        if set(by_id) != set(self._items):
            self._items = {k: v for k, v in self._items.items() if k in by_id}
            self._save()

        return [CartLine(product=by_id[k], quantity=v) for k, v in self._items.items()]

    def __len__(self):
        return sum(self._items.values())

    def __bool__(self):
        return bool(self._items)
