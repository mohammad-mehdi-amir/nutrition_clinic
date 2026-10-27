"""
ساخت نسخه‌ی هم‌رنگ هویت بصری از تصاویر تزئینی قالب ClinicMaster.

فایل‌های اصلی قالب دست نمی‌خورند؛ خروجی در static/img/theme/ ذخیره می‌شود.
پالت از بنر کلینیک گرفته شده (سبز جنگلی تیره، زیتونی-مریمی، طلایی-بژ). با تغییر رنگ‌های
زیر و اجرای دوباره، تصاویر بازسازی می‌شوند:

    python tools/recolor_theme_images.py
"""
from pathlib import Path

from PIL import Image, ImageOps

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "static/clinicmaster/src/images"
OUT = BASE / "static/img/theme"

# duotone پس‌زمینه‌ها: تیره ← میانه ← روشن (متن سفید روی همه‌ی آن‌ها خواناست)
DARK, MID, LIGHT = (46, 52, 38), (84, 94, 64), (122, 132, 92)
GOLD = (217, 201, 160)  # #D9C9A0 — جایگزین زرد قالب


def duotone(src, dst, quality=82):
    image = Image.open(src).convert("L")
    image = ImageOps.autocontrast(image, cutoff=1)
    image = ImageOps.colorize(image, black=DARK, mid=MID, white=LIGHT)
    image.save(dst, "WEBP", quality=quality, method=6)


def recolor_alpha(src, dst, color):
    """شکل‌های تک‌رنگ شفاف (مثل جرقه‌های زرد): فقط رنگ عوض می‌شود، شفافیت می‌ماند."""
    image = Image.open(src).convert("RGBA")
    alpha = image.getchannel("A")
    solid = Image.new("RGBA", image.size, color + (255,))
    solid.putalpha(alpha)
    solid.save(dst, "PNG", optimize=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    duotone(SRC / "hero-banner/banner-1.webp", OUT / "hero-bg.webp")
    duotone(SRC / "banner/bnr1.webp", OUT / "page-banner-bg.webp")
    recolor_alpha(SRC / "banner/item4.png", OUT / "sparkle-gold.png", GOLD)
    for path in sorted(OUT.iterdir()):
        print(f"{path.relative_to(BASE)}  {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
