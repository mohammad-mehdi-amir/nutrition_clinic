const ClinicMaster = (function () {
  "use strict";

  const handlePricingTabs = () => {
    const toggleTabs = document.querySelector(".toggle-tabs");

    if (!toggleTabs) return;

    const priceYear = document.querySelectorAll(".pricingtable-price.year");
    const priceMonth = document.querySelectorAll(".pricingtable-price.month");

    priceYear.forEach((el) => (el.style.display = "none"));

    const toggleTabsMonthly = toggleTabs.querySelector(".monthly");
    const toggleTabsYearly = toggleTabs.querySelector(".yearly");

    if (toggleTabsMonthly) {
      toggleTabsMonthly.addEventListener("click", () => {
        toggleTabs.classList.add("monthly");
        toggleTabs.classList.remove("yearly");

        priceMonth.forEach((el) => (el.style.display = "block"));
        priceYear.forEach((el) => (el.style.display = "none"));
      });
    }

    if (toggleTabsYearly) {
      toggleTabsYearly.addEventListener("click", () => {
        toggleTabs.classList.add("yearly");
        toggleTabs.classList.remove("monthly");

        priceMonth.forEach((el) => (el.style.display = "none"));
        priceYear.forEach((el) => (el.style.display = "block"));
      });
    }
  };
  const handleTouchSpin = () => {
    function incrementValue(e) {
      e.preventDefault();
      const button = e.target.closest("[data-field]");
      const fieldName = button.getAttribute("data-field");

      const parent = button.closest("div") || button.closest("td");
      const input = parent.querySelector(`input[name="${fieldName}"]`);

      let currentVal = parseInt(input.value, 10);
      input.value = !isNaN(currentVal) ? currentVal + 1 : 0;
    }

    function decrementValue(e) {
      e.preventDefault();
      const button = e.target.closest("[data-field]");
      const fieldName = button.getAttribute("data-field");

      const parent = button.closest("div") || button.closest("td");
      const input = parent.querySelector(`input[name="${fieldName}"]`);

      let currentVal = parseInt(input.value, 10);
      input.value = !isNaN(currentVal) && currentVal > 0 ? currentVal - 1 : 0;
    }

    document.querySelectorAll(".input-group").forEach((group) => {
      group.addEventListener("click", function (e) {
        const target = e.target.closest(".button-plus, .button-minus");
        if (!target) return;

        if (target.classList.contains("button-plus")) {
          incrementValue(e);
        } else if (target.classList.contains("button-minus")) {
          decrementValue(e);
        }
      });
    });
  };

  const handleSetCurrentYear = () => {
    const currentDate = new Date();
    let currentYear = currentDate.getFullYear();
    let elements = document.getElementsByClassName("current-year");

    for (const element of elements) {
      element.innerHTML = currentYear;
    }
  };

  const handledzNumber = () => {
    const dzNumber = document.querySelectorAll(".dz-number");

    if (dzNumber) {
      dzNumber.forEach(function (element) {
        element.addEventListener("input", function () {
          const inputVal = element.value;
          const numericVal = inputVal.replace(/\D/g, "");

          if (numericVal.length > 10) {
            element.value = numericVal.slice(0, 10);
          } else {
            element.value = numericVal;
          }
        });
      });
    }
  };

  const handleAppointmentWizard = () => {
    const initWizard = (selector, orientation = "vertical") => {
      const container = document.querySelector(selector);
      if (!container) return;

      const args = {
        wz_class: selector,
        wz_nav_style: "dots",
        wz_button_style: ".btn .btn-sm .mx-3",
        wz_ori: orientation,
        buttons: true,
        navigation: "all",
        finish: "Submit",
        bubble: true,
      };

      const wizard = new Wizard(args);
      wizard.init();

      const monthEl = container.querySelector(".month");
      const yearEl = container.querySelector(".year");
      const calendarDays = container.querySelector(".calendar-days");
      const selectedDateEl = container.querySelector(".selected-date");
      const slotsContainer = container.querySelector(".slots-container");

      let currentDate = new Date();
      let selectedDay = null;

      const months = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
      ];

      const timeSlots = [
        "9:00 AM - 10:30 AM",
        "10:30 AM - 12:00 PM",
        "11:00 AM - 12:30 PM",
        "11:30 AM - 1:00 PM",
        "12:00 PM - 1:30 PM",
        "12:30 PM - 2:00 PM",
        "1:00 PM - 2:30 PM",
        "1:30 PM - 3:00 PM",
        "2:00 PM - 3:30 PM",
        "2:30 PM - 4:00 PM",
        "3:00 PM - 4:30 PM",
        "3:30 PM - 5:00 PM",
      ];

      function populateDropdowns() {
        monthEl.innerHTML = "";
        months.forEach((m, i) => {
          const opt = document.createElement("option");
          opt.value = i;
          opt.textContent = m;
          if (i === currentDate.getMonth()) opt.selected = true;
          monthEl.appendChild(opt);
        });

        yearEl.innerHTML = "";
        for (
          let y = currentDate.getFullYear();
          y <= currentDate.getFullYear() + 2;
          y++
        ) {
          const opt = document.createElement("option");
          opt.value = y;
          opt.textContent = y;
          if (y === currentDate.getFullYear()) opt.selected = true;
          yearEl.appendChild(opt);
        }
      }

      function generateCalendar() {
        calendarDays.innerHTML = "";
        const month = parseInt(monthEl.value);
        const year = parseInt(yearEl.value);
        const firstDay = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const start = firstDay === 0 ? 6 : firstDay - 1;

        for (let i = 0; i < start; i++) {
          const blank = document.createElement("div");
          calendarDays.appendChild(blank);
        }

        for (let day = 1; day <= daysInMonth; day++) {
          const d = new Date(year, month, day);
          const dayEl = document.createElement("div");
          dayEl.className = "day";
          dayEl.textContent = day;

          if (d.toDateString() === selectedDay?.toDateString()) {
            dayEl.classList.add("selected");
          }

          dayEl.onclick = () => {
            selectedDay = d;
            container
              .querySelectorAll(".day")
              .forEach((el) => el.classList.remove("selected"));
            dayEl.classList.add("selected");
            selectedDateEl.textContent = d.toDateString();
            renderTimeSlots();
          };

          calendarDays.appendChild(dayEl);
        }
      }

      function renderTimeSlots() {
        slotsContainer.innerHTML = "";
        timeSlots.forEach((slot) => {
          const div = document.createElement("div");
          div.className = "slot";
          div.textContent = slot;
          div.onclick = () => {
            container
              .querySelectorAll(".slot")
              .forEach((s) => s.classList.remove("selected"));
            div.classList.add("selected");
          };
          slotsContainer.appendChild(div);
        });
      }

      container.querySelector(".prev-month").onclick = (e) => {
        e.preventDefault();
        if (monthEl.selectedIndex > 0) {
          monthEl.selectedIndex--;
        } else if (yearEl.selectedIndex > 0) {
          yearEl.selectedIndex--;
          monthEl.selectedIndex = 11;
        }
        generateCalendar();
      };

      container.querySelector(".next-month").onclick = (e) => {
        e.preventDefault();
        if (monthEl.selectedIndex < 11) {
          monthEl.selectedIndex++;
        } else {
          monthEl.selectedIndex = 0;
          yearEl.selectedIndex++;
        }
        generateCalendar();
      };

      monthEl.onchange = generateCalendar;
      yearEl.onchange = generateCalendar;

      populateDropdowns();
      generateCalendar();
    };

    initWizard(".wizard-vertical", "vertical");

    initWizard(".wizard-horizontal", "horizontal");
  };

  const handleLightGallery = () => {
    
    const lightgallery = document.getElementById('lightgallery');
    if (!lightgallery) return;

    lightGallery(lightgallery, {
      selector: ".lg-item",
      plugins: [lgThumbnail, lgZoom],
      thumbnail: true,
      animateThumb: false,
      zoomFromOrigin: false,
      allowMediaOverlap: true,
      toggleThumb: true,
    });
  };

  const handleBoxHover = () => {
    const wrappers = document.querySelectorAll(".box-hover-wrapper");
    if (!wrappers.length) return;

    wrappers.forEach((wrapper) => {
      wrapper.addEventListener("mouseover", (e) => {
        const card = e.target.closest(".box-hover");
        if (!card || !wrapper.contains(card)) return;

        wrapper
          .querySelectorAll(".box-hover.active")
          .forEach((c) => c.classList.remove("active"));

        card.classList.add("active");
      });
    });
  };

  const handleCounter = () => {
    const counters = document.querySelectorAll(".value");
    if (!counters.length) return;

    const DURATION = 1200;

    const runCounter = (counter) => {
      const target = Number(counter.dataset.value);
      if (isNaN(target)) return;

      const startTime = performance.now();

      const update = (currentTime) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / DURATION, 1);

        counter.innerText = Math.floor(progress * target);

        if (progress < 1) {
          requestAnimationFrame(update);
        } else {
          counter.innerText = target;
        }
      };

      requestAnimationFrame(update);
    };

    const observer = new IntersectionObserver(
      (entries, obs) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            runCounter(entry.target);
            obs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.4 }
    );

    counters.forEach((counter) => observer.observe(counter));
  };

  const handleNavScroller = (() => {
    let previousScroll = 0;
    let isAttached = false;

    const onScroll = () => {
      if (window.innerWidth > 768) return;

      const extraNav = document.querySelector(".extra-nav");
      if (!extraNav) return;

      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      const innerHeight = window.innerHeight;
      const scrollHeight = document.documentElement.scrollHeight;

      extraNav.classList.toggle(
        "bottom-end",
        scrollTop + innerHeight >= scrollHeight
      );

      extraNav.classList.toggle("active", scrollTop > previousScroll);

      previousScroll = scrollTop;
    };

    const debounce = (fn, delay = 80) => {
      let timer;
      return () => {
        clearTimeout(timer);
        timer = setTimeout(fn, delay);
      };
    };

    return () => {
      if (isAttached) return;

      window.addEventListener("scroll", debounce(onScroll), { passive: true });

      isAttached = true;
    };
  })();

  const handleCustomSelects = () => {
    document.querySelectorAll(".dynamic-select").forEach((selectElement) => {
      createCustomSelectFromSelect(selectElement);
    });
  };

  const createCustomSelectFromSelect = (selectElement) => {
    const selectId =
      selectElement.id || `select-${Math.random().toString(36).substr(2, 9)}`;
    const customSelectDiv = document.createElement("div");
    customSelectDiv.id = `custom-${selectId}`;
    customSelectDiv.className = "custom-select";

    const selectedDiv = document.createElement("div");
    selectedDiv.className = "select-selected";
    selectedDiv.textContent = (
      selectElement.querySelector("option[selected]") ||
      selectElement.options[0]
    ).textContent;

    const labelText = selectElement.parentElement?.dataset?.label || "";
    if (labelText) {
      const label = document.createElement("span");
      label.textContent = labelText;
      selectedDiv.appendChild(label);
    }

    customSelectDiv.appendChild(selectedDiv);

    const itemsDiv = document.createElement("div");
    itemsDiv.className = "select-items select-hide";
    customSelectDiv.appendChild(itemsDiv);

    Array.from(selectElement.options).forEach((option) => {
      const customOptionDiv = document.createElement("div");
      customOptionDiv.className = "select-item";
      customOptionDiv.setAttribute("data-value", option.value);
      customOptionDiv.textContent = option.textContent;
      if (option.selected) customOptionDiv.classList.add("active");

      customOptionDiv.addEventListener("click", function () {
        selectedDiv.childNodes[0].textContent = this.textContent;
        selectElement.value = this.getAttribute("data-value");
        selectElement.dispatchEvent(new Event("change"));
        selectElement.dispatchEvent(new Event("click"));

        itemsDiv.classList.add("select-hide");
        selectedDiv.classList.remove("select-active");

        itemsDiv
          .querySelectorAll(".select-item")
          .forEach((item) => item.classList.remove("active"));
        this.classList.add("active");
      });

      itemsDiv.appendChild(customOptionDiv);
    });

    selectElement.style.display = "none";
    selectElement.parentNode.insertBefore(
      customSelectDiv,
      selectElement.nextSibling
    );

    selectedDiv.addEventListener("click", function (e) {
      e.stopPropagation();
      itemsDiv.classList.toggle("select-hide");
      selectedDiv.classList.toggle("select-active");
    });

    document.addEventListener("click", function (e) {
      if (!customSelectDiv.contains(e.target)) {
        itemsDiv.classList.add("select-hide");
        selectedDiv.classList.remove("select-active");
      }
    });
  };

  const handleAccordion = (container = document) => {
    const accordionContainers = container.querySelectorAll(".myAccordion");

    accordionContainers.forEach((accordion) => {
      if (accordion.dataset.bound === "true") return;
      accordion.dataset.bound = "true";

      accordion.addEventListener("click", function (e) {
        const header = e.target.closest(".accordion-header");
        if (!header || !accordion.contains(header)) return;

        const item = header.parentElement;
        const content = item.querySelector(".accordion-content");
        const arrow = header.querySelector(".arrow");
        const isOpen = header.classList.contains("open");

        accordion.querySelectorAll(".accordion-header").forEach((h) => {
          if (h !== header) {
            h.classList.remove("open");
            h.querySelector(".arrow")?.classList.remove("active");
            const c = h.parentElement.querySelector(".accordion-content");
            if (c) c.style.maxHeight = null;
          }
        });

        if (!isOpen) {
          header.classList.add("open");
          content.style.maxHeight = content.scrollHeight + "px";
          arrow?.classList.add("active");
        } else {
          header.classList.remove("open");
          content.style.maxHeight = null;
          arrow?.classList.remove("active");
        }
      });
    });

    container.querySelectorAll(".accordion-header.open").forEach((header) => {
      const content = header.parentElement.querySelector(".accordion-content");
      const arrow = header.querySelector(".arrow");
      if (content) {
        content.style.maxHeight = content.scrollHeight + "px";
        arrow?.classList.add("active");
      }
    });
  };

  const handleVideoPopup = function () {
    const dialog = document.getElementById("videoDialog");
    const container = document.getElementById("videoContainer");
    const closeBtn = document.getElementById("closeBtn");
    const videoWrapper = document.body;

    if (!dialog || !container || !closeBtn) return;

    const onOpenVideo = (e) => {
      const button = e.target.closest("button[data-type]");
      if (!button) return;

      const type = button.getAttribute("data-type");
      const src = button.getAttribute("data-src");

      if (!type || !src) return;

      openVideo(type, src);
    };

    const openVideo = (type, src) => {
      let videoHTML = "";

      if (type === "youtube" || type === "vimeo") {
        const sanitizedSrc = encodeURI(src);
        videoHTML = `<iframe src="${sanitizedSrc}?autoplay=1" allow="autoplay; encrypted-media; fullscreen" allowfullscreen></iframe>`;
      } else if (type === "mp4") {
        videoHTML = `<video controls autoplay><source src="${src}" type="video/mp4">Your browser does not support the video tag.</video>`;
      }

      container.innerHTML = videoHTML;
      dialog.style.display = "flex";
    };

    const closeVideo = () => {
      container.innerHTML = "";
      dialog.style.display = "none";
    };

    videoWrapper.addEventListener("click", onOpenVideo);
    closeBtn.addEventListener("click", closeVideo);

    return () => {
      videoWrapper.removeEventListener("click", onOpenVideo);
      closeBtn.removeEventListener("click", closeVideo);
    };
  };

  const handleTabs = () => {
    const tabContainers = document.querySelectorAll(".custom-tab");

    tabContainers.forEach((container) => {
      const titles = container.querySelectorAll(".tab-title");
      const contents = container.querySelectorAll(".tab-content");

      const activeIndex = container.dataset.activeIndex
        ? container.dataset.activeIndex
        : 0;

      titles[activeIndex]?.classList.add("active");
      contents[activeIndex]?.classList.add("active");
      handleAccordion(contents[activeIndex]);

      container.addEventListener("click", (e) => {
        const clicked = e.target.closest(".tab-title");
        if (!clicked || !container.contains(clicked)) return;

        titles.forEach((t, i) => {
          const isActive = t === clicked;
          t.classList.toggle("active", isActive);
          contents[i].classList.toggle("active", isActive);

          if (isActive) {
            handleAccordion(contents[i]);
          }
        });
      });
    });
  };

  const handleStarRating = () => {
    const starRatingElements = document.querySelectorAll(".star-rating-old");
    if (starRatingElements.length > 0) {
      new StarRating(".star-rating-old");
    }
  };

  const handleMasonryBox = () => {
    const masonryEl = document.querySelector("#masonry, .masonry");
    const filters = document.querySelector(".filters");

    if (!masonryEl) return;

    const gutter = parseInt(masonryEl.dataset.gutter || 0, 10);
    const columnWidth = masonryEl.dataset.columnWidth
      ? parseInt(masonryEl.dataset.columnWidth, 10)
      : ".card-container";

    imagesLoaded(masonryEl, () => {
      const iso = new Isotope(masonryEl, {
        itemSelector: ".card-container",
        layoutMode: "masonry",
        masonry: {
          gutter: gutter,
          columnWidth: columnWidth,
        },
        transitionDuration: "0.4s",
      });

      if (filters) {
        const first = filters.querySelector("li:first-child");
        if (first) first.classList.add("active");

        filters.addEventListener("click", (e) => {
          const li = e.target.closest("li");
          if (!li) return;

          filters
            .querySelectorAll("li")
            .forEach((el) => el.classList.remove("active"));
          li.classList.add("active");

          let filterValue = li.dataset.filter || "*";
          if (filterValue === "all") filterValue = "*";

          iso.arrange({ filter: filterValue });
        });
      }
    });
  };

  const handleCountdown = () => {
    const counter = document.querySelector("#countdown");
    if (!counter) return;

    const countDownClock = (number = 100, format = "seconds") => {
      const d = document;
      const daysElement = d.querySelector("#countdown .days");
      const hoursElement = d.querySelector("#countdown .hours");
      const minutesElement = d.querySelector("#countdown .minutes");
      const secondsElement = d.querySelector("#countdown .seconds");
      let countdown;
      convertFormat(format);

      function convertFormat(format) {
        switch (format) {
          case "seconds":
            return timer(number);
          case "minutes":
            return timer(number * 60);
          case "hours":
            return timer(number * 60 * 60);
          case "days":
            return timer(number * 60 * 60 * 24);
        }
      }

      function timer(seconds) {
        const now = Date.now();
        const then = now + seconds * 1000;

        countdown = setInterval(() => {
          const secondsLeft = Math.round((then - Date.now()) / 1000);

          if (secondsLeft <= 0) {
            clearInterval(countdown);
            return;
          }

          displayTimeLeft(secondsLeft);
        }, 1000);
      }

      function displayTimeLeft(seconds) {
        daysElement.textContent = Math.floor(seconds / 86400);
        hoursElement.textContent = Math.floor((seconds % 86400) / 3600);
        minutesElement.textContent = Math.floor(
          ((seconds % 86400) % 3600) / 60
        );
        secondsElement.textContent =
          seconds % 60 < 10 ? `0${seconds % 60}` : seconds % 60;
      }
    };
    countDownClock(20, "days");
  };

  const handleBmiCalculator = function () {
    const bmiFormMetric = document.querySelector("#BmiCalculatorMetric");
    if (bmiFormMetric) {
      bmiFormMetric.addEventListener("submit", (event) => {
        event.preventDefault();

        const height = document.querySelector("#heightMetric")?.value.trim();
        const weight = document.querySelector("#weightMetric")?.value.trim();

        if (!height || !weight) {
          alert("لطفاً قد و وزن را وارد کنید.");
          return;
        }

        const bmi = Number(weight) / (Number(height) / 100) ** 2;
        bmiFormMetric.reset();
        showBmiResult(bmi, ".dzFormBmiMetric");
      });
    }

    const bmiFormImperial = document.querySelector("#BmiCalculatorImperial");
    if (bmiFormImperial) {
      bmiFormImperial.addEventListener("submit", (event) => {
        event.preventDefault();

        const feet = document.querySelector("#heightFeet")?.value.trim();
        const inches =
          document.querySelector("#heightInches")?.value.trim() || 0;
        const weight = document.querySelector("#weightPounds")?.value.trim();

        if (!feet || !weight) {
          alert("لطفاً قد و وزن را وارد کنید.");
          return;
        }

        const totalInches = Number(feet) * 12 + Number(inches);
        const heightMeters = totalInches * 0.0254;
        const weightKg = Number(weight) * 0.453592;

        const bmi = weightKg / heightMeters ** 2;
        bmiFormImperial.reset();
        showBmiResult(bmi, ".dzFormBmiImperial");
      });
    }

    function showBmiResult(bmi, selector) {
      let result = "";

      if (bmi < 18.5) result = "کمبود وزن";
      else if (bmi <= 24.9) result = "وزن نرمال";
      else if (bmi <= 29.9) result = "اضافه وزن";
      else if (bmi <= 34.9) result = "چاقی";
      else result = "چاقی شدید";

      const container = document.querySelector(selector);
      if (container) {
        container.innerHTML = `
          <div class="dzFormInner flex gap-5 mt-4">
            <h4 class="title text-white !mb-0">${result}</h4>
            <h5 class="bmi-result text-primary mb-0">شاخص توده بدنی: ${bmi.toFixed(1)}</h5>
          </div>
        `;
      }
    }
  };
  
  const handleflatpickr = () => {
    if (document.querySelector(".flatpickr1")) {
      flatpickr(".flatpickr1", {});
    }

    if (document.querySelector(".time-picker")) {
      flatpickr(".time-picker", {
        enableTime: true,
        noCalendar: true,
        dateFormat: "H:i",
        defaultDate: "13:45",
      });
    }
  };

  const handleMenuActive = () => {
    // نسخه‌ی پروژه: مقایسه‌ی مسیر کامل (آدرس‌های Django با / تمام می‌شوند)
    const normalize = (path) => path.replace(/\/+$/, "").toLowerCase();
    const currentPath = normalize(window.location.pathname);

    document.querySelectorAll(".navbar-nav a, .navbar-nav li").forEach((el) => {
      el.classList.remove("active");
    });

    const links = document.querySelectorAll(
      '.navbar-nav a[href]:not([href^="javascript"])'
    );

    links.forEach((link) => {
      if (link.getAttribute("href").startsWith("#")) return;
      const linkPath = normalize(new URL(link.href).pathname);

      if (linkPath === currentPath) {
        link.classList.add("active");

        const parentLi = link.closest("li.group, li.relative");
        if (parentLi) parentLi.classList.add("active");

        const topLevelLi = link.closest(".navbar-nav > li");
        if (topLevelLi) {
          topLevelLi.classList.add("active");

          const topAnchor = topLevelLi.querySelector(":scope > a");
          if (topAnchor) topAnchor.classList.add("active");
        }
      }
    });
  };

  const directionSwitcher = () => {

    const themeDirection = "rtl" //  "ltr"/"rtl"

    const setCookie = (name, value, days = 30) => {
      const expires = new Date();
      expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);

      document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/`;
    };

    const getCookie = (name) => {
      const cookieName = `${name}=`;

      for (let cookie of document.cookie.split(";")) {
        cookie = cookie.trim();

        if (cookie.startsWith(cookieName)) {
          return cookie.substring(cookieName.length);
        }
      }

      return null;
    };

    
    const setDirection = (direction) => {
      document.documentElement.setAttribute("dir", direction);
      setCookie("direction", direction);

      const url = new URL(window.location);
      url.searchParams.set("data-direction", direction);
      window.history.replaceState({}, "", url);

      const radio = document.querySelector(
        `input[name="direction"][value="${direction}"]`
      );

      if (radio) {
        radio.checked = true;
      }
    };

    const params = new URLSearchParams(window.location.search);
    const paramDirection = params.get("data-direction");

    let direction = paramDirection || getCookie("direction") || "themeDirection";

    if (direction !== "rtl" && direction !== "ltr") {
      direction = "ltr";
    }

    setDirection(direction);

    document.querySelectorAll('input[name="direction"]').forEach((radio) => {
      radio.addEventListener("change", (e) => {
        setDirection(e.target.value);
      });
    });
  };

  /* Function ============ */
  return {
    init() {
      handlePricingTabs();
      handleTouchSpin();
      handleStarRating();
      handleSetCurrentYear();
      handledzNumber();
      handleAppointmentWizard();
      handleLightGallery();
      handleBoxHover();
      handleCounter();
      handleNavScroller();
      handleCustomSelects();
      handleAccordion();
      handleVideoPopup();
      handleTabs();
      handleMasonryBox();
      handleCountdown();
      handleBmiCalculator();
      handleflatpickr();
      handleMenuActive();
      // نسخه‌ی پروژه: جهت صفحه از <html dir="rtl"> در base.html می‌آید.
      // directionSwitcher قالب به‌دلیل باگ "themeDirection" جهت را ltr می‌کرد و URL را تغییر می‌داد.
    },

    load() {},

    resize() {},
  };
})();

document.addEventListener("DOMContentLoaded", function () {
  ClinicMaster.init();
});

window.addEventListener("load", function () {
  ClinicMaster.load();
  const dzPreloader = document.getElementById("dzPreloader");
  setTimeout(function () {
    if (dzPreloader) {
      dzPreloader.remove();
    }
  }, 1000);
  document.body.addEventListener("keydown", function () {
    document.body.classList.add("show-focus-outline");
  });
  document.body.addEventListener("mousedown", function () {
    document.body.classList.remove("show-focus-outline");
  });
});

window.addEventListener("resize", function () {
  ClinicMaster.resize();
});
