const ClinicMasterGsap = function () {
  gsap.registerPlugin(ScrollSmoother, ScrollTrigger);

  let smoother;

  if (!smoother) {
    smoother = ScrollSmoother.create({
      smooth: 1,
      effects: true,
      normalizeScroll: true,
      smoothTouch: 0.1,
    });
  }

  const headerEl = document.querySelector("#headerWrapper1");
  if (headerEl) {

      let tl = gsap.timeline({ paused: true });

      tl.to(headerEl, {
          top: -98,
          duration: 0.3,
          ease: "power2.out"
      });

      ScrollTrigger.create({
          trigger: headerEl,
          start: "bottom top",
          onEnter: () => tl.play(),
          onLeaveBack: () => tl.reverse()
      });
  }

  const initHeaderSticky = () => {
    const header = document.querySelector(".site-header");
    const sidebarStickyWrap = document.querySelector(".sidebar-sticky");

    if (!header) return;

    let lastScroll = 0;
    let animationFrameId;
    const headerHeight = header.offsetHeight || 80;

    const updateStickyHeader = (scrollY) => {
      const shouldFix = scrollY > 100;
      header.classList.toggle("is-fixed", shouldFix);

      if (sidebarStickyWrap) {
        sidebarStickyWrap.style.top = shouldFix
          ? `${headerHeight + 10}px`
          : "60%";
      }

      lastScroll = scrollY;
    };

    const loop = () => {
      const currentScroll =
        typeof smoother?.scrollTop === "function"
          ? smoother.scrollTop()
          : window.scrollY || document.documentElement.scrollTop;

      updateStickyHeader(currentScroll);
      animationFrameId = requestAnimationFrame(loop);
    };

    animationFrameId = requestAnimationFrame(loop);

    return () => {
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
    };
  };

  let cleanupSticky = null;
  const initStickyPosition = (selector = ".my-sticky", offset = 100) => {
    ScrollTrigger.matchMedia({
      "(min-width: 992px)": () => {
        const elements = document.querySelectorAll(selector);
        const triggers = [];
        elements.forEach((el) => {
          const parent = el.parentElement;
          if (!parent) return;

          const spacer = document.createElement("div");
          spacer.style.position = "relative";
          spacer.style.height = el.classList.contains("sidebar-sticky")
            ? 0
            : `${el.offsetHeight + offset}px`;
          parent.insertBefore(spacer, el);
          spacer.appendChild(el);

          Object.assign(el.style, {
            position: "absolute",
            top: el.classList.contains("space-top-0") ? 0 : `${offset}px`,
            left: 0,
            right: 0,
          });

          const trigger = ScrollTrigger.create({
            trigger: spacer,
            start: "top top",
            end: () => `+=${parent.offsetHeight - el.offsetHeight - offset}`,
            pin: el,
            pinSpacing: false,
            scroller: "#smooth-wrapper",
            anticipatePin: 1,
          });

          triggers.push({ trigger, spacer, el });
        });

        return () => {
          triggers.forEach(({ trigger, spacer, el }) => {
            trigger.kill();

            const parent = spacer.parentElement;
            if (parent) {
              parent.insertBefore(el, spacer);
              parent.removeChild(spacer);
            }

            Object.assign(el.style, {
              position: "",
              top: "",
              left: "",
              right: "",
            });
          });
        };
      },
    });
  };

  const initApplySticky = () => {
    if (cleanupSticky) cleanupSticky();
    cleanupSticky = initStickyPosition();
  };

  document.querySelectorAll(".sticky-update-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      setTimeout(() => {
        initApplySticky();
      }, 200);
    });
  });

  const initCustomScroll = () => {
    const content = document.querySelectorAll(".custom-scroll");

    content.forEach((item) => {
      item.addEventListener(
        "wheel",
        function (e) {
          e.stopPropagation();
        },
        { passive: false }
      );

      let startY = 0;
      let startX = 0;

      item.addEventListener(
        "touchstart",
        (e) => {
          const touch = e.touches[0];
          startY = touch.clientY;
          startX = touch.clientX;
        },
        { passive: true }
      );

      item.addEventListener(
        "touchmove",
        (e) => {
          const touch = e.touches[0];
          const deltaY = startY - touch.clientY;
          const deltaX = startX - touch.clientX;

          item.scrollTop += deltaY;
          item.scrollLeft += deltaX;

          startY = touch.clientY;
          startX = touch.clientX;

          e.stopPropagation();
          e.preventDefault();
        },
        { passive: false }
      );
    });
  };
  
  const initScrollTop = function () {
    const scrollBtn = document.getElementById("scrollProgress");
    if (!scrollBtn) return;

    const circle = scrollBtn.querySelector("circle");
    if (!circle) return;

    const radius = circle.r.baseVal.value;
    const circumference = 2 * Math.PI * radius;

    circle.style.strokeDasharray = `${circumference}`;
    circle.style.strokeDashoffset = `${circumference}`;

    function updateProgress() {
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      const docHeight =
        document.documentElement.scrollHeight -
        document.documentElement.clientHeight;
      const scrollPercent = scrollTop / docHeight;
      const offset = circumference * (1 - scrollPercent);
      circle.style.strokeDashoffset = offset;

      if (scrollTop > 200) {
        scrollBtn.classList.add("active");
      } else {
        scrollBtn.classList.remove("active");
      }
    }

    window.addEventListener("scroll", updateProgress);
    updateProgress();

    scrollBtn.addEventListener("click", () => {
      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    });
  };

  return {
    init() {
      initHeaderSticky();
      initApplySticky();
      initCustomScroll();
      initScrollTop();
    },
  };
};

window.addEventListener("load", () => {
  ClinicMasterGsap().init();
});

let resizeTimeout;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimeout);
  resizeTimeout = setTimeout(() => {
    ScrollTrigger.refresh();
  }, 250);
});
