"""API de la vue de programmation (réservée aux admins)."""

import json

import pytest
from django.urls import reverse

from apps.agenda.models import Event
from apps.core.dates import to_wall_clock
from apps.ideas import services as ideas_services

pytestmark = pytest.mark.django_db


def post(client, url, payload):
    return client.post(url, json.dumps(payload), content_type="application/json")


@pytest.fixture
def placed(make_idea, at, room, admin_user):
    idea = make_idea(slots=[{"start": at(1, 10)}, {"start": at(3, 14)}], room=room)
    ideas_services.accept(idea, user=admin_user)
    return idea.event


@pytest.mark.parametrize(
    "name,args",
    [
        ("agenda:programming", []),
        ("agenda:gestion_events", []),
    ],
)
def test_gestion_pages_require_staff(client, name, args):
    response = client.get(reverse(name, args=args))
    assert response.status_code == 302


def test_move_requires_staff(client, placed, at):
    response = post(
        client,
        reverse("agenda:gestion_move", args=[placed.pk]),
        {"start": to_wall_clock(at(2, 10)), "end": to_wall_clock(at(2, 12)), "revision": 1},
    )
    assert response.status_code == 302
    placed.refresh_from_db()
    assert placed.start == at(1, 10)


def test_events_feed_includes_alternatives_for_provisional(admin_client, placed, at):
    data = admin_client.get(reverse("agenda:gestion_events")).json()
    kinds = sorted(item["extendedProps"]["kind"] for item in data)
    assert kinds == ["alternative", "event"]
    alternative = next(i for i in data if i["extendedProps"]["kind"] == "alternative")
    assert alternative["start"] == to_wall_clock(at(3, 14))


def test_move_to_other_room_and_free_place(admin_client, placed, other_room, at):
    url = reverse("agenda:gestion_move", args=[placed.pk])
    response = post(
        admin_client,
        url,
        {
            "start": to_wall_clock(at(2, 9)),
            "end": to_wall_clock(at(2, 11)),
            "room": str(other_room.pk),
            "revision": 1,
        },
    )
    assert response.json()["ok"] is True
    response = post(
        admin_client,
        url,
        {
            "start": to_wall_clock(at(2, 9)),
            "end": to_wall_clock(at(2, 11)),
            "room": "lieu-libre",
            "revision": 2,
        },
    )
    placed.refresh_from_db()
    assert (placed.start, placed.room) == (at(2, 9), None)


def test_move_with_stale_revision_returns_409(admin_client, placed, at):
    response = post(
        admin_client,
        reverse("agenda:gestion_move", args=[placed.pk]),
        {"start": to_wall_clock(at(2, 9)), "end": to_wall_clock(at(2, 11)), "revision": 99},
    )
    assert response.status_code == 409


def test_place_unplaced_idea_with_duration(admin_client, make_idea, room, admin_user, at):
    idea = make_idea(slots=[{"period_text": "Un midi"}], minutes=90)
    ideas_services.accept(idea, user=admin_user)
    response = post(
        admin_client,
        reverse("agenda:gestion_place", args=[idea.pk]),
        {"start": to_wall_clock(at(2, 12)), "room": str(room.pk)},
    )
    assert response.json()["ok"] is True
    event = Event.objects.get(idea=idea)
    assert (event.start, event.end, event.room) == (at(2, 12), at(2, 13, 30), room)


def test_batch_confirm_reports_conflicts(admin_client, make_idea, room, admin_user, at):
    events = []
    for title in ("Premier", "Second"):
        idea = make_idea(title=title, slots=[{"start": at(1, 10)}], room=room)
        ideas_services.accept(idea, user=admin_user)
        events.append(idea.event)
    response = post(
        admin_client, reverse("agenda:gestion_confirm"), {"ids": [e.pk for e in events]}
    )
    data = response.json()
    assert len(data["confirmed"]) == 1
    assert len(data["refused"]) == 1
    assert "déjà occupée" in data["refused"][0]["error"]
