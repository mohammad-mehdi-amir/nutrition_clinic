from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm, UserCreationForm

from utils.forms import StyledFormMixin
from utils.validators import iran_mobile_validator, normalize_digits
from .models import User


class RegisterForm(StyledFormMixin, UserCreationForm):
    """ثبت‌نام با شماره موبایل؛ شماره موبایل نام کاربری هم هست."""

    phone_number = forms.CharField(
        label="شماره موبایل",
        max_length=11,
        # اعتبارسنجی در clean_phone_number و پس از تبدیل ارقام فارسی انجام می‌شود
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "tel", "dir": "ltr", "placeholder": "09xxxxxxxxx"}),
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone_number")
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name", "placeholder": "نام"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name", "placeholder": "نام خانوادگی"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["password1"].widget.attrs["placeholder"] = "رمز عبور"
        self.fields["password2"].widget.attrs["placeholder"] = "تکرار رمز عبور"

    def clean_phone_number(self):
        phone = normalize_digits(self.cleaned_data["phone_number"])
        iran_mobile_validator(phone)

        if User.objects.filter(phone_number=phone).exists() or User.objects.filter(username=phone).exists():
            raise forms.ValidationError("با این شماره موبایل قبلاً ثبت‌نام شده است.")

        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["phone_number"]
        user.phone_number = self.cleaned_data["phone_number"]

        if commit:
            user.save()

        return user


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(
        label="شماره موبایل یا نام کاربری",
        max_length=150,
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username", "dir": "ltr", "placeholder": "09xxxxxxxxx"}),
    )

    def clean_username(self):
        return normalize_digits(self.cleaned_data["username"])


class PasswordResetRequestForm(StyledFormMixin, forms.Form):
    phone_number = forms.CharField(
        label="شماره موبایل",
        max_length=11,
        widget=forms.TextInput(attrs={"autofocus": True, "inputmode": "numeric", "autocomplete": "tel", "dir": "ltr", "placeholder": "09xxxxxxxxx"}),
    )

    def clean_phone_number(self):
        phone = normalize_digits(self.cleaned_data["phone_number"])
        iran_mobile_validator(phone)
        return phone


class PasswordResetVerifyForm(StyledFormMixin, SetPasswordForm):
    """کد پیامکی + رمز جدید (اعتبارسنجی رمز با AUTH_PASSWORD_VALIDATORS)."""

    code = forms.CharField(
        label="کد تأیید",
        max_length=6,
        widget=forms.TextInput(attrs={"autofocus": True, "inputmode": "numeric", "autocomplete": "one-time-code", "dir": "ltr", "placeholder": "------"}),
    )
    field_order = ["code", "new_password1", "new_password2"]

    def __init__(self, *args, **kwargs):
        # SetPasswordForm به user نیاز دارد؛ کاربر واقعی بعد از تأیید کد در سرویس مشخص می‌شود
        super().__init__(None, *args, **kwargs)

    def clean_code(self):
        code = normalize_digits(self.cleaned_data["code"]).strip()
        if len(code) != 6 or not code.isdigit():
            raise forms.ValidationError("کد تأیید ۶ رقمی است.")
        return code

    def save(self, commit=True):
        raise NotImplementedError("تغییر رمز از طریق accounts.services.verify_and_reset انجام می‌شود.")


class ProfileForm(StyledFormMixin, forms.ModelForm):
    """شماره موبایل (نام کاربری) عمداً در این فرم نیست تا قابل تغییر نباشد."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        widgets = {
            "email": forms.EmailInput(attrs={"dir": "ltr", "autocomplete": "email", "placeholder": "اختیاری"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True


class UserPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass
