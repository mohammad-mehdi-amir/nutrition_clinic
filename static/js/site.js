// اسکریپت‌های اختصاصی سایت (جدا از JS قالب ClinicMaster)
document.addEventListener("click", (event) => {
  const closeButton = event.target.closest(".remove-alert");
  if (closeButton) {
    closeButton.parentElement.remove();
  }
});
