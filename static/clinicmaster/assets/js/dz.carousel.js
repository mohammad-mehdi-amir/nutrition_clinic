const ClinicMasterCarousel = function () {
  const handleTestimonialSwiper1 = () => {
    const swiperEl = document.querySelector(".testimonial-swiper1");
    if (!swiperEl) return;

    new Swiper(".testimonial-swiper1", {
      loop: true,
      spaceBetween: 20,
      slidesPerView: 1,
      navigation: {
        nextEl: ".swiper1-button-next",
        prevEl: ".swiper1-button-prev",
      },
    });
  };

  const handleTestimonialSwiper4 = () => {
    const swiperEl = document.querySelector(".testimonial-swiper4");
    if (!swiperEl) return;

    const testimonialThumbSwiper4 = new Swiper(".testimonial-thumb-swiper4", {
      slidesPerView: 1,
      effect: "fade",
      centeredSlides: true,
    });

    new Swiper(".testimonial-swiper4", {
      loop: true,
      spaceBetween: 20,
      slidesPerView: 1,
      centeredSlides: true,
      autoplay: {
        delay: 3000,
      },
      thumbs: {
        swiper: testimonialThumbSwiper4,
      },
      navigation: {
        nextEl: ".swiper4-button-next",
        prevEl: ".swiper4-button-prev",
      },
    });
  };

  const BlogSlideshowSwiper = () => {
    const swiperEl = document.querySelector(".blog-slideshow");
    if (!swiperEl) return;

    new Swiper(".blog-slideshow", {
      loop: true,
      spaceBetween: 0,
      slidesPerView: "auto",
      speed: 1500,
      autoplay: {
        delay: 2000,
      },
      pagination: {
        el: ".swiper-pagination-two",
        clickable: true,
      },
    });
  };

  if (
    document.querySelector(".galley-thumb-swiper") &&
    document.querySelector(".galley-swiper")
  ) {
    const swiperThumbs = new Swiper(".galley-thumb-swiper", {
      loop: false,
      spaceBetween: 10,
      slidesPerView: 4,
      freeMode: true,
      watchSlidesProgress: true,
    });

    new Swiper(".galley-swiper", {
      loop: true,
      spaceBetween: 10,
      thumbs: {
        swiper: swiperThumbs,
      },
    });
  }

  const handleTestimonialSwiper = function () {
    const wrapper = document.querySelector(".testimonial-swiper-wrapper");
    if (!wrapper) return;

    const testimonialThumbs = new Swiper(".testimonial-thumbs", {
      speed: 1500,
      parallax: true,
      slidesPerView: 1,
      spaceBetween: 10,
      loop: true,
      autoplay: {
        delay: 3000,
      },
    });

    new Swiper(".testimonial-swiper", {
      speed: 1500,
      parallax: true,
      slidesPerView: 1,
      spaceBetween: 10,
      loop: true,
      autoplay: {
        delay: 3000,
      },
      navigation: {
        nextEl: ".testimonial-button-next",
        prevEl: ".testimonial-button-prev",
      },
      pagination: {
        el: ".swiper-pagination",
        clickable: true,
      },
      thumbs: {
        swiper: testimonialThumbs,
      },
    });
  };

  const handleServiceSwiper = () => {
    const swiperEl = document.querySelector(".service-swiper");
    if (!swiperEl) return;

    new Swiper(".service-swiper", {
      speed: 1500,
      parallax: true,
      slidesPerView: 1,
      spaceBetween: 35,
      loop: true,
      autoplay: {
        delay: 3000,
      },
      breakpoints: {
        567: {
          slidesPerView: 1,
          spaceBetween: 15,
        },
        767: {
          slidesPerView: 2,
          spaceBetween: 20,
        },
        1025: {
          slidesPerView: 4,
          spaceBetween: 35,
        },
      },
    });
  };

  const handleVerticalSwiper = () => {
    const blogVerticalSwiper = document.querySelector(".blog-vertical-swiper");

    if (blogVerticalSwiper) {
      const teamSwiperThumb = new Swiper(".blog-vertical-swiper-thumb", {
        direction: "vertical",
        slidesPerView: 3,
        mousewheel: false,
        spaceBetween: 10,
        autoplay: {
          delay: 3000,
        },
        breakpoints: {
          320: {
            slidesPerView: 1,
            direction: "horizontal",
          },
          767: {
            slidesPerView: 2,
            direction: "vertical",
          },
          1191: {
            slidesPerView: 3,
          },
        },
      });

      new Swiper(".blog-vertical-swiper", {
        slidesPerView: 1,
        effect: "fade",
        grabCursor: true,
        thumbs: {
          swiper: teamSwiperThumb,
        },
        navigation: {
          nextEl: ".blog-swiper-next",
          prevEl: ".blog-swiper-prev",
        },
      });
    }
  };

  const handleCompareSwiper2 = function () {
    const swiperContainer = document.querySelector(".compare-swiper-2");

    if (swiperContainer) {
      const compareSwiper = new Swiper(".compare-swiper-2", {
        loop: true,
        slidesPerView: 3,
        spaceBetween: 20,
        centeredSlides: true,
        autoplay: {
          delay: 3000,
        },
        navigation: {
          nextEl: ".compare-swiper-2-next",
          prevEl: ".compare-swiper-2-prev",
        },
        pagination: {
          el: ".compare-pagination-swiper",
          type: "progressbar",
        },
        breakpoints: {
          1481: {
            slidesPerView: 2.6,
          },
          1280: {
            slidesPerView: 3,
          },
          991: {
            slidesPerView: 3,
          },
          320: {
            slidesPerView: 2,
          },
        },
      });

      const paginationCurrent = document.querySelector(
        ".compare-slider__current"
      );
      const paginationTotal = document.querySelector(".compare-slider__total");

      if (paginationCurrent && paginationTotal) {
        const mainSliderPagination = () => {
          const totalSlides =
            compareSwiper.slides.length - compareSwiper.loopedSlides * 2;
          let current = compareSwiper.realIndex + 1;
          if (current > totalSlides) current = 1;
          const currentFormatted = current < 10 ? `0${current}` : current;
          const totalFormatted =
            totalSlides < 10 ? `0${totalSlides}` : totalSlides;

          paginationCurrent.innerHTML = currentFormatted;
          paginationTotal.innerHTML = totalFormatted;
        };

        mainSliderPagination();
        compareSwiper.on("slideChange", mainSliderPagination);
      }
    }
  };

  const handleTestimonialSwiper7 = function () {
    const swiperContainer = document.querySelector(".testimonial-swiper7");

    if (swiperContainer) {
      const testimonialSwiper7 = new Swiper(".testimonial-swiper7", {
        loop: true,
        spaceBetween: 0,
        slidesPerView: 1,
        autoplay: {
          delay: 3000,
        },
        pagination: {
          el: ".testimonial-pagination-swiper7",
          clickable: true,
        },
      });
    }
  };

  return {
    load() {
      handleTestimonialSwiper();
      handleTestimonialSwiper1();
      handleTestimonialSwiper4();
      handleTestimonialSwiper7();
      BlogSlideshowSwiper();
      handleServiceSwiper();
      handleVerticalSwiper();
      handleCompareSwiper2();
    },
  };
};

window.addEventListener("load", function () {
  ClinicMasterCarousel().load();
});
