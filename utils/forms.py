from django import forms

INPUT_CLASS = "py-2.5 px-5 bg-light w-full outline-none text-black rounded-2lg h-15"
TEXTAREA_CLASS = "py-3.75 px-5 bg-light w-full outline-none text-black rounded-2lg min-h-50"
SELECT_CLASS = "py-2.5 px-5 bg-light w-full outline-none text-black rounded-2lg h-15 cursor-pointer"


class StyledFormMixin:
    """کلاس‌های فیلد فرم قالب ClinicMaster را به ویجت‌های Django اضافه می‌کند."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            widget = field.widget

            if isinstance(widget, forms.Textarea):
                css = TEXTAREA_CLASS
            elif isinstance(widget, forms.Select):
                css = SELECT_CLASS
            elif isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
                continue
            else:
                css = INPUT_CLASS

            widget.attrs["class"] = f"{css} {widget.attrs.get('class', '')}".strip()
