"""Page publique des actualités : à la une, cartes par mois, pages, article (CDC §7)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.public.models import NewsPost
from apps.public.views import NEWS_PER_PAGE

pytestmark = pytest.mark.django_db


def make(title, days_ago=0, **fields):
    fields.setdefault("body", "Un texte.")
    fields.setdefault("is_published", True)
    return NewsPost.objects.create(
        title=title,
        slug=slugify(title),
        published_at=timezone.now() - timedelta(days=days_ago),
        **fields,
    )


def test_excerpt_is_plain_text_with_list_items_kept_apart():
    post = make("Liste", body="Ordre du jour :\n\n- **bilan** & suite\n- projets")
    assert post.excerpt == "Ordre du jour : bilan & suite · projets"


def test_latest_is_featured_then_cards_by_month(client, site):
    make("Récente", 1)
    make("Ancienne", 40)
    page = client.get(reverse("public:news_list"))
    assert page.context["featured"].title == "Récente"
    months = page.context["months"]
    assert [post.title for _, posts in months for post in posts] == ["Ancienne"]
    assert "Nouveau" in page.content.decode()  # moins d'une semaine


def test_unpublished_or_future_news_never_listed(client, site):
    make("Brouillon", is_published=False)
    make("Demain", days_ago=-1)
    body = client.get(reverse("public:news_list")).content.decode()
    assert "Brouillon" not in body and "Demain" not in body


def test_pagination(client, site):
    for i in range(NEWS_PER_PAGE + 2):
        make(f"Actu {i}", i * 3)
    first = client.get(reverse("public:news_list"))
    assert first.context["page"].has_next()
    second = client.get(reverse("public:news_list") + "?page=2")
    assert second.context["featured"] is None
    assert len([p for _, posts in second.context["months"] for p in posts]) == 2


def test_article_links_to_newer_and_older(client, site):
    old, middle, new = make("Vieille", 30), make("Milieu", 20), make("Neuve", 10)
    make("Brouillon", 15, is_published=False)
    page = client.get(reverse("public:news_detail", args=[middle.slug]))
    assert (page.context["newer"], page.context["older"]) == (new, old)
