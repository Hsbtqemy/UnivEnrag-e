"""Espaces minimaux de la phase 1 : rattachement, couleur, archivage."""

import pytest
from django.urls import reverse

from apps.actors.services import get_or_create_for_name
from apps.agenda import services
from apps.spaces.models import Space
from conftest import login_verified

pytestmark = pytest.mark.django_db


@pytest.fixture
def space(db):
    return Space.objects.create(name="Conditions de travail", color="#c0392b")


def test_slug_is_generated(space):
    assert space.slug == "conditions-de-travail"


def test_event_takes_space_color_before_room_color(space, room, at):
    event = services.create(
        actor=get_or_create_for_name("Marie"),
        title="Groupe",
        start=at(1, 10),
        end=at(1, 11),
        room=room,
        space=space,
    )
    assert event.display_color == "#c0392b"


def test_archived_space_takes_no_new_event(space, at):
    space.is_archived = True
    space.save()
    with pytest.raises(services.EventError):
        services.create(
            actor=get_or_create_for_name("Marie"),
            title="Trop tard",
            start=at(1, 10),
            end=at(1, 11),
            space=space,
        )


def test_event_in_archived_space_stays_editable(space, at):
    marie = get_or_create_for_name("Marie")
    event = services.create(
        actor=marie, title="Groupe", start=at(1, 10), end=at(1, 11), space=space
    )
    space.is_archived = True
    space.save()
    services.update(
        event,
        actor=marie,
        revision=event.revision,
        title="Groupe (fin)",
        start=event.start,
        end=event.end,
        space=space,
    )


def test_form_offers_open_spaces_only(member_client, space):
    Space.objects.create(name="Ancien groupe", is_archived=True)
    form = member_client.get(reverse("agenda:new")).context["form"]
    assert list(form.fields["space"].queryset) == [space]


def test_member_feed_carries_space_for_filter(member_client, space, at):
    services.create(
        actor=get_or_create_for_name("Marie"),
        title="Groupe",
        start=at(1, 10),
        end=at(1, 11),
        space=space,
    )
    data = member_client.get(reverse("agenda:events_json")).json()
    assert data[0]["extendedProps"]["spaceId"] == space.pk
    assert data[0]["color"] == "#c0392b"


def test_spaces_admin_needs_spaces_right(client, make_manager):
    login_verified(client, make_manager("manage_spaces"))
    assert client.get("/gestion/admin/spaces/space/").status_code == 200
    client.logout()
    login_verified(client, make_manager("manage_rooms", username="autre"))
    assert client.get("/gestion/admin/spaces/space/").status_code == 403
