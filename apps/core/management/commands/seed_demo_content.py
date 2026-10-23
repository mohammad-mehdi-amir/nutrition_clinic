from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.blog.models import Post, PostCategory
from apps.core.models import FAQ, Service, SiteSettings
from apps.core.seed_data import content
from apps.shop.models import Category, Product

IMAGES_DIR = Path(content.__file__).resolve().parent / "images"


class Command(BaseCommand):
    help = (
        "پر کردن سایت با محتوای نمونه‌ی معنی‌دار (خدمات، سؤالات، مقالات، محصولات، پکیج‌ها، تصاویر سایت). "
        "فقط فیلدهای خالی پر و موارد ناموجود ساخته می‌شوند؛ داده‌ی موجود بازنویسی نمی‌شود."
    )

    def handle(self, *args, **options):
        self.created = 0
        self.filled = 0

        with transaction.atomic():
            self.seed_site_settings()
            self.seed_services()
            self.seed_faqs()
            self.seed_blog()
            self.seed_shop()

        self.stdout.write(self.style.SUCCESS(f"{self.created} مورد جدید ساخته شد، {self.filled} فیلد خالی پر شد."))

    # ---------- helpers ----------

    def attach_image(self, instance, field_name, image_key):
        """تصویر را فقط اگر فیلد خالی باشد قرار می‌دهد."""
        if getattr(instance, field_name):
            return False

        path = IMAGES_DIR / f"{image_key}.webp"
        with path.open("rb") as fp:
            getattr(instance, field_name).save(path.name, File(fp), save=False)

        self.filled += 1
        return True

    def get_or_create(self, model, lookup, defaults):
        obj, created = model.objects.get_or_create(**lookup, defaults=defaults)
        if created:
            self.created += 1
        return obj, created

    # ---------- sections ----------

    def seed_site_settings(self):
        settings_obj = SiteSettings.load()
        changed = False

        for field, value in content.SITE.items():
            if not getattr(settings_obj, field):
                setattr(settings_obj, field, value)
                self.filled += 1
                changed = True

        for field, image_key in content.SITE_IMAGES.items():
            changed |= self.attach_image(settings_obj, field, image_key)

        if changed or not settings_obj.pk:
            settings_obj.save()

    def seed_services(self):
        for order, item in enumerate(content.SERVICES):
            service, _ = self.get_or_create(
                Service,
                {"slug": item["slug"]},
                {"title": item["title"], "summary": item["summary"], "body": item["body"], "order": order},
            )
            if self.attach_image(service, "image", item["image"]):
                service.save()

    def seed_faqs(self):
        for order, (question, answer) in enumerate(content.FAQS):
            self.get_or_create(FAQ, {"question": question}, {"answer": answer, "order": order})

    def seed_blog(self):
        author = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        categories = {}

        for order, (slug, name) in enumerate(content.BLOG_CATEGORIES):
            categories[slug], _ = self.get_or_create(PostCategory, {"slug": slug}, {"name": name, "order": order})

        for item in content.POSTS:
            post, _ = self.get_or_create(
                Post,
                {"slug": item["slug"]},
                {
                    "title": item["title"],
                    "category": categories[item["category"]],
                    "author": author,
                    "summary": item["summary"],
                    "body": item["body"],
                    "status": Post.STATUS_PUBLISHED,
                    "published_at": timezone.now() - timedelta(days=item["days_ago"]),
                },
            )
            if self.attach_image(post, "image", item["image"]):
                post.save()

    def seed_shop(self):
        categories = {}

        for order, (slug, name) in enumerate(content.PRODUCT_CATEGORIES):
            categories[slug], _ = self.get_or_create(Category, {"slug": slug}, {"name": name, "order": order})

        for item in content.PRODUCTS:
            product, _ = self.get_or_create(
                Product,
                {"slug": item["slug"]},
                {
                    "product_type": Product.TYPE_PHYSICAL,
                    "category": categories[item["category"]],
                    "name": item["name"],
                    "short_description": item["short_description"],
                    "description": item["description"],
                    "price": item["price"],
                    "discount_price": item.get("discount_price"),
                    "stock": item["stock"],
                },
            )
            if self.attach_image(product, "image", item["image"]):
                product.save()

        for item in content.PACKAGES:
            package, _ = self.get_or_create(
                Product,
                {"slug": item["slug"]},
                {
                    "product_type": Product.TYPE_PACKAGE,
                    "name": item["name"],
                    "short_description": item["short_description"],
                    "description": item["description"],
                    "price": item["price"],
                    "discount_price": item.get("discount_price"),
                    "duration_days": item["duration_days"],
                    "features": item["features"],
                },
            )
            if self.attach_image(package, "image", item["image"]):
                package.save()
