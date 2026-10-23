from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.http import Http404

from .models import DietTemplate, PatientDiet
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
