// اسکریپت‌های اختصاصی سایت (جدا از JS قالب ClinicMaster)
document.addEventListener("click", (event) => {
  const closeButton = event.target.closest(".remove-alert");
  if (closeButton) {
    closeButton.parentElement.remove();
  }
});

// مقایسه‌ی قبل/بعد: مقدار range محل خط جداکننده را تعیین می‌کند
document.querySelectorAll("[data-compare]").forEach((compare) => {
  const range = compare.querySelector(".compare-range");
  if (!range) return;
  const update = () => compare.style.setProperty("--pos", `${range.value}%`);
  range.addEventListener("input", update);
  update();
});
