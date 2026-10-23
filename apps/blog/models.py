import math

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from utils.fields import WebPImageField


class PostCategory(models.Model):
    name = models.CharField(max_length=100, verbose_name="نام")
    slug = models.SlugField(max_length=110, unique=True, allow_unicode=True, verbose_name="نامک (آدرس)")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "دسته‌بندی مقاله"
        verbose_name_plural = "دسته‌بندی‌های مقالات"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("blog:category", kwargs={"slug": self.slug})


class PostQuerySet(models.QuerySet):
    def published(self):
        """فقط مقاله‌های منتشرشده‌ای که زمان انتشارشان رسیده و دسته‌شان فعال است."""
        return self.filter(
            status=Post.STATUS_PUBLISHED,
            published_at__lte=timezone.now(),
        ).filter(Q(category__isnull=True) | Q(category__is_active=True))


class Post(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "پیش‌نویس"),
        (STATUS_PUBLISHED, "منتشرشده"),
    ]

    title = models.CharField(max_length=200, verbose_name="عنوان")
    slug = models.SlugField(max_length=210, unique=True, allow_unicode=True, verbose_name="نامک (آدرس)")
    category = models.ForeignKey(
        PostCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="posts",
        verbose_name="دسته‌بندی",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
        verbose_name="نویسنده",
    )
    image = WebPImageField(upload_to="blog/", blank=True, verbose_name="تصویر شاخص")
    summary = models.CharField(
        max_length=300,
        verbose_name="خلاصه",
        help_text="در کارت مقاله و توضیحات متای صفحه (SEO) نمایش داده می‌شود.",
    )
    body = models.TextField(
        verbose_name="متن مقاله",
        help_text="بین پاراگراف‌ها یک خط خالی بگذارید. «## » در ابتدای خط = تیتر، «- » = آیتم فهرست.",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name="وضعیت")
    published_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="زمان انتشار",
        help_text="مقاله‌ی منتشرشده تا این زمان در سایت نمایش داده نمی‌شود (انتشار زمان‌بندی‌شده).",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین تغییر")

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-id"]
        verbose_name = "مقاله"
        verbose_name_plural = "مقالات"
        indexes = [models.Index(fields=["status", "published_at"])]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog:post_detail", kwargs={"slug": self.slug})

    @property
    def is_public(self):
        return (
            self.status == self.STATUS_PUBLISHED
            and self.published_at <= timezone.now()
            and (self.category is None or self.category.is_active)
        )

    @property
    def reading_minutes(self):
        return max(1, math.ceil(len(self.body.split()) / 200))

    @property
    def author_name(self):
        if not self.author:
            return ""
        return self.author.get_full_name() or ""
