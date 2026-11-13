"""Statistiques de visite anonymes (décision 28) : on compte des pages, jamais des gens."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.actors.services import get_or_create_for_name
from apps.agenda import services as agenda_services
from apps.core.models import PageCount
from conftest import login_verified

pytestmark = pytest.mark.django_db

BROWSER = {"HTTP_USER_AGENT": "Mozilla/5.0 (X11; Linux x86_64) Firefox/140.0"}


def counts():
    return {(c.kind, c.key): c.count for c in PageCount.objects.all()}


def test_public_page_views_are_counted(client, site):
    client.get("/p/", **BROWSER)
    client.get("/p/", **BROWSER)
    client.get(reverse("agenda:public_list"), **BROWSER)
    assert counts() == {("public", "public:home"): 2, ("public", "agenda:public_list"): 1}
    assert PageCount.objects.get(key="public:home").day == timezone.localdate()


def test_nothing_about_the_person_is_stored(client, site):
    client.get(
        "/p/",
        HTTP_REFERER="https://www.instagram.com/collectif/?utm=secret",
        REMOTE_ADDR="203.0.113.7",
        **BROWSER,
    )
    stored = " ".join(f"{c.kind} {c.key} {c.count}" for c in PageCount.objects.all())
    assert "203.0.113.7" not in stored and "Firefox" not in stored and "secret" not in stored
    # De la provenance, seul le domaine reste.
    assert counts()[("source", "instagram.com")] == 1
    field_names = {f.name for f in PageCount._meta.get_fields()}
    assert field_names == {"id", "day", "kind", "key", "count"}


def test_internal_links_are_not_a_source(client, site):
    client.get("/p/", HTTP_REFERER="http://testserver/p/agenda/", **BROWSER)
    assert not PageCount.objects.filter(kind="source").exists()


@pytest.mark.parametrize(
    "agent", ["", "Googlebot/2.1", "curl/8.4", "Mozilla/5.0 (compatible; bingbot/2.0)"]
)
def test_robots_are_not_counted(client, site, agent):
    client.get("/p/", HTTP_USER_AGENT=agent)
    assert not PageCount.objects.exists()


def test_errors_redirects_and_prefetch_are_not_counted(client, site):
    client.get("/p/agenda/999999/", **BROWSER)  # 404
    client.get("/", **BROWSER)  # redirection vers /p/
    client.get("/p/", HTTP_SEC_PURPOSE="prefetch", **BROWSER)
    client.get("/sante/", **BROWSER)
    assert not PageCount.objects.exists()


def test_management_accounts_and_pages_are_not_counted(client, admin_user, site):
    login_verified(client, admin_user)
    client.get("/p/", **BROWSER)
    client.get(reverse("accounts:gestion_home"), **BROWSER)
    assert not PageCount.objects.exists()


def test_tokens_never_reach_the_counters(client, site, make_idea):
    """Le lien de suivi et les flux internes portent un jeton : on ne garde que le nom."""
    idea = make_idea()
    client.get(reverse("ideas:track", args=[idea.tracking_token]), **BROWSER)
    token = site.feeds_token
    client.get(reverse("agenda:feed_all", args=[token]), **BROWSER)
    assert counts() == {("public", "ideas:track"): 1, ("feed", "agenda:feed_all"): 1}
    assert str(idea.tracking_token) not in str(counts()) and token not in str(counts())


def test_public_detail_keeps_the_object(client, site, at, admin_user):
    event = agenda_services.create(
        actor=get_or_create_for_name("Inès"),
        user=admin_user,
        title="Ciné-débat",
        start=at(1, 18),
        end=at(1, 20),
    )
    agenda_services.set_public(event, is_public=True, user=admin_user)
    client.get(reverse("agenda:public_detail", args=[event.pk]), **BROWSER)
    assert counts() == {("public", f"agenda:public_detail:{event.pk}"): 1}


def test_board_counts_page_loads_not_refreshes(client, site):
    client.get(reverse("agenda:public_board"), **BROWSER)
    client.get(reverse("agenda:public_board") + "?fragment=1", **BROWSER)
    assert counts() == {("board", "agenda:public_board"): 1}


def test_member_pages_are_counted_apart(member_client):
    member_client.get(reverse("agenda:calendar"), **BROWSER)
    assert counts() == {("members", "agenda:calendar"): 1}


# --- Page « Statistiques de visite » --------------------------------------------------


def test_statistics_page(client, site, make_manager, at, admin_user):
    event = agenda_services.create(
        actor=get_or_create_for_name("Inès"),
        user=admin_user,
        title="Ciné-débat",
        start=at(1, 18),
        end=at(1, 20),
    )
    today = timezone.localdate()
    PageCount.objects.create(day=today, kind="public", key="public:home", count=12)
    PageCount.objects.create(
        day=today - timedelta(days=3),
        kind="public",
        key=f"agenda:public_detail:{event.pk}",
        count=5,
    )
    PageCount.objects.create(day=today, kind="source", key="instagram.com", count=4)
    two_months_ago = today - timedelta(days=60)
    PageCount.objects.create(day=two_months_ago, kind="public", key="public:home", count=99)
    login_verified(client, make_manager("manage_public"))
    page = client.get(reverse("public:statistics")).content.decode()
    assert "Page d&#x27;accueil" in page and "Événement « Ciné-débat »" in page
    assert "instagram.com" in page
    assert ">17<" in page  # 12 + 5 sur 30 jours, sans les 99 d'il y a deux mois
    year = client.get(reverse("public:statistics") + "?periode=365").content.decode()
    assert ">116<" in year


def test_statistics_need_public_page_right(client, site, make_manager, member_client):
    assert member_client.get(reverse("public:statistics")).status_code == 302
    login_verified(client, make_manager("manage_agenda"))
    assert client.get(reverse("public:statistics")).status_code == 403
