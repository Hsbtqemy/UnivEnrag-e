"""Étanchéité du public : rien de non confirmé ou non public, jamais l'e-mail du porteur.

CLAUDE.md PUB-1 et PUB-2.
"""

import pytest
from django.urls import reverse

from apps.agenda import services
from apps.ideas import services as ideas_services

pytestmark = pytest.mark.django_db

EMAIL = "porteur.secret@univ.example"


@pytest.fixture
def events(make_idea, at, room, admin_user):
    def placed(title, day, confirm=False, public=True):
        idea = make_idea(
            title=title,
            name=f"Porteur {title}",
            email=EMAIL,
            slots=[{"start": at(day, 10)}],
            room=room,
        )
        ideas_services.accept(idea, user=admin_user)
        event = idea.event
        if not public:
            event = services.set_public(event, is_public=False)
        if confirm:
            event = services.confirm(event, user=admin_user)
        return event

    return {
        "visible": placed("Visible", 1, confirm=True),
        "provisional": placed("Provisoire", 2),
        "private": placed("Privé", 3, confirm=True, public=False),
    }


PUBLIC_PAGES = ["agenda:public_list", "agenda:public_events_json", "agenda:public_ics"]


@pytest.mark.parametrize("name", PUBLIC_PAGES)
def test_only_confirmed_public_events_are_published(client, events, name):
    body = client.get(reverse(name)).content.decode()
    assert "Visible" in body
    assert "Provisoire" not in body
    assert "Privé" not in body


@pytest.mark.parametrize("name", PUBLIC_PAGES)
def test_owner_name_is_public_but_email_never(client, events, name):
    body = client.get(reverse(name)).content.decode()
    assert "Porteur Visible" in body
    assert EMAIL not in body


def test_detail_page_shows_owner_without_email(client, events):
    body = client.get(reverse("agenda:public_detail", args=[events["visible"].pk])).content.decode()
    assert "Porteur Visible" in body
    assert EMAIL not in body


@pytest.mark.parametrize("key", ["provisional", "private"])
def test_detail_page_of_unpublished_event_is_404(client, events, key):
    response = client.get(reverse("agenda:public_detail", args=[events[key].pk]))
    assert response.status_code == 404


def test_public_pages_load_no_external_resource(client, events):
    response = client.get(reverse("agenda:public_week"))
    assert "default-src 'self'" in response["Content-Security-Policy"]
    body = response.content.decode()
    assert "http://" not in body.replace("http://testserver", "")
    assert "https://" not in body


def test_ics_is_valid_calendar(client, events):
    from icalendar import Calendar

    calendar = Calendar.from_ical(client.get(reverse("agenda:public_ics")).content)
    summaries = [str(c["summary"]) for c in calendar.walk("VEVENT")]
    assert summaries == ["Visible"]
