from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, PasswordResetRequestForm, PasswordResetVerifyForm, RegisterForm
from .services import ResetError, request_reset_code, verify_and_reset


class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


def register(request):
    if request.user.is_authenticated:
        return redirect("core:home")

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

            return redirect("core:home")
    else:
        form = RegisterForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form, "next": next_url or ""},
    )


RESET_SESSION_KEY = "password_reset_phone"


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
