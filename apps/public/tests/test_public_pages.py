"""Page publique : présentation, actualités, contact (CDC §7, CLAUDE.md PUB-1)."""

import io
from datetime import timedelta

import pytest
from django.core import signing
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.core.antispam import SALT
from apps.core.markdown import render
from apps.public import services
from apps.public.models import ContactMessage, NewsPost
from conftest import login_verified

pytestmark = pytest.mark.django_db


def test_markdown_keeps_simple_formatting_and_strips_the_rest():
    html = render(
        "**gras** [lien](https://exemple.org)\n\n- un\n\n"
        "<script>alert(1)</script><img src=x onerror=alert(1)> [x](javascript:alert(1))"
    )
    assert "<strong>gras</strong>" in html
    assert '<a href="https://exemple.org" rel="nofollow noopener">lien</a>' in html
    assert "<li>un</li>" in html
    for forbidden in ("<script", "alert", "<img", "onerror", "javascript:"):
        assert forbidden not in html


def test_public_home_shows_presentation_and_only_published_news(client, site):
    site.presentation = "Nous sommes un **collectif**."
    site.save()
    NewsPost.objects.create(title="Publiée", slug="publiee", body="Texte", is_published=True)
    NewsPost.objects.create(title="Brouillon", slug="brouillon", body="Texte")
    NewsPost.objects.create(
        title="Programmée",
        slug="programmee",
        body="Texte",
        is_published=True,
        published_at=timezone.now() + timedelta(days=2),
    )
    body = client.get(reverse("public:home")).content.decode()
    assert "<strong>collectif</strong>" in body
    assert "Publiée" in body
    assert "Brouillon" not in body and "Programmée" not in body


def test_unpublished_news_is_404_and_absent_from_rss(client, site):
    NewsPost.objects.create(title="Brouillon", slug="brouillon", body="Secret")
    NewsPost.objects.create(title="Publiée", slug="publiee", body="Texte", is_published=True)
    assert client.get(reverse("public:news_detail", args=["brouillon"])).status_code == 404
    rss = client.get(reverse("public:news_feed")).content.decode()
    assert "Publiée" in rss and "Brouillon" not in rss


def form_data(**overrides):
    data = {
        "name": "Paul Henry",
        "email": "",
        "message": "Bonjour, comment vous rejoindre ?",
        "website": "",
        "rendered_at": signing.TimestampSigner(salt=SALT).sign("form"),
    }
    return data | overrides


def test_contact_without_email_is_kept(client, site, monkeypatch):
    monkeypatch.setattr("apps.core.antispam.AntiSpamFormMixin.is_spam", lambda self: False)
    response = client.post(reverse("public:contact"), form_data())
    assert response.status_code == 302
    message = ContactMessage.objects.get()
    assert (message.sender.display_name, message.email) == ("Paul Henry", "")


def test_contact_spam_is_dropped_silently(client, site):
    response = client.post(reverse("public:contact"), form_data(website="http://spam.example"))
    assert response.status_code == 302
    assert not ContactMessage.objects.exists()


def test_contact_rate_limit(client, site, settings, monkeypatch):
    monkeypatch.setattr("apps.core.antispam.AntiSpamFormMixin.is_spam", lambda self: False)
    settings.CONTACT_RATE_LIMIT = (2, 3600)
    for _ in range(2):
        client.post(reverse("public:contact"), form_data())
    assert client.post(reverse("public:contact"), form_data()).status_code == 429
    assert ContactMessage.objects.count() == 2


def test_contact_email_never_appears_publicly(client, site, admin_user):
    services.submit_contact(name="Paul", email="paul@exemple.org", message="Bonjour")
    for name in ("public:home", "public:news_list", "agenda:public_list"):
        assert "paul@exemple.org" not in client.get(reverse(name)).content.decode()
    admin = login_verified(Client(), admin_user)
    changelist = admin.get(reverse("admin:public_contactmessage_changelist")).content.decode()
    assert "mailto:paul@exemple.org" in changelist


def test_presentation_needs_the_public_page_right(client, site, make_manager):
    manager = login_verified(client, make_manager("manage_agenda"))
    assert manager.get(reverse("public:presentation")).status_code == 403
    other = login_verified(Client(), make_manager("manage_public", username="publication"))
    other.post(reverse("public:presentation"), {"presentation": "Texte", "apercu": "1"})
    site.refresh_from_db()
    assert site.presentation == ""  # l'aperçu n'enregistre rien
    other.post(reverse("public:presentation"), {"presentation": "Nouveau texte"})
    site.refresh_from_db()
    assert site.presentation == "Nouveau texte"
    assert AuditLog.objects.filter(action="public.presentation_changed").exists()


def test_news_admin_is_for_the_public_page_right(client, make_manager):
    login_verified(client, make_manager("manage_agenda"))
    assert client.get(reverse("admin:public_newspost_changelist")).status_code == 403


def test_contact_messages_are_purged_after_a_year(db):
    old = services.submit_contact(name="Ancien", email="", message="…")
    ContactMessage.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=400))
    services.submit_contact(name="Récent", email="", message="…")
    call_command("purge_contact_messages", stdout=io.StringIO())
    assert list(ContactMessage.objects.values_list("sender__display_name", flat=True)) == ["Récent"]


def test_visitors_and_members_have_their_own_navigation(client, member_client):
    visitor = Client().get(reverse("public:home")).content.decode()
    assert "Actualités" in visitor and "Espace membres" in visitor
    member = member_client.get(reverse("agenda:home")).content.decode()
    assert "Site public" in member and "Espace membres" not in member
