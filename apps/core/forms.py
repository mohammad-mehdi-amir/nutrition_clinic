from django import forms

from utils.forms import StyledFormMixin
from utils.validators import normalize_digits
from .models import ContactMessage


class ContactForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "phone", "email", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "نام و نام خانوادگی", "autocomplete": "name"}),
            "phone": forms.TextInput(attrs={"placeholder": "شماره موبایل", "inputmode": "numeric", "autocomplete": "tel", "dir": "ltr"}),
            "email": forms.EmailInput(attrs={"placeholder": "ایمیل (اختیاری)", "autocomplete": "email", "dir": "ltr"}),
            "message": forms.Textarea(attrs={"placeholder": "پیام شما", "rows": 5}),
        }

    def clean_phone(self):
        return normalize_digits(self.cleaned_data["phone"])
