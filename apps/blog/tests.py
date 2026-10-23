from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Post, PostCategory
from .templatetags.blog_tags import article_body


def make_post(title="مقاله", slug=None, **extra):
    defaults = dict(
        title=title,
        slug=slug or title.replace(" ", "-"),
        summary=f"خلاصه‌ی {title}",
        body="پاراگراف اول.",
        status=Post.STATUS_PUBLISHED,
        published_at=timezone.now() - timedelta(hours=1),
    )
    defaults.update(extra)
    return Post.objects.create(**defaults)


class PublishedVisibilityTests(TestCase):

    def test_only_published_and_due_posts_are_listed(self):
        make_post("منتشرشده")
        make_post("پیش‌نویس", status=Post.STATUS_DRAFT)
        make_post("زمان‌بندی‌شده", published_at=timezone.now() + timedelta(days=1))

        response = self.client.get(reverse("blog:post_list"))

        self.assertContains(response, "منتشرشده")
        self.assertNotContains(response, "پیش‌نویس")
        self.assertNotContains(response, "زمان‌بندی‌شده")

    def test_draft_detail_404_for_public_but_previewable_by_staff(self):
        draft = make_post("پیش‌نویس", status=Post.STATUS_DRAFT)

        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)

        staff = get_user_model().objects.create_user(username="staff", is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(draft.get_absolute_url())
        self.assertContains(response, "پیش‌نمایش کارکنان")
        self.assertContains(response, "noindex")

    def test_inactive_category_hides_posts(self):
        category = PostCategory.objects.create(name="غیرفعال", slug="inactive", is_active=False)
        post = make_post("در دسته‌ی غیرفعال", category=category)

        self.assertNotContains(self.client.get(reverse("blog:post_list")), "در دسته‌ی غیرفعال")
        self.assertEqual(self.client.get(post.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(category.get_absolute_url()).status_code, 404)


class ListAndDetailTests(TestCase):

    def test_category_filter_and_search(self):
        nutrition = PostCategory.objects.create(name="تغذیه", slug="nutrition")
        make_post("صبحانه‌ی سالم", category=nutrition)
        make_post("ورزش صبحگاهی")

        # «آخرین مقالات» نوار کناری همه‌ی مقالات را دارد؛ پس فهرست اصلی صفحه بررسی می‌شود
        category_page = self.client.get(nutrition.get_absolute_url())
        self.assertEqual([p.title for p in category_page.context["posts"]], ["صبحانه‌ی سالم"])

        search = self.client.get(reverse("blog:post_list"), {"q": "ورزش"})
        self.assertEqual([p.title for p in search.context["posts"]], ["ورزش صبحگاهی"])

    def test_pagination(self):
        for i in range(8):
            make_post(f"مقاله {i}", slug=f"post-{i}")
        first = self.client.get(reverse("blog:post_list"))
        second = self.client.get(reverse("blog:post_list"), {"page": 2})
        self.assertEqual(len(first.context["posts"]), 6)
        self.assertEqual(len(second.context["posts"]), 2)

    def test_detail_seo_and_related(self):
        category = PostCategory.objects.create(name="تغذیه", slug="nutrition")
        post = make_post("اصلی", category=category, summary="خلاصه‌ی سئو")
        make_post("مرتبط", category=category)
        make_post("نامرتبط")

        response = self.client.get(post.get_absolute_url())

        self.assertContains(response, 'property="og:type" content="article"')
        self.assertContains(response, '<meta name="description" content="خلاصه‌ی سئو">')
        self.assertEqual([p.title for p in response.context["related_posts"]], ["مرتبط"])

    def test_home_shows_latest_posts(self):
        make_post("مقاله‌ی صفحه‌ی خانه")
        self.assertContains(self.client.get(reverse("core:home")), "مقاله‌ی صفحه‌ی خانه")

    def test_reading_minutes(self):
        self.assertEqual(make_post("کوتاه", body="یک دو سه").reading_minutes, 1)
        self.assertEqual(make_post("بلند", body="کلمه " * 450).reading_minutes, 3)


class ArticleBodyFormatterTests(TestCase):

    def test_structure(self):
        html = article_body("## تیتر\n\nپاراگراف یک\nخط دوم\n\n- آیتم اول\n- آیتم دوم")
        self.assertIn(">تیتر</h2>", html)
        self.assertIn("پاراگراف یک<br>خط دوم", html)
        self.assertEqual(html.count("<li "), 2)

    def test_html_is_escaped(self):
        html = article_body('<script>alert(1)</script>\n\n## <img src=x onerror=alert(1)>')
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;script&gt;", html)

    def test_empty(self):
        self.assertEqual(article_body(""), "")


class AdminTests(TestCase):

    def test_author_defaults_to_current_user_and_publish_action(self):
        admin_user = get_user_model().objects.create_superuser("admin", "a@a.com", "x")
        self.client.force_login(admin_user)
        response = self.client.post(reverse("admin:blog_post_add"), {
            "title": "از ادمین", "slug": "from-admin", "summary": "خلاصه", "body": "متن",
            "status": "draft", "published_at_0": "1405-08-01", "published_at_1": "10:00:00",
        })
        self.assertEqual(response.status_code, 302, response.content[:2000])
        post = Post.objects.get(slug="from-admin")
        self.assertEqual(post.author, admin_user)

        self.client.post(reverse("admin:blog_post_changelist"), {"action": "publish", "_selected_action": [post.pk]})
        post.refresh_from_db()
        self.assertEqual(post.status, Post.STATUS_PUBLISHED)
