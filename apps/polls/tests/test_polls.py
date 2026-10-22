"""Sondage de dates : créneaux, réponses nominatives, meilleur créneau → événement."""

import pytest
from django.urls import reverse

from apps.actors.services import get_or_create_for_name
from apps.agenda.models import Event
from apps.polls import services
from apps.polls.models import Poll, PollAnswer

pytestmark = pytest.mark.django_db


@pytest.fixture
def poll(at, room):
    return services.create(
        actor=get_or_create_for_name("Marie"),
        title="Réunion du groupe",
        slots=[(at(1, 10), at(1, 12)), (at(2, 14), at(2, 16)), (at(3, 9), at(3, 10))],
        room=room,
    )


def test_needs_at_least_two_future_slots(at):
    marie = get_or_create_for_name("Marie")
    with pytest.raises(services.PollError):
        services.create(actor=marie, title="Un seul", slots=[(at(1, 10), at(1, 11))])
    with pytest.raises(services.PollError):
        services.create(
            actor=marie, title="Passé", slots=[(at(-30, 10), at(-30, 11)), (at(1, 10), at(1, 11))]
        )


def test_answers_are_nominal_and_replaced(poll):
    paul = get_or_create_for_name("Paul")
    first, second, third = poll.slots.all()
    services.answer(poll, actor=paul, answers={first.pk: "yes", second.pk: "maybe"})
    services.answer(poll, actor=paul, answers={second.pk: "yes"})
    assert list(PollAnswer.objects.values_list("slot", "answer")) == [(second.pk, "yes")]


def test_best_slot_counts_yes_then_maybe(poll):
    first, second, third = poll.slots.all()
    for name, answers in {
        "Paul": {first.pk: "yes", second.pk: "yes"},
        "Inès": {first.pk: "maybe", second.pk: "yes"},
        "Léa": {first.pk: "yes", second.pk: "maybe"},
    }.items():
        services.answer(poll, actor=get_or_create_for_name(name), answers=answers)
    results = services.results(poll)
    assert [(r.yes, r.maybe, r.is_best) for r in results.slots] == [
        (2, 1, True),
        (2, 1, True),
        (0, 0, False),
    ]
    assert results.participants == 3
    assert [name for name, _ in results.rows] == ["Inès", "Léa", "Paul"]


def test_closed_poll_takes_no_answer(poll, at):
    services.close_with_event(poll, None)
    with pytest.raises(services.PollError):
        services.answer(poll, actor=get_or_create_for_name("Paul"), answers={})


def test_member_creates_answers_and_fixes_slot(member_client, at, room):
    data = {
        "title": "Atelier",
        "description": "",
        "space": "",
        "room": room.pk,
        "author_name": "Inès",
        "slot1_day": at(1, 0).date().isoformat(),
        "slot1_start": "10:00",
        "slot1_end": "12:00",
        "slot2_day": at(2, 0).date().isoformat(),
        "slot2_start": "14:00",
        "slot2_end": "16:00",
    }
    response = member_client.post(reverse("polls:new"), data)
    assert response.status_code == 302
    poll_url = response["Location"]
    poll_id = int(poll_url.rstrip("/").split("/")[-1])
    poll = Poll.objects.get(pk=poll_id)
    first, second = poll.slots.all()
    member_client.post(
        poll_url, {f"slot-{first.pk}": "", f"slot-{second.pk}": "yes", "author_name": "Paul"}
    )
    page = member_client.get(poll_url).content.decode()
    assert "Paul" in page and "Fixer ce créneau" in page

    # Le formulaire d'événement arrive pré-rempli, et le sondage se clôt à la création.
    form_page = member_client.get(reverse("agenda:new") + f"?sondage={poll.pk}&creneau={second.pk}")
    initial = form_page.context["form"].initial
    assert (initial["title"], initial["room"]) == ("Atelier", room)
    assert initial["start_time"].strftime("%H:%M") == "14:00"
    response = member_client.post(
        reverse("agenda:new"),
        {
            "sondage": poll.pk,
            "title": "Atelier",
            "day": at(2, 0).date().isoformat(),
            "start_time": "14:00",
            "end_time": "16:00",
            "room": room.pk,
            "author_name": "Paul",
        },
    )
    assert response.status_code == 302
    poll.refresh_from_db()
    assert poll.is_closed and poll.event == Event.objects.get()


def test_polls_are_internal(client, site):
    assert client.get(reverse("polls:list")).status_code == 302
