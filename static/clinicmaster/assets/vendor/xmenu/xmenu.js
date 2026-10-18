const xMenu = function () {
  "use strict";

  const xMenuSearch = () => {
    const quickSearchBtns = document.querySelectorAll(".quick-search");
    const searchRemoveBtns = document.querySelectorAll(".search-remove");

    quickSearchBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetSelector = btn.getAttribute("data-target");
        const targetEl = document.querySelector(targetSelector);
        if (targetEl) {
          targetEl.classList.add("show");
          document.body.classList.add("fixed");
        }
      });
    });

    searchRemoveBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const searchEls = document.querySelectorAll(".xmenu-search");
        searchEls.forEach((el) => el.classList.remove("show"));
        document.body.classList.remove("fixed");
      });
    });
  };

  const xMenuTheme = () => {
    const screenWidth = window.innerWidth;

    if (screenWidth <= 991) {
      const links = document.querySelectorAll(
        ".navbar-nav > li > a, .sub-menu > li > a, .navbar-nav > li > a > i, .sub-menu > li > a > i"
      );

      const tabIndexEls = document.querySelectorAll(".tabindex");
      tabIndexEls.forEach((el) => el.setAttribute("tabindex", "0"));

      links.forEach((link) => {
        const clone = link.cloneNode(true);
        link.parentNode.replaceChild(clone, link);

        clone.addEventListener("click", (e) => handleMenus(e, clone));
        clone.addEventListener("keypress", (e) => {
          if (e.key === "Enter") {
            handleMenus(e, clone);
          }
        });
      });

      function handleMenus(e, menuEl) {
        const parentLi = menuEl.closest("li");
        const nextMenu = menuEl.nextElementSibling;
        const hasSubMenu =
          parentLi?.querySelector("ul, .sub-menu, .mega-menu") !== null;

        if (hasSubMenu) {
          e.preventDefault();

          if (
            nextMenu?.classList.contains("sub-menu") ||
            nextMenu?.classList.contains("mega-menu")
          ) {
            slideDown(nextMenu);
          }

          const siblings = parentLi?.parentElement?.children;
          if (siblings) {
            Array.from(siblings).forEach((sibling) => {
              if (sibling !== parentLi) {
                const subMenus = sibling.querySelectorAll(
                  ".sub-menu, .mega-menu"
                );
                subMenus.forEach((sm) => slideUp(sm));
              }
            });
          }
        }

        if (parentLi?.classList.contains("open")) {
          const submenuEls = parentLi.querySelectorAll(".sub-menu, .mega-menu");
          submenuEls.forEach((sm) =>
            slideUp(sm, () => {
              parentLi.classList.remove("open");
            })
          );
        } else {
          const openSiblings =
            parentLi?.parentElement?.querySelectorAll("li.open");
          openSiblings?.forEach((li) => li.classList.remove("open"));
          parentLi?.classList.add("open");
        }
      }

      function slideUp(el, callback) {
        el.style.transition = "height 0.3s ease";
        el.style.overflow = "hidden";
        el.style.height = el.scrollHeight + "px";
        requestAnimationFrame(() => {
          el.style.height = "0px";
        });
        setTimeout(() => {
          el.style.display = "none";
          el.style.removeProperty("height");
          el.style.removeProperty("transition");
          el.style.removeProperty("overflow");
          if (callback) callback();
        }, 300);
      }

      function slideDown(el) {
        el.style.removeProperty("display");
        let display = window.getComputedStyle(el).display;
        if (display === "none") display = "block";
        el.style.display = display;

        const height = el.scrollHeight + "px";
        el.style.height = "0px";
        el.style.overflow = "hidden";
        el.style.transition = "height 0.3s ease";

        requestAnimationFrame(() => {
          el.style.height = height;
        });

        setTimeout(() => {
          el.style.removeProperty("height");
          el.style.removeProperty("transition");
          el.style.removeProperty("overflow");
        }, 300);
      }
    } else {
      const tabIndexEls = document.querySelectorAll(".tabindex");
      tabIndexEls.forEach((el) => el.removeAttribute("tabindex"));
    }
  };

  const xMenuSidebar = () => {
    const headers = document.querySelectorAll("header");

    headers.forEach((header) => {
      const toggler = header.querySelector(".xmenu-toggler");
      const headerNav = header.querySelector(".header-nav");
      const menuClose = header.querySelector(".menu-close");

      if (!toggler || !headerNav) return;

      const toggleMenu = () => {
        const isOpen = headerNav.classList.toggle("show");
        toggler.classList.toggle("open");

        if (window.innerWidth < 992) {
          document.body.classList.toggle("overflow-hidden", isOpen);
        }
      };

      const closeMenu = () => {
        headerNav.classList.remove("show");
        toggler.classList.remove("open");

        if (window.innerWidth < 992) {
          document.body.classList.remove("overflow-hidden");
        }
      };

      toggler.addEventListener("click", toggleMenu);

      if (menuClose) {
        menuClose.addEventListener("click", closeMenu);
      }

      window.addEventListener("resize", () => {
        if (window.innerWidth >= 992) {
          document.body.classList.remove("overflow-hidden");
        }
      });
    });
  };

  const xMenuTabs = () => {
    const tabContainers = document.querySelectorAll(".custom-tab");

    tabContainers.forEach((container) => {
      const titles = container.querySelectorAll(".tab-title");
      const contents = container.querySelectorAll(".tab-content");

      titles[0]?.classList.add("active");
      contents[0]?.classList.add("active");
      xMenuAccordion(contents[0]);

      container.addEventListener("click", (e) => {
        const clicked = e.target.closest(".tab-title");
        if (!clicked || !container.contains(clicked)) return;

        titles.forEach((t, i) => {
          const isActive = t === clicked;
          t.classList.toggle("active", isActive);
          contents[i].classList.toggle("active", isActive);

          if (isActive) {
            xMenuAccordion(contents[i]);
          }
        });
      });
    });
  };

  const xMenuAccordion = (container = document) => {
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

  const xMenuSwiper = () => {
    const swiperEl = document.getElementById("xMenuSwiper");
    if (!swiperEl) return;

    const swiper = new Swiper("#xMenuSwiper", {
      loop: true,
      spaceBetween: 16,
      slidesPerView: 4,
      speed: 500,
      autoplay: {
        delay: 1500,
      },
      pagination: {
        el: ".swiper-pagination",
        clickable: true,
        dynamicBullets: true,
      },
      navigation: {
        nextEl: ".swiper-button-next",
        prevEl: ".swiper-button-prev",
      },
      breakpoints: {
        0: {
          slidesPerView: 2,
        },
        591: {
          slidesPerView: 4,
        },
      },
    });
  };

  const xMenuHeartBlast = () => {
    const hearts = document.querySelectorAll(".heart");

    hearts.forEach((heart) => {
      heart.addEventListener("click", () => {
        heart.classList.toggle("heart-blast");
      });
    });
  };

  const xMenuSetCurrentYear = () => {
    const currentDate = new Date();
    let currentYear = currentDate.getFullYear();
    let elements = document.getElementsByClassName("current-year");

    for (const element of elements) {
      element.innerHTML = currentYear;
    }
  };

  const xMenuOffcanvas = () => {
    const drawers = document.querySelectorAll("[data-drawer]");
    const drawersHide = document.querySelectorAll("[data-drawer-hide]");
    drawers.forEach((btn) => {
      btn.addEventListener("click", function () {
        if (btn.dataset.drawer) {
          const backdrop = document.createElement("div");
          backdrop.classList.add(
            "bg-gray-900/50",
            "fixed",
            "inset-0",
            "z-999999",
            "drawer-backdrop"
          );
          backdrop.addEventListener("click", function () {
            document
              .querySelector(btn.dataset.drawer)
              .classList.remove("translate-none!");
            if (btn.dataset.drawerPlacement == "left") {
              document
                .querySelector(btn.dataset.drawer)
                .classList.add("-translate-x-full");
            } else if (btn.dataset.drawerPlacement == "right") {
              document
                .querySelector(btn.dataset.drawer)
                .classList.add("translate-x-full");
            } else if (btn.dataset.drawerPlacement == "top") {
              document
                .querySelector(btn.dataset.drawer)
                .classList.add("-translate-y-full");
            } else if (btn.dataset.drawerPlacement == "bottom") {
              document
                .querySelector(btn.dataset.drawer)
                .classList.add("translate-y-full");
            } else {
              document
                .querySelector(btn.dataset.drawer)
                .classList.add("-translate-x-full");
            }
            this.remove();
          });
          document.querySelector("body").append(backdrop);
          if (btn.dataset.drawerPlacement == "left") {
            document
              .querySelector(btn.dataset.drawer)
              .classList.remove("-translate-x-full");
            document
              .querySelector(btn.dataset.drawer)
              .classList.add("translate-none!");
          } else if (btn.dataset.drawerPlacement == "right") {
            document
              .querySelector(btn.dataset.drawer)
              .classList.remove("translate-x-full");
            document
              .querySelector(btn.dataset.drawer)
              .classList.add("translate-none!");
          } else if (btn.dataset.drawerPlacement == "top") {
            document
              .querySelector(btn.dataset.drawer)
              .classList.remove("-translate-y-full");
            document
              .querySelector(btn.dataset.drawer)
              .classList.add("translate-none!");
          } else if (btn.dataset.drawerPlacement == "bottom") {
            document
              .querySelector(btn.dataset.drawer)
              .classList.remove("translate-y-full");
            document
              .querySelector(btn.dataset.drawer)
              .classList.add("translate-none!");
          } else {
            document
              .querySelector(btn.dataset.drawer)
              .classList.remove("-translate-x-full");
            document
              .querySelector(btn.dataset.drawer)
              .classList.add("translate-none!");
          }
        }
      });
    });
    drawersHide.forEach((btn) => {
      btn.addEventListener("click", function () {
        if (btn.dataset.drawerHide) {
          const position = document.querySelector(
            `[data-drawer="#${btn.dataset.drawerHide}"]`
          );
          document
            .querySelector(`#${btn.dataset.drawerHide}`)
            .classList.remove("translate-none!");
          if (position.dataset.drawerPlacement == "left") {
            document
              .querySelector(`#${btn.dataset.drawerHide}`)
              .classList.add("-translate-x-full");
          } else if (position.dataset.drawerPlacement == "right") {
            document
              .querySelector(`#${btn.dataset.drawerHide}`)
              .classList.add("translate-x-full");
          } else if (position.dataset.drawerPlacement == "top") {
            document
              .querySelector(`#${btn.dataset.drawerHide}`)
              .classList.add("-translate-y-full");
          } else if (position.dataset.drawerPlacement == "bottom") {
            document
              .querySelector(`#${btn.dataset.drawerHide}`)
              .classList.add("translate-y-full");
          } else {
            document
              .querySelector(`#${btn.dataset.drawerHide}`)
              .classList.add("-translate-x-full");
          }
          document.querySelector(".drawer-backdrop").remove();
        }
      });
    });
  };

  const xMenuCountDown = () => {
    const daysEl = document.getElementById("days");
    const hoursEl = document.getElementById("hours");
    const minutesEl = document.getElementById("minutes");
    const secondsEl = document.getElementById("seconds");

    if (!daysEl || !hoursEl || !minutesEl || !secondsEl) return;

    const headlineEl = document.getElementById("headline");
    const countdownEl = document.getElementById("countdown");
    const contentEl = document.getElementById("content");

    const second = 1000,
      minute = second * 60,
      hour = minute * 60,
      day = hour * 24;

    let today = new Date(),
      dd = String(today.getDate()).padStart(2, "0"),
      mm = String(today.getMonth() + 1).padStart(2, "0"),
      yyyy = today.getFullYear(),
      nextYear = yyyy + 1,
      dayMonth = "09/30/",
      birthday = dayMonth + yyyy;

    today = mm + "/" + dd + "/" + yyyy;
    if (today > birthday) {
      birthday = dayMonth + nextYear;
    }

    const countDown = new Date(birthday).getTime();

    const x = setInterval(() => {
      const now = new Date().getTime();
      const distance = countDown - now;

      daysEl.innerText = Math.floor(distance / day);
      hoursEl.innerText = Math.floor((distance % day) / hour);
      minutesEl.innerText = Math.floor((distance % hour) / minute);
      secondsEl.innerText = Math.floor((distance % minute) / second);

      if (distance < 0) {
        if (headlineEl) headlineEl.innerText = "It's my birthday!";
        if (countdownEl) countdownEl.style.display = "none";
        if (contentEl) contentEl.style.display = "block";
        clearInterval(x);
      }
    }, 1000);
  };

  const xMenuHamburgerMenu = () => {
    const menu = document.getElementById("menu");
    const openBtn = document.querySelector(".hamburger-open");
    const closeBtn = document.querySelector(".hamburger-close");
    const menuLinksContainer = document.querySelector(".hamburger-links");

    if (openBtn) {
      openBtn.addEventListener("click", () => {
        if (menu) menu.classList.add("open");
        document.body.classList.add("overflow-hidden");
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener("click", () => {
        if (menu) menu.classList.remove("open");
        document.body.classList.remove("overflow-hidden");
      });
    }

    if (menuLinksContainer) {
      menuLinksContainer.addEventListener("click", (e) => {
        const link = e.target.closest(".has-submenu > a");
        if (!link) return;

        e.preventDefault();

        const clickedItem = link.parentElement;

        const parentList = clickedItem.parentElement;
        const siblingItems = parentList
          ? parentList.querySelectorAll(":scope > .has-submenu")
          : [];

        siblingItems.forEach((item) => {
          if (item !== clickedItem) {
            item.classList.remove("open");
          }
        });

        clickedItem.classList.toggle("open");
      });
    }
  };

  return {
    init() {
      xMenuSearch();
      xMenuTheme();
      xMenuSidebar();
      xMenuTabs();
      xMenuAccordion();
      xMenuSwiper();
      xMenuHeartBlast();
      xMenuSetCurrentYear();
      xMenuOffcanvas();
      xMenuCountDown();
      xMenuHamburgerMenu();
    },
    resize() {
      xMenuTheme();
    },
  };
};

window.addEventListener("load", function () {
  setTimeout(function () {
    const preloader = document.getElementById("xMenuPreloader");
    if (preloader) {
      preloader.remove();
    }
  }, 50);

  setTimeout(function () {
    const loadingArea = document.getElementById("loading-area");
    if (loadingArea) {
      loadingArea.remove();
    }
  }, 100);
});

document.addEventListener("DOMContentLoaded", function () {
  xMenu().init();
});
window.addEventListener("resize", () => {
  xMenu().resize();
});
