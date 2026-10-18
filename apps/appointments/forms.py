from django import forms
from jalali_date.fields import JalaliDateField

from utils.forms import StyledFormMixin
from utils.validators import normalize_digits
from .models import Doctor


class NormalizedJalaliDateField(JalaliDateField):
    """تاریخ جلالی با ارقام فارسی یا لاتین و جداکننده‌ی / یا -."""

    def to_python(self, value):
        if isinstance(value, str):
            value = normalize_digits(value.strip())
        return super().to_python(value)


class AppointmentDateForm(StyledFormMixin, forms.Form):
    doctor = forms.ModelChoiceField(
        label="پزشک",
        queryset=Doctor.objects.filter(is_active=True),
        empty_label="انتخاب پزشک",
        error_messages={
            "required": "لطفاً پزشک را انتخاب کنید.",
            "invalid_choice": "پزشک انتخاب‌شده معتبر نیست.",
        },
    )
    date = NormalizedJalaliDateField(
        label="تاریخ",
        input_formats=["%Y/%m/%d", "%Y-%m-%d"],
        help_text="روی کادر بزنید و تاریخ را از تقویم انتخاب کنید.",
        error_messages={
            "required": "لطفاً تاریخ را انتخاب کنید.",
            "invalid": "تاریخ واردشده معتبر نیست.",
        },
        widget=forms.TextInput(
            attrs={
                "data-jdp": "",
                "dir": "ltr",
                "placeholder": "1405/07/15",
                "autocomplete": "off",
                "inputmode": "none",
            }
        ),
    )
