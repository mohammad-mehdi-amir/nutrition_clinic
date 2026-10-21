from django import forms

from utils.forms import StyledFormMixin
from utils.validators import iran_mobile_validator, normalize_digits
from .locations import city_choices, is_valid_city, province_choices


class AddressFieldsMixin(forms.Form):
    """
    فیلدهای گیرنده و نشانی با استان/شهر وابسته.
    مشترک بین فرم تسویه‌حساب و نشانی پیش‌فرض پروفایل.
    """

    recipient_name = forms.CharField(label="نام و نام خانوادگی گیرنده", max_length=100)
    recipient_phone = forms.CharField(
        label="موبایل گیرنده",
        max_length=11,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "dir": "ltr", "placeholder": "09xxxxxxxxx"}),
    )
    province = forms.ChoiceField(
        label="استان",
        required=False,
        widget=forms.Select(attrs={"data-province-select": ""}),
    )
    city = forms.ChoiceField(
        label="شهر",
        required=False,
        widget=forms.Select(attrs={"data-city-select": ""}),
    )
    address = forms.CharField(label="نشانی کامل", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    postal_code = forms.CharField(
        label="کد پستی",
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "dir": "ltr"}),
    )

    SHIPPING_FIELDS = ("province", "city", "address", "postal_code")

    def setup_address_fields(self, needs_shipping=True):
        self.needs_shipping = needs_shipping

        if not needs_shipping:
            for name in self.SHIPPING_FIELDS:
                del self.fields[name]
            return

        for name in self.SHIPPING_FIELDS:
            self.fields[name].required = True

        # شهرها وابسته به استان انتخاب‌شده (در JS هم با تغییر استان به‌روز می‌شوند)
        selected_province = self.data.get(self.add_prefix("province")) or self.initial.get("province", "")
        self.fields["province"].choices = [("", "انتخاب استان")] + province_choices()
        self.fields["city"].choices = [
            ("", "ابتدا استان را انتخاب کنید" if not selected_province else "انتخاب شهر")
        ] + city_choices(selected_province)

    def clean_recipient_phone(self):
        phone = normalize_digits(self.cleaned_data["recipient_phone"])
        iran_mobile_validator(phone)
        return phone

    def clean_postal_code(self):
        code = normalize_digits(self.cleaned_data.get("postal_code", ""))
        if self.needs_shipping and (len(code) != 10 or not code.isdigit()):
            raise forms.ValidationError("کد پستی باید ۱۰ رقم باشد.")
        return code

    def clean(self):
        cleaned_data = super().clean()

        if self.needs_shipping:
            province = cleaned_data.get("province")
            city = cleaned_data.get("city")

            if province and city and not is_valid_city(province, city):
                self.add_error("city", "شهر انتخاب‌شده متعلق به این استان نیست.")

        return cleaned_data


class CheckoutForm(StyledFormMixin, AddressFieldsMixin):
    note = forms.CharField(label="توضیحات (اختیاری)", max_length=500, required=False, widget=forms.Textarea(attrs={"rows": 2}))
    save_address = forms.BooleanField(
        label="ذخیره به‌عنوان نشانی پیش‌فرض من",
        required=False,
        initial=True,
    )

    def __init__(self, *args, needs_shipping=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_address_fields(needs_shipping)

        if not needs_shipping:
            del self.fields["save_address"]


class ShippingAddressForm(StyledFormMixin, AddressFieldsMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_address_fields(needs_shipping=True)
