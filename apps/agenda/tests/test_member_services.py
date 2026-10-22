"""Règles de l'agenda des membres (CLAUDE.md AGE-1 à AGE-5, SAL-2, décisions 10 et 11)."""

import pytest

from apps.actors.services import get_or_create_for_name
from apps.agenda import services
from apps.agenda.models import Event, EventChange

pytestmark = pytest.mark.django_db


@pytest.fixture
def marie(db):
    return get_or_create_for_name("Marie")


@pytest.fixture
def paul(db):
    return get_or_create_for_name("Paul")


def make(actor, at, room=None, day=1, hour=10, **extra):
    return services.create(
        actor=actor,
        title=extra.pop("title", "Réunion"),
        start=at(day, hour),
        end=at(day, hour + 2),
        room=room,
        **extra,
    )


def test_member_event_is_confirmed_at_once_and_history_starts(marie, at, room):
    event = make(marie, at, room)
    assert event.status == Event.Status.CONFIRMED
    assert event.owner == marie
    change = event.changes.get()
    assert (change.action, change.actor) == (EventChange.Action.CREATED, marie)


def test_creation_refused_when_room_taken(marie, at, room):
    make(marie, at, room, title="Premier")
    with pytest.raises(services.RoomConflictError):
        make(marie, at, room, title="Second")
    assert Event.objects.count() == 1


def test_creation_in_other_room_or_free_place_is_fine(marie, at, room, other_room):
    make(marie, at, room)
    make(marie, at, other_room)
    make(marie, at, None, place_text="Café du coin")


def test_member_public_box_is_only_a_request(marie, at):
    event = make(marie, at, wants_public=True)
    assert (event.is_public, event.public_requested) == (False, True)


def test_manager_public_box_publishes(marie, at, admin_user):
    event = make(marie, at, wants_public=True, user=admin_user)
    assert (event.is_public, event.public_requested) == (True, False)


def test_any_member_edits_and_history_keeps_before_after(marie, paul, at, room):
    event = make(marie, at, room)
    event = services.update(
        event,
        actor=paul,
        revision=event.revision,
        title="Réunion déplacée",
        start=at(2, 14),
        end=at(2, 16),
        room=room,
    )
    change = event.changes.first()
    assert change.actor == paul
    assert change.changes["title"] == ["Réunion", "Réunion déplacée"]
    assert event.owner == marie  # le porteur ne change pas


def test_stale_revision_is_refused(marie, paul, at):
    event = make(marie, at)
    stale = event.revision
    services.update(event, actor=paul, revision=stale, title="A", start=at(1, 10), end=at(1, 11))
    with pytest.raises(services.StaleRevisionError):
        services.update(
            event, actor=marie, revision=stale, title="B", start=at(1, 10), end=at(1, 11)
        )


def test_lock_blocks_members_not_managers(marie, at, admin_user):
    event = make(marie, at)
    event = services.set_locked(event, locked=True, user=admin_user)
    with pytest.raises(services.LockedError):
        services.move(
            event, start=at(2, 9), end=at(2, 10), room=None, revision=event.revision, actor=marie
        )
    with pytest.raises(services.LockedError):
        services.cancel(event, actor=marie, revision=event.revision)
    services.move(
        event, start=at(2, 9), end=at(2, 10), room=None, revision=event.revision, user=admin_user
    )


def test_only_managers_lock_confirm_restore_publish(marie, at, make_manager):
    event = make(marie, at)
    rooms_only = make_manager("manage_rooms")
    for call in (
        lambda: services.set_locked(event, locked=True, user=rooms_only),
        lambda: services.confirm(event, user=rooms_only),
        lambda: services.set_public(event, is_public=True, user=rooms_only),
        lambda: services.restore(event, event.changes.first(), user=rooms_only),
    ):
        with pytest.raises(services.EventError):
            call()


def test_public_page_manager_can_publish(marie, at, make_manager):
    event = make(marie, at, wants_public=True)
    publisher = make_manager("manage_public")
    event = services.set_public(event, is_public=True, user=publisher)
    assert (event.is_public, event.public_requested) == (True, False)


def test_cancelled_event_stays_and_frees_room(marie, at, room):
    event = make(marie, at, room)
    services.cancel(event, actor=marie, revision=event.revision)
    event.refresh_from_db()
    assert event.status == Event.Status.CANCELLED
    make(marie, at, room, title="À la place")  # la salle est libre


def test_restore_previous_version_is_itself_tracked(marie, paul, at, room, admin_user):
    event = make(marie, at, room)
    created = event.changes.get()
    event = services.update(
        event,
        actor=paul,
        revision=event.revision,
        title="Titre faux",
        start=at(3, 9),
        end=at(3, 10),
        room=None,
    )
    event = services.restore(event, created, user=admin_user)
    assert (event.title, event.start, event.room) == ("Réunion", at(1, 10), room)
    assert event.changes.first().action == EventChange.Action.RESTORED
    assert event.changes.count() == 3


def test_restore_refused_if_room_taken_since(marie, paul, at, room, admin_user):
    event = make(marie, at, room)
    created = event.changes.get()
    event = services.update(
        event,
        actor=paul,
        revision=event.revision,
        title="Ailleurs",
        start=at(3, 9),
        end=at(3, 10),
        room=room,
    )
    make(paul, at, room, title="Occupe l'ancien créneau")
    with pytest.raises(services.RoomConflictError):
        services.restore(event, created, user=admin_user)
