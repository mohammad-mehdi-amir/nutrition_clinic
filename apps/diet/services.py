import logging

from django.core.files import File
from django.db import transaction
from django.utils import timezone

from apps.core import notifications

from .models import BodyMeasurement, DietRequest, HealthProfile, PatientDiet

logger = logging.getLogger(__name__)


def create_requests_for_order(order):
    """
    برای هر پکیج سفارش پرداخت‌شده یک درخواست رژیم می‌سازد.
    idempotent است (callback تکراری یا ذخیره‌ی دوباره‌ی ادمین درخواست تکراری نمی‌سازد).
    """
    from apps.shop.models import Product

    created = []
    for item in order.items.filter(product_type=Product.TYPE_PACKAGE):
        diet_request, is_new = DietRequest.objects.get_or_create(
            order_item=item,
            defaults={"user_id": order.user_id, "package_name": item.product_name},
        )
        if is_new:
            created.append(diet_request)
    return created


# ---------- پروفایل سلامت و آمار ----------

NOTICE_SESSION_KEY = "health_notice_dismissed"  # بستن اعلان تکمیل پروفایل


def trim_number(value):
    """۷۸.۰ ⇒ ۷۸ و ۷۴.۱ ⇒ ۷۴.۱ (Decimal یا float)."""
    if value is None or value == "":
        return value
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:.1f}"


BMI_CATEGORIES = [
    # (حد بالا، برچسب، کلاس رنگ قالب)
    (18.5, "کمبود وزن", "info"),
    (25, "وزن طبیعی", "success"),
    (30, "اضافه‌وزن", "warning"),
    (None, "چاقی", "danger"),
]
BMI_SCALE = (15, 40)  # بازه‌ی نوار نمایش BMI


def calculate_bmi(weight_kg, height_cm):
    meters = height_cm / 100
    return round(weight_kg / (meters * meters), 1)


def bmi_category(bmi):
    for limit, label, color in BMI_CATEGORIES:
        if limit is None or bmi < limit:
            return label, color


def healthy_weight_range(height_cm):
    """بازه‌ی وزن متناظر با BMI ۱۸.۵ تا ۲۴.۹."""
    meters = height_cm / 100
    return round(18.5 * meters * meters, 1), round(24.9 * meters * meters, 1)


def calculate_bmr(weight_kg, height_cm, age, sex):
    """متابولیسم پایه با فرمول Mifflin-St Jeor (کیلوکالری در روز)."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return round(base + (5 if sex == HealthProfile.SEX_MALE else -161))


def calculate_tdee(bmr, activity_level):
    """کالری روزانه با ضریب فعالیت، گرد شده به ده."""
    return int(round(bmr * HealthProfile.ACTIVITY_FACTORS[activity_level], -1))


def daily_water_liters(weight_kg):
    """حدود ۳۳ میلی‌لیتر به ازای هر کیلوگرم."""
    return round(weight_kg * 0.033, 1)


def waist_to_height(waist_cm, height_cm):
    ratio = round(waist_cm / height_cm, 2)
    if ratio < 0.5:
        return ratio, "مطلوب", "success"
    if ratio < 0.6:
        return ratio, "افزایش خطر", "warning"
    return ratio, "خطر بالا", "danger"


def weight_chart(measurements, width=300, height=100, padding=8):
    """نقاط نمودار SVG روند وزن (قدیمی به جدید)؛ کمتر از دو اندازه‌گیری ⇒ None."""
    if len(measurements) < 2:
        return None

    weights = [float(m.weight_kg) for m in measurements]
    low, high = min(weights), max(weights)
    spread = (high - low) or 1
    step = (width - 2 * padding) / (len(weights) - 1)

    points = [
        (round(padding + i * step, 1), round(height - padding - (w - low) / spread * (height - 2 * padding), 1))
        for i, w in enumerate(weights)
    ]
    return {
        "points": " ".join(f"{x},{y}" for x, y in points),
        "dots": [{"x": x, "y": y, "measurement": m} for (x, y), m in zip(points, measurements)],
        "min": low,
        "max": high,
        "width": width,
        "height": height,
    }


PROFILE_REQUIRED_FOR_STATS = ("sex", "birth_date", "height_cm", "activity_level", "goal")


def get_health_stats(user):
    """
    آمار داشبورد از روی پروفایل و آخرین اندازه‌گیری. هر آماری که داده‌اش ناقص است None می‌ماند
    و فهرست missing نشان می‌دهد چه چیزی برای تکمیل لازم است.
    """
    profile = HealthProfile.objects.filter(user=user).first()
    history = list(user.body_measurements.order_by("-recorded_at", "-id")[:12])[::-1]
    latest = history[-1] if history else None
    latest_waist = user.body_measurements.filter(waist_cm__isnull=False).order_by("-recorded_at", "-id").first()

    weight = float(latest.weight_kg) if latest else None
    height = profile.height_cm if profile else None
    age = profile.age if profile else None
    sex = profile.sex if profile else ""
    activity = profile.activity_level if profile else ""

    stats = {
        "profile": profile,
        "weight": weight,
        "height": height,
        "latest": latest,
        "bmi": None,
        "healthy_range": None,
        "target_diff": None,
        "bmr": None,
        "tdee": None,
        "water": daily_water_liters(weight) if weight else None,
        "whtr": None,
        "weight_change": None,
        "chart": weight_chart(history),
    }

    if weight and height:
        bmi = calculate_bmi(weight, height)
        label, color = bmi_category(bmi)
        low, high = BMI_SCALE
        stats["bmi"] = {
            "value": bmi,
            "label": label,
            "color": color,
            "position": round(min(max((bmi - low) / (high - low), 0), 1) * 100),
        }
        stats["healthy_range"] = healthy_weight_range(height)

    if weight and profile and profile.target_weight_kg:
        stats["target_diff"] = round(weight - float(profile.target_weight_kg), 1)

    if weight and height and age and sex:
        stats["bmr"] = calculate_bmr(weight, height, age, sex)
        if activity:
            stats["tdee"] = calculate_tdee(stats["bmr"], activity)

    if latest_waist and height:
        ratio, label, color = waist_to_height(float(latest_waist.waist_cm), height)
        stats["whtr"] = {"value": ratio, "label": label, "color": color}

    first = user.body_measurements.order_by("recorded_at", "id").first()
    if latest and first and first.pk != latest.pk:
        stats["weight_change"] = round(weight - float(first.weight_kg), 1)

    missing = [
        HealthProfile._meta.get_field(name).verbose_name
        for name in PROFILE_REQUIRED_FOR_STATS
        if not profile or not getattr(profile, name)
    ]
    if not latest:
        missing.insert(0, "وزن")
    stats["missing"] = missing
    stats["is_complete"] = not missing
    return stats


def is_profile_complete(user):
    profile = HealthProfile.objects.filter(user=user).first()
    return bool(
        profile
        and all(getattr(profile, name) for name in PROFILE_REQUIRED_FOR_STATS)
        and user.body_measurements.exists()
    )


@transaction.atomic
def save_health_profile(user, profile_data, weight_kg=None, waist_cm=None):
    """
    ذخیره‌ی پروفایل سلامت؛ اگر وزن یا دور کمر با آخرین اندازه‌گیری فرق کند، ردیف جدیدی در سابقه ثبت می‌شود.
    """
    profile, _ = HealthProfile.objects.select_for_update().get_or_create(user=user)
    for name, value in profile_data.items():
        setattr(profile, name, value)
    if not profile.consent_at:
        profile.consent_at = timezone.now()
    profile.save()

    latest = user.body_measurements.order_by("-recorded_at", "-id").first()
    if weight_kg is not None and (
        latest is None or latest.weight_kg != weight_kg or (waist_cm is not None and latest.waist_cm != waist_cm)
    ):
        BodyMeasurement.objects.create(user=user, weight_kg=weight_kg, waist_cm=waist_cm)

    return profile


def add_measurement(user, weight_kg, waist_cm=None):
    return BodyMeasurement.objects.create(user=user, weight_kg=weight_kg, waist_cm=waist_cm)


# ---------- تحویل رژیم ----------

class DeliveryError(Exception):
    pass


def deliver_diet(diet_request, *, title="", uploaded_file=None, template=None, note="", by=None):
    """
    تحویل PDF رژیم به بیمار: یا فایل آپلودی یا یک رژیم آماده (که فایلش کپی می‌شود تا تغییر/حذف
    رژیم آماده روی نسخه‌ی بیمار اثر نگذارد). پیامک بعد از commit ارسال می‌شود.
    """
    if bool(uploaded_file) == bool(template):
        raise DeliveryError("یا یک فایل PDF آپلود کنید یا یکی از رژیم‌های آماده را انتخاب کنید (فقط یکی).")

    title = (title or (template.title if template else "")).strip()
    if not title:
        raise DeliveryError("عنوان رژیم را وارد کنید.")

    with transaction.atomic():
        diet_request = DietRequest.objects.select_for_update().get(pk=diet_request.pk)
        diet = PatientDiet(request=diet_request, title=title, template=template, note=note, delivered_by=by)

        if template:
            with template.file.open("rb") as source:
                diet.file.save("diet.pdf", File(source), save=False)
        else:
            diet.file = uploaded_file
        diet.save()

        if diet_request.status != DietRequest.STATUS_DELIVERED:
            diet_request.status = DietRequest.STATUS_DELIVERED
            diet_request.delivered_at = diet.delivered_at
            diet_request.save(update_fields=["status", "delivered_at"])

        notifications.diet_ready(diet_request.user)

    return diet
