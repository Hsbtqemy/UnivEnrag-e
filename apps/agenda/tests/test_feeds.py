"""Abonnements iCal internes (par jeton) et flux public."""

import pytest
from django.urls import reverse
from icalendar import Calendar

from apps.actors.services import get_or_create_for_name
from apps.agenda import services
from apps.core.models import SiteSettings
from apps.ideas import services as ideas_services
from apps.spaces.models import Space

pytestmark = pytest.mark.django_db


@pytest.fixture
def token(site):
    return SiteSettings.get().feeds_token


@pytest.fixture
def data(at, room, other_room, make_idea, admin_user):
    marie = get_or_create_for_name("Marie")
    space = Space.objects.create(name="Séminaire")
    confirmed = services.create(
        actor=marie,
        title="Confirmé",
        start=at(1, 10),
        end=at(1, 11),
        room=room,
        space=space,
        visio_link="https://visio.example/salon",
    )
    cancelled = services.create(
        actor=marie, title="Annulé", start=at(2, 10), end=at(2, 11), room=other_room
    )
    services.cancel(cancelled, actor=marie, revision=cancelled.revision)
    idea = make_idea(
        title="Provisoire", slots=[{"start": at(3, 10)}], room=room, email="secret@univ.example"
    )
    ideas_services.accept(idea, user=admin_user)
    return {"space": space, "confirmed": confirmed}


def statuses(response):
    calendar = Calendar.from_ical(response.content)
    return {str(c["summary"]): str(c["status"]) for c in calendar.walk("VEVENT")}


def test_wrong_token_is_404(client, data, token):
    assert client.get(reverse("agenda:feed_all", args=["mauvais"])).status_code == 404


def test_member_feed_needs_no_cookie_and_has_all_statuses(client, data, token):
    response = client.get(reverse("agenda:feed_all", args=[token]))
    assert response.status_code == 200
    assert statuses(response) == {
        "Confirmé": "CONFIRMED",
        "Annulé": "CANCELLED",
        "Provisoire": "TENTATIVE",
    }
    assert b"secret@univ.example" not in response.content
    assert response["X-Robots-Tag"] == "noindex, nofollow"


def test_space_and_room_feeds_are_filtered(client, data, token, room):
    by_space = client.get(reverse("agenda:feed_space", args=[token, data["space"].slug]))
    assert set(statuses(by_space)) == {"Confirmé"}
    by_room = client.get(reverse("agenda:feed_room", args=[token, room.pk]))
    assert set(statuses(by_room)) == {"Confirmé", "Provisoire"}


def test_regenerating_token_cuts_old_subscriptions(client, data, token):
    SiteSettings.get().regenerate_feeds_token()
    assert client.get(reverse("agenda:feed_all", args=[token])).status_code == 404


def test_visio_link_only_in_member_feed(client, data, token, admin_user):
    services.set_public(data["confirmed"], is_public=True, user=admin_user)
    assert b"visio.example" in client.get(reverse("agenda:feed_all", args=[token])).content
    assert b"visio.example" not in client.get(reverse("agenda:public_ics")).content


def test_subscriptions_page_lists_feeds(member_client, data, token):
    page = member_client.get(reverse("agenda:subscriptions")).content.decode()
    assert f"webcal://testserver/flux/{token}/agenda.ics" in page
    assert f"/flux/{token}/espace/{data['space'].slug}.ics" in page
