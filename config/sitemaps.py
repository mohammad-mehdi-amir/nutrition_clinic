from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.blog.models import Post, PostCategory
from apps.core.models import Service
from apps.shop.models import Category, Product


class StaticViewSitemap(Sitemap):
    changefreq = "weekly"

    PAGES = {
        "core:home": 1.0,
        "core:about": 0.6,
        "core:services": 0.8,
        "appointments:doctors": 0.7,
        "appointments:book_appointment": 0.8,
        "shop:product_list": 0.8,
        "shop:packages": 0.8,
        "blog:post_list": 0.7,
        "core:faqs": 0.5,
        "core:contact": 0.5,
        "core:terms": 0.2,
        "core:privacy": 0.2,
    }

    def items(self):
        return list(self.PAGES)

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return self.PAGES[item]


class ServiceSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return Service.objects.filter(is_active=True)


class ProductSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Product.objects.available()

    def lastmod(self, obj):
        return obj.updated_at


class ProductCategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return Category.objects.filter(is_active=True)


class PostSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Post.objects.published()

    def lastmod(self, obj):
        return obj.updated_at


class PostCategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.4

    def items(self):
        return PostCategory.objects.filter(is_active=True)


SITEMAPS = {
    "pages": StaticViewSitemap,
    "services": ServiceSitemap,
    "products": ProductSitemap,
    "product-categories": ProductCategorySitemap,
    "posts": PostSitemap,
    "post-categories": PostCategorySitemap,
}
