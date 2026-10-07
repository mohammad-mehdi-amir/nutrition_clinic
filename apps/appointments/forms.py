from django import forms
from jalali_date.admin import JalaliDateField


class AppointmentDateForm(forms.Form):
    date = JalaliDateField(
        label="تاریخ",
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "id": "appointment-date",
                "placeholder": "1405-07-15",
                "autocomplete": "on",
            }
        ),
    )