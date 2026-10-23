from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import HealthProfileForm, MeasurementForm
from .models import DietTemplate, HealthProfile, PatientDiet
from .services import NOTICE_SESSION_KEY, add_measurement, save_health_profile
from .storage import pdf_download_name, serve_private_file


@staff_member_required
def staff_file(request, path):
    """دانلود فایل خصوصی از ادمین؛ فقط کارکنانی که اجازه‌ی دیدن رژیم‌ها را دارند."""
    if not (request.user.has_perm("diet.view_patientdiet") or request.user.has_perm("diet.view_diettemplate")):
        raise PermissionDenied

    # فقط فایلی که واقعاً به یک رکورد تعلق دارد (نه هر مسیر دلخواه)
    owner = (
        PatientDiet.objects.filter(file=path).first()
        if request.user.has_perm("diet.view_patientdiet") else None
    ) or (
        DietTemplate.objects.filter(file=path).first()
        if request.user.has_perm("diet.view_diettemplate") else None
    )
    if owner is None:
        raise Http404

    return serve_private_file(owner.file, pdf_download_name(owner.title))


def _safe_next(request, fallback):
    target = request.POST.get("next") or ""
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return reverse(fallback)


@login_required
def health_profile(request):
    profile = HealthProfile.objects.filter(user=request.user).first()
    latest = request.user.body_measurements.order_by("-recorded_at", "-id").first()

    if request.method == "POST":
        form = HealthProfileForm(request.POST, instance=profile, latest_measurement=latest)

        if form.is_valid():
            data = {name: form.cleaned_data[name] for name in HealthProfileForm.Meta.fields}
            save_health_profile(
                request.user, data,
                weight_kg=form.cleaned_data["weight_kg"],
                waist_cm=form.cleaned_data["waist_cm"],
            )
            messages.success(request, "پروفایل سلامت شما ذخیره شد.")
            return redirect("accounts:dashboard")
    else:
        form = HealthProfileForm(instance=profile, latest_measurement=latest)

    return render(
        request,
        "diet/health_profile.html",
        {
            "form": form,
            "panel_section": "health",
            "measurements": request.user.body_measurements.all()[:10],
        },
    )


@login_required
@require_POST
def add_measurement_view(request):
    form = MeasurementForm(request.POST)
    if form.is_valid():
        add_measurement(request.user, form.cleaned_data["weight_kg"], form.cleaned_data["waist_cm"])
        messages.success(request, "وزن امروز ثبت شد.")
    else:
        messages.error(request, " ".join(e for errors in form.errors.values() for e in errors))
    return redirect(_safe_next(request, "accounts:dashboard"))


@login_required
@require_POST
def dismiss_health_notice(request):
    request.session[NOTICE_SESSION_KEY] = True
    return redirect(_safe_next(request, "accounts:dashboard"))
