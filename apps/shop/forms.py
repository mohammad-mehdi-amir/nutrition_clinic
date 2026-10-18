from django import forms

from utils.forms import StyledFormMixin
from utils.validators import iran_mobile_validator, normalize_digits


class CheckoutForm(StyledFormMixin, forms.Form):
    recipient_name = forms.CharField(label="نام و نام خانوادگی گیرنده", max_length=100)
    recipient_phone = forms.CharField(
        label="موبایل گیرنده",
        max_length=11,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "dir": "ltr", "placeholder": "09xxxxxxxxx"}),
    )
    province = forms.CharField(label="استان", max_length=50, required=False)
    city = forms.CharField(label="شهر", max_length=50, required=False)
    address = forms.CharField(label="نشانی کامل", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    postal_code = forms.CharField(
        label="کد پستی",
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "dir": "ltr"}),
    )
    note = forms.CharField(label="توضیحات (اختیاری)", max_length=500, required=False, widget=forms.Textarea(attrs={"rows": 2}))

    SHIPPING_FIELDS = ("province", "city", "address", "postal_code")

    def __init__(self, *args, needs_shipping=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.needs_shipping = needs_shipping

        if needs_shipping:
            for name in self.SHIPPING_FIELDS:
                self.fields[name].required = True
        else:
            for name in self.SHIPPING_FIELDS:
                del self.fields[name]

    def clean_recipient_phone(self):
        phone = normalize_digits(self.cleaned_data["recipient_phone"])
        iran_mobile_validator(phone)
        return phone

    def clean_postal_code(self):
        code = normalize_digits(self.cleaned_data.get("postal_code", ""))
        if self.needs_shipping and (len(code) != 10 or not code.isdigit()):
            raise forms.ValidationError("کد پستی باید ۱۰ رقم باشد.")
        return code
