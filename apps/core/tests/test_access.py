"""Code d'accès commun (CLAUDE.md ACC-1) et non-indexation de la partie interne."""

import io
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.core.models import RateLimitHit, SiteSettings
from conftest import ACCESS_CODE, login_verified

pytestmark = pytest.mark.django_db

INTERNAL = "/accueil/"


def test_internal_page_requires_code(client, site):
    response = client.get(INTERNAL)
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("core:access"))
    assert "next=%2Faccueil%2F" in response["Location"]


def test_right_code_opens_internal_part_and_redirects_to_next(client, site):
    response = client.post(
        reverse("core:access") + "?next=/accueil/", {"code": ACCESS_CODE, "next": "/accueil/"}
    )
    assert response.status_code == 302
    assert response["Location"] == "/accueil/"
    assert client.get(INTERNAL).status_code == 200


def test_next_cannot_leave_the_site(client, site):
    response = client.post(
        reverse("core:access"), {"code": ACCESS_CODE, "next": "https://ailleurs.example/"}
    )
    assert response["Location"] == "/accueil/"


def test_wrong_code_is_refused(client, site):
    response = client.post(reverse("core:access"), {"code": "mauvais"})
    assert response.status_code == 200
    assert "pas le bon" in response.content.decode()
    assert client.get(INTERNAL).status_code == 302


def test_ten_failures_block_further_attempts(client, site):
    for _ in range(10):
        client.post(reverse("core:access"), {"code": "mauvais"})
    response = client.post(reverse("core:access"), {"code": ACCESS_CODE})
    assert response.status_code == 429


def test_changing_the_code_invalidates_every_browser(member_client, site):
    assert member_client.get(INTERNAL).status_code == 200
    SiteSettings.get().set_access_code("nouveau-code")
    assert member_client.get(INTERNAL).status_code == 302


def test_no_code_defined_keeps_internal_part_closed(client, db):
    response = client.post(reverse("core:access"), {"code": ""})
    assert client.get(INTERNAL).status_code == 302
    assert "Aucun code" in client.get(reverse("core:access")).content.decode()
    assert response.status_code == 200


def test_cookie_does_not_contain_the_code(member_client):
    assert ACCESS_CODE not in member_client.cookies["acces"].value


@pytest.mark.parametrize("name", ["agenda:public_list", "agenda:public_ics", "ideas:propose"])
def test_public_pages_need_no_code(client, site, name):
    assert client.get(reverse(name)).status_code == 200


def test_root_sends_visitors_to_public_agenda_and_members_home(client, member_client):
    assert client.get("/")["Location"] == "/accueil/"  # member_client partage `client`


def test_root_for_visitor(client, site):
    assert client.get("/")["Location"] == "/p/"


def test_logged_in_manager_needs_no_code(client, site, admin_user):
    login_verified(client, admin_user)
    assert client.get(INTERNAL).status_code == 200


def test_internal_pages_are_not_indexed(member_client):
    assert member_client.get(INTERNAL)["X-Robots-Tag"] == "noindex, nofollow"


def test_public_agenda_is_indexable(client, site):
    assert "X-Robots-Tag" not in client.get(reverse("agenda:public_list"))


def test_robots_txt_only_allows_public_part(client, db):
    body = client.get("/robots.txt").content.decode()
    assert "Allow: /p/" in body
    assert "Disallow: /\n" in body
    assert "Disallow: /p/suivi/" in body


def test_health_is_public_and_checks_the_database(client, db):
    response = client.get("/sante/")
    assert (response.status_code, response.content) == (200, b"ok\n")
    assert "no-cache" in response["Cache-Control"]


def test_privacy_page_is_public_and_shows_contact(client, site):
    site.privacy_contact = "donnees@collectif.example"
    site.save()
    body = client.get("/p/donnees-personnelles/").content.decode()
    assert "donnees@collectif.example" in body
    assert "60 jours" in body


def test_purge_ip_data_command(db):
    old = RateLimitHit.objects.create(bucket="access_code", key_hash="x")
    RateLimitHit.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=31))
    RateLimitHit.objects.create(bucket="access_code", key_hash="y")
    call_command("purge_ip_data", stdout=io.StringIO())
    assert list(RateLimitHit.objects.values_list("key_hash", flat=True)) == ["y"]


@pytest.mark.parametrize("url", ["/sante/", "/p/", "/p/agenda/", "/p/agenda.ics", "/robots.txt"])
def test_head_requests_are_answered(client, site, url):
    """Les sondes de disponibilité et les aperçus de liens utilisent HEAD : pas de 405."""
    assert client.head(url).status_code == 200
