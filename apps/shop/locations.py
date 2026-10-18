"""
استان‌ها و شهرهای ایران برای فرم تسویه‌حساب.
داده: apps/shop/data/iran_locations.json (iran-cities-json، MIT).
"""
import json
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "data" / "iran_locations.json"


@lru_cache(maxsize=1)
def get_locations():
    """{نام استان: [نام شهرها]} به ترتیب الفبای فارسی."""
    with DATA_FILE.open(encoding="utf-8") as fp:
        return json.load(fp)["provinces"]


def province_choices():
    return [(name, name) for name in get_locations()]


def city_choices(province):
    return [(name, name) for name in get_locations().get(province, [])]


def is_valid_city(province, city):
    return city in get_locations().get(province, ())
