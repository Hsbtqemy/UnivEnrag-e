"""Vue de programmation : ouverte aux participants, confirmation réservée (CDC §3, AGE-3)."""

import json

import pytest
from django.test import Client
from django.urls import reverse

from apps.actors.resolvers import NAME_COOKIE
from apps.actors.services import get_or_create_for_name
from apps.agenda.models import Event
from apps.core.dates import to_wall_clock
from apps.ideas import services as ideas_services
from conftest import login_verified

pytestmark = pytest.mark.django_db


def post(client, url, payload):
    return client.post(url, json.dumps(payload), content_type="application/json")


@pytest.fixture
def placed(make_idea, at, room, admin_user):
    idea = make_idea(slots=[{"start": at(1, 10)}, {"start": at(3, 14)}], room=room)
    ideas_services.accept(idea, user=admin_user)
    return idea.events.get()


@pytest.fixture
def named(member_client):
    member_client.cookies[NAME_COOKIE] = "Paul"
    return member_client


@pytest.mark.parametrize("name", ["agenda:programming", "agenda:programming_events"])
def test_programming_requires_access_code(client, site, name):
    assert client.get(reverse(name)).status_code == 302


def test_members_open_programming_without_confirm_controls(member_client, placed):
    body = member_client.get(reverse("agenda:programming")).content.decode()
    assert "À placer" in body
    assert "Confirmer la sélection" not in body
    assert "indiquez d'abord votre nom" in body


def test_managers_see_confirm_controls(admin_client):
    body = admin_client.get(reverse("agenda:programming")).content.decode()
    assert "Confirmer la sélection" in body


def test_events_feed_includes_alternatives_for_provisional(member_client, placed, at):
    data = member_client.get(reverse("agenda:programming_events")).json()
    kinds = sorted(item["extendedProps"]["kind"] for item in data)
    assert kinds == ["alternative", "event"]
    alternative = next(i for i in data if i["extendedProps"]["kind"] == "alternative")
    assert alternative["start"] == to_wall_clock(at(3, 14))


def test_owner_email_is_kept_for_managers(member_client, admin_user, placed):
    """CLAUDE.md PUB-2 : l'e-mail du porteur extérieur ne sort pas de la gestion."""
    member_data = member_client.get(reverse("agenda:programming_events")).json()
    assert "camille.martin@univ.example" not in json.dumps(member_data)
    admin_client = login_verified(Client(), admin_user)  # un autre navigateur
    admin_data = admin_client.get(reverse("agenda:programming_events")).json()
    assert admin_data[0]["extendedProps"]["ownerEmail"] == "camille.martin@univ.example"


def test_events_are_read_only_without_a_name(member_client, named, placed):
    data = named.get(reverse("agenda:programming_events")).json()
    assert next(i for i in data if i["id"] == str(placed.pk))["editable"] is True
    named.cookies[NAME_COOKIE] = ""
    data = named.get(reverse("agenda:programming_events")).json()
    assert next(i for i in data if i["id"] == str(placed.pk))["editable"] is False


def test_member_moves_to_other_room_and_free_place(named, placed, other_room, at):
    url = reverse("agenda:move", args=[placed.pk])
    payload = {"start": to_wall_clock(at(2, 9)), "end": to_wall_clock(at(2, 11)), "revision": 1}
    response = post(named, url, payload | {"room": str(other_room.pk)})
    assert response.json()["ok"] is True
    placed.refresh_from_db()
    assert placed.room == other_room
    assert placed.changes.first().actor.display_name == "Paul"
    response = post(named, url, payload | {"room": "lieu-libre", "revision": 2})
    placed.refresh_from_db()
    assert (placed.start, placed.room) == (at(2, 9), None)


def test_move_without_room_keeps_room(named, placed, room, at):
    payload = {"start": to_wall_clock(at(2, 9)), "end": to_wall_clock(at(2, 11)), "revision": 1}
    post(named, reverse("agenda:move", args=[placed.pk]), payload)
    placed.refresh_from_db()
    assert (placed.start, placed.room) == (at(2, 9), room)


def test_move_with_stale_revision_returns_409(named, placed, at):
    response = post(
        named,
        reverse("agenda:move", args=[placed.pk]),
        {"start": to_wall_clock(at(2, 9)), "end": to_wall_clock(at(2, 11)), "revision": 99},
    )
    assert response.status_code == 409


def test_member_places_unplaced_idea_with_duration(named, make_idea, room, admin_user, at):
    idea = make_idea(slots=[{"period_text": "Un midi"}], minutes=90)
    ideas_services.accept(idea, user=admin_user)
    response = post(
        named,
        reverse("agenda:place_idea", args=[idea.pk]),
        {"start": to_wall_clock(at(2, 12)), "room": str(room.pk)},
    )
    assert response.json()["ok"] is True
    event = Event.objects.get(idea=idea)
    assert (event.start, event.end, event.room) == (at(2, 12), at(2, 13, 30), room)
    assert event.status == Event.Status.PROVISIONAL
    assert event.changes.get().actor == get_or_create_for_name("Paul")


def test_placing_needs_a_name(member_client, make_idea, admin_user, at):
    idea = make_idea(slots=[{"period_text": "Un midi"}])
    ideas_services.accept(idea, user=admin_user)
    response = post(
        member_client,
        reverse("agenda:place_idea", args=[idea.pk]),
        {"start": to_wall_clock(at(2, 12))},
    )
    assert response.status_code == 400
    assert not Event.objects.exists()


def test_pending_proposal_cannot_be_placed(named, make_idea, at):
    idea = make_idea(slots=[{"period_text": "Un midi"}])
    response = post(
        named, reverse("agenda:place_idea", args=[idea.pk]), {"start": to_wall_clock(at(2, 12))}
    )
    assert response.status_code == 404


def test_member_cannot_confirm_or_publish(named, placed):
    response = post(named, reverse("agenda:gestion_confirm"), {"ids": [placed.pk]})
    assert response.status_code == 302  # vers la connexion de gestion
    response = post(named, reverse("agenda:gestion_public", args=[placed.pk]), {"isPublic": False})
    assert response.status_code == 403
    placed.refresh_from_db()
    assert (placed.status, placed.is_public) == (Event.Status.PROVISIONAL, True)


def test_batch_confirm_reports_conflicts(admin_client, make_idea, room, admin_user, at):
    events = []
    for title in ("Premier", "Second"):
        idea = make_idea(title=title, slots=[{"start": at(1, 10)}], room=room)
        ideas_services.accept(idea, user=admin_user)
        events.append(idea.events.get())
    response = post(
        admin_client, reverse("agenda:gestion_confirm"), {"ids": [e.pk for e in events]}
    )
    data = response.json()
    assert len(data["confirmed"]) == 1
    assert len(data["refused"]) == 1
    assert "déjà occupée" in data["refused"][0]["error"]


def test_alternative_is_sent_even_when_event_is_on_another_day(member_client, placed, at):
    """Vue jour du jeudi : l'atelier est placé mardi, son autre créneau (jeudi) s'affiche."""
    thursday = {"start": to_wall_clock(at(3, 0)), "end": to_wall_clock(at(4, 0))}
    data = member_client.get(reverse("agenda:programming_events"), thursday).json()
    assert [i["extendedProps"]["kind"] for i in data] == ["alternative"]
    assert data[0]["extendedProps"]["eventId"] == placed.pk
