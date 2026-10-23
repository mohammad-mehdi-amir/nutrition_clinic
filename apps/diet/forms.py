from decimal import Decimal

from django import forms

from apps.appointments.forms import NormalizedJalaliDateField
from utils.forms import StyledFormMixin
from utils.validators import normalize_digits

from .models import HealthProfile
from .services import trim_number


class NormalizedDecimalField(forms.DecimalField):
    """عدد اعشاری با ارقام فارسی و ممیز «٫» یا «/»."""

    def to_python(self, value):
        if isinstance(value, str):
            value = normalize_digits(value.strip()).replace("٫", ".").replace("/", ".")
        return super().to_python(value)


class SlashJalaliDateField(NormalizedJalaliDateField):
    """نمایش مقدار اولیه با «/» هم‌شکل خروجی datepicker."""

    def prepare_value(self, value):
        value = super().prepare_value(value)
        return value.replace("-", "/") if isinstance(value, str) else value


class NormalizedIntegerField(forms.IntegerField):
    def to_python(self, value):
        if isinstance(value, str):
            value = normalize_digits(value.strip())
        return super().to_python(value)


def weight_field(**extra):
    return NormalizedDecimalField(
        max_digits=4, decimal_places=1, min_value=Decimal("20"), max_value=Decimal("350"),
        widget=forms.TextInput(attrs={"inputmode": "decimal", "dir": "ltr", "placeholder": "72.5"}),
        **extra,
    )


def waist_field(**extra):
    return NormalizedDecimalField(
        max_digits=4, decimal_places=1, min_value=Decimal("30"), max_value=Decimal("250"),
        widget=forms.TextInput(attrs={"inputmode": "decimal", "dir": "ltr", "placeholder": "85"}),
        **extra,
    )


class HealthProfileForm(StyledFormMixin, forms.ModelForm):
    """همه‌ی فیلدها اختیاری‌اند؛ فقط رضایت پردازش اطلاعات سلامت برای ذخیره لازم است."""

    birth_date = SlashJalaliDateField(
        label="تاریخ تولد",
        required=False,
        input_formats=["%Y/%m/%d", "%Y-%m-%d"],
        error_messages={"invalid": "تاریخ واردشده معتبر نیست."},
        widget=forms.TextInput(attrs={
            "data-jdp": "", "dir": "ltr", "placeholder": "1370/05/12", "autocomplete": "off", "inputmode": "none",
        }),
    )
    height_cm = NormalizedIntegerField(
        label="قد (سانتی‌متر)", required=False, min_value=100, max_value=250,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "dir": "ltr", "placeholder": "170"}),
    )
    target_weight_kg = NormalizedDecimalField(
        label="وزن هدف (کیلوگرم)", required=False, max_digits=4, decimal_places=1,
        min_value=Decimal("30"), max_value=Decimal("300"),
        widget=forms.TextInput(attrs={"inputmode": "decimal", "dir": "ltr", "placeholder": "65"}),
    )
    weight_kg = weight_field(label="وزن فعلی (کیلوگرم)", required=False)
    waist_cm = waist_field(label="دور کمر (سانتی‌متر)", required=False, help_text="اختیاری؛ در بالای ناف اندازه بگیرید.")
    consent = forms.BooleanField(
        label="موافقم اطلاعات سلامت من فقط برای تهیه‌ی رژیم توسط کارشناسان کلینیک استفاده شود.",
        error_messages={"required": "برای ذخیره‌ی اطلاعات سلامت، تأیید این گزینه لازم است."},
    )

    class Meta:
        model = HealthProfile
        fields = [
            "sex", "birth_date", "height_cm", "activity_level", "goal", "target_weight_kg",
            "medical_conditions", "medications", "allergies", "food_preferences",
        ]
        widgets = {
            name: forms.Textarea(attrs={"rows": 3})
            for name in ("medical_conditions", "medications", "allergies", "food_preferences")
        }

    def __init__(self, *args, latest_measurement=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sex"].choices = [("", "انتخاب کنید")] + HealthProfile.SEX_CHOICES
        self.fields["activity_level"].choices = [("", "انتخاب کنید")] + HealthProfile.ACTIVITY_CHOICES
        self.fields["goal"].choices = [("", "انتخاب کنید")] + list(self.fields["goal"].choices)[1:]
        self.fields["medical_conditions"].widget.attrs["placeholder"] = "مثلاً دیابت نوع ۲، کم‌کاری تیروئید، فشار خون"
        self.fields["allergies"].widget.attrs["placeholder"] = "مثلاً لاکتوز، گلوتن، بادام‌زمینی"
        self.fields["food_preferences"].widget.attrs["placeholder"] = "غذاهایی که دوست دارید یا نمی‌خورید، گیاه‌خواری و..."

        if latest_measurement:
            self.fields["weight_kg"].initial = trim_number(latest_measurement.weight_kg)
            self.fields["waist_cm"].initial = trim_number(latest_measurement.waist_cm)
        if self.instance.target_weight_kg is not None:
            self.initial["target_weight_kg"] = trim_number(self.instance.target_weight_kg)
        if self.instance.pk and self.instance.consent_at:
            self.fields["consent"].initial = True


class MeasurementForm(StyledFormMixin, forms.Form):
    """ثبت سریع وزن از داشبورد."""

    weight_kg = weight_field(label="وزن امروز (کیلوگرم)", error_messages={"required": "وزن را وارد کنید."})
    waist_cm = waist_field(label="دور کمر (سانتی‌متر)", required=False)
