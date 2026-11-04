"""Actualités écrites depuis le site, sans l'administration Django (CDC §7 : par les
admins, droit « page publique »)."""

from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.public.models import NewsPost
from conftest import login_verified

pytestmark = pytest.mark.django_db


@pytest.fixture
def editor(client, make_manager):
    return login_verified(client, make_manager("manage_public", username="redaction"))


def post_data(**overrides):
    data = {"title": "Rentrée du collectif", "summary": "", "body": "Un **beau** texte."}
    data.update(overrides)
    return data


@pytest.mark.parametrize("name", ["public:news_manage", "public:news_new"])
def test_reserved_to_the_public_page_right(client, member_client, make_manager, name):
    url = reverse(name)
    assert member_client.get(url).status_code == 302  # membre sans compte : connexion
    other = Client()
    login_verified(other, make_manager("manage_agenda", username="agenda"))
    assert other.get(url).status_code == 403


def test_draft_then_publish_from_the_list(editor, site):
    editor.post(reverse("public:news_new"), post_data())
    post = NewsPost.objects.get()
    assert not post.is_published and post.slug == "rentree-du-collectif"
    assert "Rentrée du collectif" not in Client().get(reverse("public:news_list")).content.decode()
    editor.post(reverse("public:news_publish", args=[post.pk]), {"publier": "1"})
    page = Client().get(reverse("public:news_detail", args=[post.slug])).content.decode()
    assert "<strong>beau</strong>" in page
    assert AuditLog.objects.filter(action="public.news_published").exists()
    editor.post(reverse("public:news_publish", args=[post.pk]), {"publier": "0"})
    assert Client().get(reverse("public:news_detail", args=[post.slug])).status_code == 404
    assert NewsPost.objects.count() == 1  # dépubliée, jamais supprimée


def test_preview_saves_nothing(editor):
    response = editor.post(reverse("public:news_new"), post_data(apercu="1"))
    assert "<strong>beau</strong>" in response.content.decode()
    assert not NewsPost.objects.exists()


def test_future_date_waits_for_its_day(editor, site):
    later = timezone.localtime() + timedelta(days=3)
    editor.post(
        reverse("public:news_new"),
        post_data(is_published="on", published_at=later.strftime("%Y-%m-%dT%H:%M")),
    )
    post = NewsPost.objects.get()
    assert post.is_published and post not in NewsPost.objects.public()
    assert "Programmée" in editor.get(reverse("public:news_manage")).content.decode()


def test_editing_keeps_the_address_and_is_logged(editor, site):
    editor.post(reverse("public:news_new"), post_data(is_published="on"))
    post = NewsPost.objects.get()
    editor.post(
        reverse("public:news_edit", args=[post.pk]),
        post_data(title="Un autre titre", is_published="on"),
    )
    post.refresh_from_db()
    assert (post.title, post.slug) == ("Un autre titre", "rentree-du-collectif")
    assert AuditLog.objects.filter(action="public.news_updated").exists()


def test_same_title_gets_a_distinct_address(editor):
    editor.post(reverse("public:news_new"), post_data())
    editor.post(reverse("public:news_new"), post_data())
    assert sorted(NewsPost.objects.values_list("slug", flat=True)) == [
        "rentree-du-collectif",
        "rentree-du-collectif-2",
    ]


def test_management_home_links_to_the_new_page(editor):
    html = editor.get(reverse("accounts:gestion_home")).content.decode()
    assert reverse("public:news_manage") in html
