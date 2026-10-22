"""Nom mémorisé par le navigateur et résolution de `request.actor` (CLAUDE.md ACC-2)."""

from urllib.parse import unquote

import pytest
from django.test import RequestFactory
from django.urls import reverse

from apps.actors.resolvers import NAME_COOKIE, NameCookieResolver
from apps.actors.services import get_or_create_for_name
from apps.polls import services as polls_services

pytestmark = pytest.mark.django_db


def test_name_page_remembers_name(member_client):
    response = member_client.post(reverse("actors:name"), {"author_name": "Marie-Hélène"})
    assert response.status_code == 302
    assert unquote(member_client.cookies[NAME_COOKIE].value) == "Marie-Hélène"
    page = member_client.get("/accueil/").content.decode()
    assert "Bonjour Marie-Hélène" in page


def test_name_page_can_forget(member_client):
    member_client.post(reverse("actors:name"), {"author_name": "Marie"})
    member_client.post(reverse("actors:name"), {"forget": "1", "author_name": ""})
    assert member_client.cookies[NAME_COOKIE].value == ""


def test_blank_name_is_refused(member_client):
    response = member_client.post(reverse("actors:name"), {"author_name": " -- "})
    assert response.status_code == 200
    assert NAME_COOKIE not in member_client.cookies or not member_client.cookies[NAME_COOKIE].value


def test_name_page_is_internal(client, site):
    assert client.get(reverse("actors:name")).status_code == 302


def test_resolver_reads_cookie_without_creating_actor(db):
    request = RequestFactory().get("/")
    request.COOKIES[NAME_COOKIE] = "Inconnu"
    assert NameCookieResolver().resolve(request) is None
    actor = get_or_create_for_name("Connu")
    request.COOKIES[NAME_COOKIE] = "connu"
    assert NameCookieResolver().resolve(request) == actor


def test_resolver_prefers_manager_actor(db, admin_user):
    actor = get_or_create_for_name("Administratrice")
    actor.user = admin_user
    actor.save()
    request = RequestFactory().get("/")
    request.user = admin_user
    request.COOKIES[NAME_COOKIE] = "Quelqu'un d'autre"
    assert NameCookieResolver().resolve(request) == actor


@pytest.mark.parametrize("url", ["/presences/ma-semaine/", "/sondages/", "/agenda/nouveau/"])
def test_pages_work_without_a_name(member_client, url):
    """Sans nom retenu, `request.actor` vaut None : les pages s'affichent quand même."""
    assert member_client.get(url).status_code == 200


def test_poll_page_works_without_a_name(member_client, at):
    poll = polls_services.create(
        actor=get_or_create_for_name("Marie"),
        title="Réunion",
        slots=[(at(1, 10), at(1, 11)), (at(2, 10), at(2, 11))],
    )
    assert member_client.get(f"/sondages/{poll.pk}/").status_code == 200
