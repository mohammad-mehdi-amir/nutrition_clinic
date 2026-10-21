from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import ShippingAddress
from apps.accounts.services import save_default_address
from apps.payments.views import redirect_to_gateway
from .cart import Cart
from .forms import CheckoutForm
from .locations import get_locations
from .models import Category, Order, Product
from .services import OrderError, calculate_totals, cancel_order, create_order

SORT_OPTIONS = {
    "newest": ("-created_at", "جدیدترین"),
    "cheapest": ("price", "ارزان‌ترین"),
    "expensive": ("-price", "گران‌ترین"),
}


def product_list(request, slug=None):
    products = Product.objects.available().select_related("category")
    category = None

    if slug:
        category = get_object_or_404(Category, slug=slug, is_active=True)
        products = products.filter(category=category)

    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(short_description__icontains=query)
        )

    product_type = request.GET.get("type")
    if product_type in dict(Product.TYPE_CHOICES):
        products = products.filter(product_type=product_type)

    sort = request.GET.get("sort", "newest")
    if sort not in SORT_OPTIONS:
        sort = "newest"
    products = products.order_by(SORT_OPTIONS[sort][0])

    page = Paginator(products, 12).get_page(request.GET.get("page"))

    return render(
        request,
        "shop/product_list.html",
        {
            "page_obj": page,
            "products": page.object_list,
            "categories": Category.objects.filter(is_active=True),
            "category": category,
            "query": query,
            "product_type": product_type,
            "sort": sort,
            "sort_options": [(key, label) for key, (_, label) in SORT_OPTIONS.items()],
            "type_choices": Product.TYPE_CHOICES,
        },
    )


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.available().select_related("category"), slug=slug)
    related = (
        Product.objects.available()
        .filter(product_type=product.product_type, category=product.category)
        .exclude(pk=product.pk)[:4]
    )

    return render(
        request,
        "shop/product_detail.html",
        {
            "product": product,
            "related_products": related,
            "in_cart": Cart(request).quantity_of(product.pk),
        },
    )


def package_list(request):
    return render(
        request,
        "shop/package_list.html",
        {"packages": Product.objects.available().filter(product_type=Product.TYPE_PACKAGE).order_by("price")},
    )


def cart_detail(request):
    cart = Cart(request)
    lines = cart.lines()
    return render(
        request,
        "shop/cart.html",
        {"lines": lines, "totals": calculate_totals(lines)},
    )


def _quantity_from(request, default=1):
    try:
        return int(request.POST.get("quantity", default))
    except (TypeError, ValueError):
        return default


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product.objects.available(), pk=product_id)
    cart = Cart(request)

    if not product.in_stock:
        messages.error(request, f"«{product.name}» در حال حاضر موجود نیست.")
        return redirect(product.get_absolute_url())

    requested = cart.quantity_of(product.pk) + max(1, _quantity_from(request))
    added = cart.set(product, requested)

    if added < requested:
        messages.warning(request, f"تعداد «{product.name}» به حداکثر مجاز ({added}) محدود شد.")
    else:
        messages.success(request, f"«{product.name}» به سبد خرید اضافه شد.")

    return redirect("shop:cart")


@require_POST
def cart_update(request, product_id):
    product = get_object_or_404(Product.objects.available(), pk=product_id)
    requested = _quantity_from(request, default=0)
    saved = Cart(request).set(product, requested)

    if saved < requested:
        messages.warning(request, f"تعداد «{product.name}» به حداکثر مجاز ({saved}) محدود شد.")

    return redirect("shop:cart")


@require_POST
def cart_remove(request, product_id):
    Cart(request).remove(product_id)
    return redirect("shop:cart")


@login_required
def checkout(request):
    cart = Cart(request)
    lines = cart.lines()

    if not lines:
        messages.info(request, "سبد خرید شما خالی است.")
        return redirect("shop:product_list")

    totals = calculate_totals(lines)
    saved_address = ShippingAddress.objects.filter(user=request.user).first()
    initial = saved_address.as_initial() if saved_address else {
        "recipient_name": request.user.get_full_name(),
        "recipient_phone": request.user.phone_number or "",
    }

    if request.method == "POST":
        form = CheckoutForm(request.POST, needs_shipping=totals.needs_shipping)

        if form.is_valid():
            try:
                order = create_order(request.user, cart, form.cleaned_data)
            except OrderError as error:
                messages.error(request, str(error))
                return redirect("shop:cart")

            if form.cleaned_data.get("save_address"):
                save_default_address(request.user, form.cleaned_data)

            messages.success(request, f"سفارش #{order.pk} ثبت شد.")
            return redirect_to_gateway(request, order, order.get_absolute_url())
    else:
        form = CheckoutForm(initial=initial, needs_shipping=totals.needs_shipping)

    return render(
        request,
        "shop/checkout.html",
        {
            "form": form,
            "lines": lines,
            "totals": totals,
            "iran_locations": get_locations() if totals.needs_shipping else None,
        },
    )


@login_required
def order_list(request):
    orders = request.user.orders.prefetch_related("items")
    return render(request, "shop/order_list.html", {"orders": orders, "panel_section": "orders"})


@login_required
def order_detail(request, pk):
    # فقط سفارش‌های خود کاربر؛ شناسه‌ی سفارش دیگران 404 می‌دهد
    order = get_object_or_404(request.user.orders.prefetch_related("items"), pk=pk)
    return render(
        request,
        "shop/order_detail.html",
        {"order": order, "panel_section": "order_detail", "panel_menu_key": "orders"},
    )


@login_required
@require_POST
def order_cancel(request, pk):
    order = get_object_or_404(request.user.orders, pk=pk)

    try:
        cancel_order(order)
    except OrderError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"سفارش #{order.pk} لغو شد.")

    return redirect(order.get_absolute_url())
