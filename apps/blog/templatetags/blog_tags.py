import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

P_CLASS = "lg:text-lg text-base text-secondary font-normal leading-[2] sm:mb-7.5 mb-3.75"
H_CLASS = "text-xl font-bold mt-7.5 mb-3.75"
UL_CLASS = "mb-7.5"
LI_CLASS = (
    "w-full relative py-1 ps-6 lg:text-lg text-base text-secondary leading-[1.9] "
    "before:absolute ltr:before:left-0 rtl:before:right-0 before:top-3.5 before:size-2 before:rounded-full before:bg-primary"
)


@register.filter
def article_body(text):
    """
    متن ساده‌ی مقاله ⇒ HTML امن.
    همه‌ی ورودی escape می‌شود؛ فقط ساختار پاراگراف، تیتر («## ») و فهرست («- ») ساخته می‌شود.
    """
    if not text:
        return ""

    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip())
    html = []

    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        if len(lines) == 1 and lines[0].startswith("## "):
            html.append(f'<h2 class="{H_CLASS}">{escape(lines[0][3:].strip())}</h2>')
        elif all(line.startswith("- ") for line in lines):
            items = "".join(f'<li class="{LI_CLASS}">{escape(line[2:].strip())}</li>' for line in lines)
            html.append(f'<ul class="{UL_CLASS}">{items}</ul>')
        else:
            html.append(f'<p class="{P_CLASS}">{"<br>".join(escape(line) for line in lines)}</p>')

    return mark_safe("\n".join(html))
