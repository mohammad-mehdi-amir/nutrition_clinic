from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from utils.ratelimit import ratelimit
from django.utils.http import url_has_allowed_host_and_scheme

from apps.payments.models import Payment
from apps.shop.forms import ShippingAddressForm
from apps.shop.locations import get_locations
from .forms import (
    LoginForm,
    PasswordResetRequestForm,
    PasswordResetVerifyForm,
    ProfileForm,
    RegisterForm,
    UserPasswordChangeForm,
)
from .models import ShippingAddress
from .services import (
    ResetError,
    get_dashboard_summary,
    request_reset_code,
    save_default_address,
    verify_and_reset,
)


@method_decorator(ratelimit("login", limit=10, window=600), name="dispatch")
class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


@ratelimit("register", limit=5, window=3600)
def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    next_url = request.POST.get("next") or request.GET.get("next")

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "ثبت‌نام شما با موفقیت انجام شد.")

            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)

            return redirect("accounts:dashboard")
    else:
        form = RegisterForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form, "next": next_url or ""},
    )


RESET_SESSION_KEY = "password_reset_phone"


@ratelimit("password_reset", limit=10, window=3600)
def password_reset_request(request):
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)

        if form.is_valid():
            phone = form.cleaned_data["phone_number"]

            try:
                request_reset_code(phone)
            except ResetError as error:
                form.add_error(None, str(error))
            else:
                request.session[RESET_SESSION_KEY] = phone
                messages.info(
                    request,
                    "اگر این شماره در سایت ثبت‌نام کرده باشد، کد تأیید برایش پیامک شد.",
                )
                return redirect("accounts:password_reset_verify")
    else:
        form = PasswordResetRequestForm()

    return render(request, "accounts/password_reset_request.html", {"form": form})


@ratelimit("password_reset_verify", limit=20, window=3600)
def password_reset_verify(request):
    phone = request.session.get(RESET_SESSION_KEY)

    if not phone:
        return redirect("accounts:password_reset")

    if request.method == "POST":
        form = PasswordResetVerifyForm(request.POST)

        if form.is_valid():
            try:
                verify_and_reset(phone, form.cleaned_data["code"], form.cleaned_data["new_password1"])
            except ResetError as error:
                form.add_error("code", str(error))
            else:
                request.session.pop(RESET_SESSION_KEY, None)
                messages.success(request, "رمز عبور شما تغییر کرد. با رمز جدید وارد شوید.")
                return redirect("accounts:login")
    else:
        form = PasswordResetVerifyForm()

    return render(
        request,
        "accounts/password_reset_verify.html",
        {"form": form, "phone": phone},
    )


# ---------- پنل کاربری ----------

@login_required
def dashboard(request):
    return render(
        request,
        "accounts/dashboard.html",
        {"panel_section": "dashboard", **get_dashboard_summary(request.user)},
    )


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)

        if form.is_valid():
            form.save()
            messages.success(request, "اطلاعات حساب شما به‌روز شد.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)

    return render(request, "accounts/profile.html", {"form": form, "panel_section": "profile"})


class UserPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """Django همچنان session کاربر را پس از تغییر رمز معتبر نگه می‌دارد."""

    template_name = "accounts/password_change.html"
    form_class = UserPasswordChangeForm
    success_url = reverse_lazy("accounts:profile")
    extra_context = {"panel_section": "password"}

    def form_valid(self, form):
        messages.success(self.request, "رمز عبور شما تغییر کرد.")
        return super().form_valid(form)


@login_required
def address(request):
    current = ShippingAddress.objects.filter(user=request.user).first()
    initial = current.as_initial() if current else {
        "recipient_name": request.user.get_full_name(),
        "recipient_phone": request.user.phone_number or "",
    }

    if request.method == "POST":
        form = ShippingAddressForm(request.POST)

        if form.is_valid():
            save_default_address(request.user, form.cleaned_data)
            messages.success(request, "نشانی پیش‌فرض ذخیره شد و در خریدهای بعدی به‌صورت خودکار پر می‌شود.")
            return redirect("accounts:address")
    else:
        form = ShippingAddressForm(initial=initial)

    return render(
        request,
        "accounts/address.html",
        {"form": form, "panel_section": "address", "iran_locations": get_locations()},
    )


@login_required
def packages(request):
    # «پکیج‌های من» با «رژیم‌های من» جایگزین شد؛ آدرس قدیمی همچنان کار می‌کند
    return redirect("diet:my_diets", permanent=True)


@login_required
def payments(request):
    return render(
        request,
        "accounts/payments.html",
        {
            "payments": Payment.objects.filter(user=request.user).select_related("appointment", "order"),
            "panel_section": "payments",
        },
    )
