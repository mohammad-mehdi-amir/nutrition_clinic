from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .models import Post, PostCategory


def _sidebar():
    published = Post.objects.published()
    return {
        "sidebar_categories": PostCategory.objects.filter(is_active=True).annotate(
            post_count=Count("posts", filter=Q(posts__in=published))
        ).filter(post_count__gt=0),
        "latest_posts": published.select_related("category")[:3],
    }


def post_list(request, slug=None):
    posts = Post.objects.published().select_related("category", "author")
    category = None

    if slug:
        category = get_object_or_404(PostCategory, slug=slug, is_active=True)
        posts = posts.filter(category=category)

    query = request.GET.get("q", "").strip()
    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(summary__icontains=query) | Q(body__icontains=query))

    page = Paginator(posts, 6).get_page(request.GET.get("page"))

    return render(
        request,
        "blog/post_list.html",
        {"page_obj": page, "posts": page.object_list, "category": category, "query": query, **_sidebar()},
    )


def post_detail(request, slug):
    post = get_object_or_404(Post.objects.select_related("category", "author"), slug=slug)

    # پیش‌نویس و انتشار زمان‌بندی‌شده فقط برای کارکنان (پیش‌نمایش) قابل مشاهده است
    if not post.is_public and not request.user.is_staff:
        raise Http404

    related = Post.objects.published().exclude(pk=post.pk)
    if post.category_id:
        related = related.filter(category=post.category)

    return render(
        request,
        "blog/post_detail.html",
        {"post": post, "related_posts": related.select_related("category")[:3], **_sidebar()},
    )
