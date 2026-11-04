"""Couleur choisie pour un événement : palette fixe, historique, agenda et page publique."""

import json

import pytest
from django.urls import reverse

from apps.actors.services import get_or_create_for_name
from apps.agenda import history, services
from apps.agenda.models import Event
from apps.agenda.serializers import public_event
from apps.agenda.tests.test_member_views import form_data
from apps.spaces.models import Space

pytestmark = pytest.mark.django_db

RED = Event.Color.RED.value


@pytest.fixture
def marie(db):
    return get_or_create_for_name("Marie")


def test_color_is_chosen_in_the_form(member_client, at):
    member_client.post(reverse("agenda:new"), form_data(at, color=RED))
    assert Event.objects.get().color == RED


def test_color_outside_the_palette_is_refused(member_client, at):
    response = member_client.post(reverse("agenda:new"), form_data(at, color="#ffff00"))
    assert response.status_code == 200
    assert not Event.objects.exists()


def test_chosen_color_wins_over_space_and_room(marie, at, room):
    space = Space.objects.create(name="Cinéma", color="#123456")
    event = services.create(
        actor=marie, title="Projection", start=at(1, 18), end=at(1, 20), room=room, space=space
    )
    assert event.display_color == "#123456"  # automatique : l'espace d'abord
    assert event.public_color == room.color  # pas d'espace sur la page publique
    event.color = RED
    assert event.display_color == event.public_color == RED


def test_color_change_is_in_history_and_restorable(marie, at, admin_user):
    event = services.create(actor=marie, title="Atelier", start=at(1, 10), end=at(1, 12))
    created = event.changes.get()
    event = services.update(
        event,
        actor=marie,
        revision=event.revision,
        title="Atelier",
        start=at(1, 10),
        end=at(1, 12),
        color=RED,
    )
    lines = " ".join(history.describe(event.changes.first()))
    assert "couleur" in lines and "Rouge" in lines
    event = services.restore(event, created, user=admin_user)
    assert event.color == ""


def test_calendar_and_public_feed_use_the_color(member_client, marie, at):
    event = services.create(actor=marie, title="Atelier", start=at(1, 10), end=at(1, 12), color=RED)
    start, end = at(0, 0).date().isoformat(), at(7, 0).date().isoformat()
    data = json.loads(
        member_client.get(reverse("agenda:events_json") + f"?start={start}&end={end}").content
    )
    assert data[0]["color"] == RED
    assert public_event(event)["color"] == RED


def test_duplicate_keeps_the_color(member_client, marie, at):
    event = services.create(actor=marie, title="Atelier", start=at(1, 10), end=at(1, 12), color=RED)
    response = member_client.get(reverse("agenda:new") + f"?depuis={event.pk}")
    assert response.context["form"].initial["color"] == RED
