"""Permanences ouvertes au public : jour, moment et lieu, jamais de nom (PUB-1, décision 23)."""

from datetime import date, time, timedelta

import pytest
from django.urls import reverse

from apps.actors.resolvers import NAME_COOKIE
from apps.actors.services import get_or_create_for_name
from apps.presences import services
from apps.presences.models import Presence

pytestmark = pytest.mark.django_db

# La semaine prochaine : toujours à venir, et dans les 14 jours affichés au public.
MONDAY = services.week_start(date.today()) + timedelta(days=7)


def test_presence_is_private_by_default():
    marie = get_or_create_for_name("Marie Curie")
    services.save_week(marie, MONDAY, {(MONDAY, "morning"): "Bât. A"})
    assert not Presence.objects.public().exists()


def test_open_day_becomes_public_permanence():
    marie = get_or_create_for_name("Marie Curie")
    tuesday = MONDAY + timedelta(days=1)
    services.save_week(
        marie,
        MONDAY,
        {(tuesday, "afternoon"): "Local du collectif", (MONDAY, "morning"): "Bât. A"},
        open_days={tuesday},
    )
    days = services.public_permanences()
    assert [(d.day, d.slots) for d in days] == [(tuesday, [("Après-midi", ["Local du collectif"])])]


def test_permanence_without_place_or_hours_shows_the_moment():
    marie = get_or_create_for_name("Marie Curie")
    services.save_week(marie, MONDAY, {(MONDAY, "morning"): ""}, open_days={MONDAY})
    assert services.public_permanences()[0].slots == [("Matin", [])]


def test_permanence_with_hours():
    marie = get_or_create_for_name("Marie Curie")
    services.save_week(
        marie,
        MONDAY,
        {(MONDAY, "afternoon"): services.Declared("Local", time(14), time(17))},
        open_days={MONDAY},
    )
    assert services.public_permanences()[0].slots == [("Après-midi", ["14:00 – 17:00, Local"])]


def test_end_must_follow_start():
    marie = get_or_create_for_name("Marie Curie")
    with pytest.raises(services.PresenceError):
        services.save_week(
            marie, MONDAY, {(MONDAY, "afternoon"): services.Declared("", time(17), time(14))}
        )
    assert not Presence.objects.exists()


def test_two_people_same_place_show_once_without_names():
    for name in ("Marie Curie", "Paul Langevin"):
        services.save_week(
            get_or_create_for_name(name),
            MONDAY,
            {(MONDAY, "morning"): "Bât. A"},
            open_days={MONDAY},
        )
    assert services.public_permanences()[0].slots == [("Matin", ["Bât. A"])]


def test_past_permanences_are_not_public():
    marie = get_or_create_for_name("Marie Curie")
    last_week = MONDAY - timedelta(days=14)
    services.save_week(marie, last_week, {(last_week, "morning"): "Bât. A"}, open_days={last_week})
    assert services.public_permanences() == []


def test_public_home_shows_place_but_never_the_name(client):
    marie = get_or_create_for_name("Marie Curie")
    services.save_week(marie, MONDAY, {(MONDAY, "evening"): "Bât. C"}, open_days={MONDAY})
    body = client.get(reverse("public:home")).content.decode()
    assert "Où nous trouver" in body
    assert "Bât. C" in body
    assert "Marie Curie" not in body


def test_member_marks_a_day_as_permanence(member_client):
    member_client.cookies[NAME_COOKIE] = "Marie Curie"
    day = MONDAY.isoformat()
    member_client.post(
        reverse("presences:my_week"),
        {
            "semaine": day,
            f"p-{day}-morning": "on",
            f"lieu-{day}": "Bât. A",
            f"ouvert-{day}": "on",
            "author_name": "Marie Curie",
        },
    )
    assert Presence.objects.get().is_open is True
    board = member_client.get(f"{reverse('presences:board')}?semaine={day}").content.decode()
    assert "permanence" in board


def test_member_form_saves_hours_without_place(member_client):
    day = MONDAY.isoformat()
    member_client.post(
        reverse("presences:my_week"),
        {
            "semaine": day,
            f"p-{day}-afternoon": "on",
            f"de-{day}-afternoon": "14:00",
            f"a-{day}-afternoon": "17:30",
            f"ouvert-{day}": "on",
            "author_name": "Marie Curie",
        },
    )
    presence = Presence.objects.get()
    assert (presence.start_time, presence.end_time, presence.place) == (time(14), time(17, 30), "")
    page = member_client.get(f"{reverse('presences:my_week')}?semaine={day}").content.decode()
    assert 'value="14:00"' in page


def test_member_form_refuses_end_before_start(member_client):
    day = MONDAY.isoformat()
    response = member_client.post(
        reverse("presences:my_week"),
        {
            "semaine": day,
            f"p-{day}-morning": "on",
            f"de-{day}-morning": "11:00",
            f"a-{day}-morning": "09:00",
            "author_name": "Marie Curie",
        },
    )
    assert response.status_code == 200
    assert "heure de fin" in response.content.decode()
    assert not Presence.objects.exists()
