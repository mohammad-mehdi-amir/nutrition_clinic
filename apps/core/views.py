from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static

from apps.appointments.models import Doctor
from apps.blog.models import Post

from utils.ratelimit import ratelimit
from .forms import ContactForm
from .models import FAQ, Service, SiteSettings, TransformationCase


def home(request):
    return render(
        request,
        "core/home.html",
        {
            "services": Service.objects.filter(is_active=True)[:4],
            "doctors": Doctor.objects.filter(is_active=True)[:4],
            "posts": Post.objects.published().select_related("category")[:3],
            "transformations": TransformationCase.objects.public()[:3],
        },
    )


def about(request):
    return render(
        request,
        "core/about.html",
        {"faqs": FAQ.objects.filter(is_active=True)[:4]},
    )


def services(request):
    return render(
        request,
        "core/services.html",
        {"services": Service.objects.filter(is_active=True)},
    )


def service_detail(request, slug):
    service = get_object_or_404(Service, slug=slug, is_active=True)
    return render(
        request,
        "core/service_detail.html",
        {
            "service": service,
            "other_services": Service.objects.filter(is_active=True).exclude(pk=service.pk)[:5],
            "faqs": FAQ.objects.filter(is_active=True)[:4],
        },
    )


def faqs(request):
    return render(
        request,
        "core/faqs.html",
        {"faqs": FAQ.objects.filter(is_active=True)},
    )


@ratelimit("contact", limit=5, window=3600)
def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                "پیام شما ثبت شد. همکاران ما به‌زودی با شما تماس می‌گیرند.",
            )
            return redirect("core:contact")
    else:
        form = ContactForm()

    return render(request, "core/contact.html", {"form": form})


def terms(request):
    return render(request, "core/legal.html", {"page": "terms"})


def privacy(request):
    return render(request, "core/legal.html", {"page": "privacy"})


def favicon(request):
    """/favicon.ico (درخواست پیش‌فرض مرورگرها، مثلاً در صفحات ادمین)."""
    site_settings = SiteSettings.load()
    url = site_settings.favicon.url if site_settings.favicon else static("clinicmaster/src/images/favicon.png")
    return redirect(url)
