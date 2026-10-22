"""Conflits de salle (CLAUDE.md SAL-2) et verrouillage optimiste."""

import pytest

from apps.agenda import services
from apps.agenda.models import Event
from apps.ideas import services as ideas_services

pytestmark = pytest.mark.django_db


@pytest.fixture
def place(make_idea, admin_user):
    """Crée une proposition acceptée et placée en provisoire ; renvoie l'événement."""

    def build(start, end, room, title="Événement"):
        idea = make_idea(title=title)
        ideas_services.accept(idea, user=admin_user)
        return ideas_services.place(idea, start=start, end=end, room=room)

    return build


def test_confirm_refused_when_room_taken_by_confirmed_event(place, at, room, admin_user):
    first = place(at(1, 10), at(1, 12), room, "Premier")
    second = place(at(1, 11), at(1, 13), room, "Second")
    services.confirm(first, user=admin_user)
    with pytest.raises(services.RoomConflictError) as error:
        services.confirm(second, user=admin_user)
    assert "Premier" in str(error.value)
    second.refresh_from_db()
    assert second.status == Event.Status.PROVISIONAL


def test_back_to_back_events_do_not_conflict(place, at, room, admin_user):
    first = place(at(1, 10), at(1, 12), room)
    second = place(at(1, 12), at(1, 14), room)
    services.confirm(first, user=admin_user)
    services.confirm(second, user=admin_user)


def test_different_rooms_and_free_place_never_conflict(place, at, room, other_room, admin_user):
    services.confirm(place(at(1, 10), at(1, 12), room), user=admin_user)
    services.confirm(place(at(1, 10), at(1, 12), other_room), user=admin_user)
    services.confirm(place(at(1, 10), at(1, 12), None), user=admin_user)
    services.confirm(place(at(1, 10), at(1, 12), None), user=admin_user)


def test_cancelled_event_frees_the_room(place, at, room, admin_user):
    first = place(at(1, 10), at(1, 12), room)
    services.confirm(first, user=admin_user)
    Event.objects.filter(pk=first.pk).update(status=Event.Status.CANCELLED)
    services.confirm(place(at(1, 10), at(1, 12), room), user=admin_user)


def test_provisional_overlap_is_only_a_warning(place, at, room):
    first = place(at(1, 10), at(1, 12), room, "Premier")
    second = place(at(1, 11), at(1, 13), room, "Second")
    assert any("Premier" in w for w in services.warnings_for(second))
    assert any("Second" in w for w in services.warnings_for(first))


def test_batch_confirm_never_double_books(place, at, room, admin_user):
    first = place(at(1, 10), at(1, 12), room, "Premier")
    second = place(at(1, 11), at(1, 13), room, "Second")
    report = services.confirm_many([second, first], user=admin_user)
    assert [e.pk for e in report.confirmed] == [first.pk]
    assert [e.pk for e, _ in report.refused] == [second.pk]


def test_moving_confirmed_event_into_taken_room_is_refused(place, at, room, admin_user):
    services.confirm(place(at(1, 10), at(1, 12), room), user=admin_user)
    other = services.confirm(place(at(2, 10), at(2, 12), room), user=admin_user)
    with pytest.raises(services.RoomConflictError):
        services.move(other, start=at(1, 11), end=at(1, 13), room=room, revision=other.revision)


def test_moving_provisional_event_is_allowed_even_if_room_taken(place, at, room, admin_user):
    services.confirm(place(at(1, 10), at(1, 12), room), user=admin_user)
    other = place(at(2, 10), at(2, 12), room)
    moved = services.move(other, start=at(1, 11), end=at(1, 13), room=room, revision=1)
    assert moved.start == at(1, 11)
    assert moved.revision == 2


def test_stale_revision_is_refused(place, at, room):
    event = place(at(1, 10), at(1, 12), room)
    services.move(event, start=at(1, 11), end=at(1, 13), room=room, revision=1)
    with pytest.raises(services.StaleRevisionError):
        services.move(event, start=at(1, 14), end=at(1, 16), room=room, revision=1)


def test_end_must_follow_start(place, at, room):
    event = place(at(1, 10), at(1, 12), room)
    with pytest.raises(services.EventError):
        services.move(event, start=at(1, 12), end=at(1, 10), room=room, revision=1)
