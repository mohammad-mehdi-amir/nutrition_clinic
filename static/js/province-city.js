// لیست شهرهای وابسته به استان (فرم تسویه‌حساب).
// داده با {{ ...|json_script:"iran-locations" }} در صفحه قرار می‌گیرد؛ اعتبارسنجی نهایی سمت سرور است.
(() => {
  const dataElement = document.getElementById("iran-locations");
  const provinceSelect = document.querySelector("[data-province-select]");
  const citySelect = document.querySelector("[data-city-select]");

  if (!dataElement || !provinceSelect || !citySelect) return;

  const locations = JSON.parse(dataElement.textContent);

  const fillCities = () => {
    const cities = locations[provinceSelect.value] || [];
    const current = citySelect.value;

    citySelect.replaceChildren(
      new Option(cities.length ? "انتخاب شهر" : "ابتدا استان را انتخاب کنید", ""),
      ...cities.map((city) => new Option(city, city, false, city === current)),
    );
    citySelect.disabled = !cities.length;
  };

  provinceSelect.addEventListener("change", fillCities);
  fillCities();
})();
