"""Salles : plages d'ouverture, validation, dérogation (CLAUDE.md SAL-2, SAL-3, SAL-4)."""

from datetime import time

import pytest
from django.urls import reverse

from apps.actors.services import get_or_create_for_name
from apps.agenda import services
from apps.agenda.models import Event
from apps.audit.models import AuditLog
from apps.ideas import services as ideas_services
from apps.rooms.models import OpeningHours, Room
from conftest import login_verified

pytestmark = pytest.mark.django_db


@pytest.fixture
def marie(db):
    return get_or_create_for_name("Marie")


@pytest.fixture
def weekday_room(room):
    """Ouverte du lundi au vendredi, 8 h - 20 h ; `at(0, …)` tombe un lundi."""
    for day in range(5):
        OpeningHours.objects.create(room=room, weekday=day, opens=time(8), closes=time(20))
    return room


@pytest.fixture
def approval_room(db):
    return Room.objects.create(name="Salle de projection", booking_mode=Room.BookingMode.APPROVAL)


def book(actor, at, room, day=1, start=10, end=12, **extra):
    return services.create(
        actor=actor,
        title=extra.pop("title", "Réunion"),
        start=at(day, start),
        end=at(day, end),
        room=room,
        **extra,
    )


# --- Plages d'ouverture ------------------------------------------------------------------


def test_room_without_hours_is_always_open(room, at):
    assert room.is_open(at(5, 22), at(5, 23))


def test_opening_hours(weekday_room, at):
    assert weekday_room.is_open(at(0, 8), at(0, 20))
    assert not weekday_room.is_open(at(0, 7), at(0, 9))
    assert not weekday_room.is_open(at(0, 19), at(0, 21))
    assert not weekday_room.is_open(at(5, 10), at(5, 12))  # samedi


def test_booking_outside_hours_is_refused(marie, at, weekday_room):
    with pytest.raises(services.RoomClosedError):
        book(marie, at, weekday_room, day=5)
    with pytest.raises(services.RoomClosedError):
        book(marie, at, weekday_room, start=19, end=21)


def test_derogation_needs_rooms_right_and_is_logged(marie, at, weekday_room, make_manager):
    with pytest.raises(services.RoomClosedError):
        book(marie, at, weekday_room, day=5, override=True)  # simple membre : refusé
    agenda_manager = make_manager("manage_agenda", username="agenda")
    with pytest.raises(services.RoomClosedError):
        book(marie, at, weekday_room, day=5, override=True, user=agenda_manager)
    rooms_manager = make_manager("manage_rooms", username="salles")
    event = book(marie, at, weekday_room, day=5, override=True, user=rooms_manager)
    entry = AuditLog.objects.get(action="rooms.derogation")
    assert entry.object_id == str(event.pk)
    assert "hors des plages d'ouverture" in entry.details["reasons"]


def test_derogation_allows_double_booking(marie, at, room, make_manager):
    book(marie, at, room)
    rooms_manager = make_manager("manage_rooms")
    book(marie, at, room, override=True, user=rooms_manager, title="Exception")
    assert Event.objects.filter(room=room).count() == 2


# --- Salles soumises à validation --------------------------------------------------------


def test_member_booking_in_approval_room_is_pending_but_blocks(marie, at, approval_room):
    event = book(marie, at, approval_room)
    assert event.status == Event.Status.CONFIRMED
    assert event.room_pending
    with pytest.raises(services.RoomConflictError):
        book(marie, at, approval_room, title="Autre")


def test_rooms_manager_booking_is_approved_at_once(marie, at, approval_room, make_manager):
    event = book(marie, at, approval_room, user=make_manager("manage_rooms"))
    assert not event.room_pending


def test_approve_and_refuse(marie, at, approval_room, make_manager):
    rooms_manager = make_manager("manage_rooms")
    first = book(marie, at, approval_room)
    second = book(marie, at, approval_room, day=2)
    services.approve_room(first, user=rooms_manager)
    services.refuse_room(second, user=rooms_manager, reason="Travaux")
    first.refresh_from_db()
    second.refresh_from_db()
    assert not first.room_pending
    assert (second.room, second.status, second.place_label) == (
        None,
        "confirmed",
        "Lieu à préciser",
    )
    assert second.changes.first().action == "room"


def test_only_rooms_managers_validate(marie, at, approval_room, make_manager):
    event = book(marie, at, approval_room)
    with pytest.raises(services.EventError):
        services.approve_room(event, user=make_manager("manage_agenda"))


def test_moving_an_approved_booking_needs_new_approval(marie, at, approval_room, make_manager):
    event = book(marie, at, approval_room)
    event = services.approve_room(event, user=make_manager("manage_rooms"))
    event = services.update(
        event,
        actor=marie,
        revision=event.revision,
        title=event.title,
        start=event.start,
        end=event.end,
        room=approval_room,
        description="Précision",
    )
    assert not event.room_pending  # ni salle ni créneau changés
    event = services.move(
        event,
        start=at(3, 10),
        end=at(3, 12),
        room=approval_room,
        revision=event.revision,
        actor=marie,
    )
    assert event.room_pending


def test_confirming_idea_in_approval_room_waits_for_rooms_manager(
    make_idea, at, approval_room, make_manager
):
    idea = make_idea(slots=[{"start": at(1, 10)}], room=approval_room)
    agenda_manager = make_manager("manage_agenda")
    ideas_services.accept(idea, user=agenda_manager)
    event = services.confirm(idea.event, user=agenda_manager)
    assert event.room_pending


# --- Pages -------------------------------------------------------------------------------


def test_rooms_page_for_members(member_client, weekday_room, approval_room):
    page = member_client.get(reverse("agenda:rooms")).content.decode()
    assert "Soumise à validation" in page
    assert "lundi 08:00–20:00" in page


def test_room_requests_queue(client, marie, at, approval_room, make_manager):
    event = book(marie, at, approval_room)
    login_verified(client, make_manager("manage_rooms"))
    assert "Réunion" in client.get(reverse("agenda:room_requests")).content.decode()
    client.post(reverse("agenda:room_requests"), {"event": event.pk, "decision": "approve"})
    event.refresh_from_db()
    assert not event.room_pending


def test_room_requests_need_rooms_right(client, make_manager):
    login_verified(client, make_manager("manage_agenda"))
    assert client.get(reverse("agenda:room_requests")).status_code == 403


def test_check_endpoint_reports_closed_room_and_approval(
    member_client, at, weekday_room, approval_room
):
    from apps.core.dates import to_wall_clock

    closed = member_client.get(
        reverse("agenda:check"),
        {
            "start": to_wall_clock(at(5, 10)),
            "end": to_wall_clock(at(5, 12)),
            "room": weekday_room.pk,
        },
    ).json()
    assert "n'est pas ouverte" in closed["closed"]
    approval = member_client.get(
        reverse("agenda:check"),
        {
            "start": to_wall_clock(at(1, 10)),
            "end": to_wall_clock(at(1, 12)),
            "room": approval_room.pk,
        },
    ).json()
    assert approval["approval"] is True
