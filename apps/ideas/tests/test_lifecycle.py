"""Cycle de vie d'une proposition : modération, placement, planification."""

import pytest

from apps.agenda import services as agenda_services
from apps.agenda.models import Event
from apps.ideas import services
from apps.ideas.models import Idea

pytestmark = pytest.mark.django_db


def test_submit_creates_pending_idea_with_ranked_slots(make_idea, at, room):
    idea = make_idea(slots=[{"start": at(1, 14)}, {"period_text": "Un jeudi"}], room=room)
    assert idea.status == Idea.Status.PENDING
    first, second = idea.slots.all()
    assert (first.rank, first.start, first.end) == (1, at(1, 14), at(1, 16))
    assert (second.rank, second.start, second.period_text) == (2, None, "Un jeudi")


def test_accept_places_provisional_event_on_preferred_precise_slot(make_idea, at, room, admin_user):
    idea = make_idea(slots=[{"period_text": "Un jour"}, {"start": at(2, 10)}], room=room)
    services.accept(idea, user=admin_user)
    event = Event.objects.get(idea=idea)
    assert event.status == Event.Status.PROVISIONAL
    assert (event.start, event.room, event.is_public) == (at(2, 10), room, True)
    assert event.owner == idea.owner
    assert event.owner_email == idea.owner_email


def test_accept_without_precise_slot_leaves_idea_to_place(make_idea, admin_user):
    idea = make_idea(slots=[{"period_text": "Un midi"}])
    services.accept(idea, user=admin_user)
    assert not Event.objects.filter(idea=idea).exists()


def test_refuse_keeps_idea_with_reason(make_idea, admin_user):
    idea = make_idea()
    services.refuse(idea, user=admin_user, reason="  Hors sujet. ")
    idea.refresh_from_db()
    assert (idea.status, idea.refusal_reason) == (Idea.Status.REFUSED, "Hors sujet.")


@pytest.mark.parametrize("first", ["accept", "refuse"])
def test_moderation_happens_only_once(make_idea, admin_user, first):
    idea = make_idea()
    if first == "accept":
        services.accept(idea, user=admin_user)
    else:
        services.refuse(idea, user=admin_user, reason="")
    with pytest.raises(services.TransitionError):
        services.accept(idea, user=admin_user)
    with pytest.raises(services.TransitionError):
        services.refuse(idea, user=admin_user, reason="")


def test_pending_idea_cannot_be_placed(make_idea, at):
    idea = make_idea()
    with pytest.raises(services.TransitionError):
        services.place(idea, start=at(1, 10), end=at(1, 12), room=None)


def test_idea_cannot_be_placed_twice(make_idea, at, admin_user):
    idea = make_idea(slots=[{"start": at(1, 10)}])
    services.accept(idea, user=admin_user)
    with pytest.raises(services.TransitionError):
        services.place(idea, start=at(2, 10), end=at(2, 12), room=None)


def test_confirming_event_marks_idea_planned(make_idea, at, room, admin_user):
    idea = make_idea(slots=[{"start": at(1, 10)}], room=room)
    services.accept(idea, user=admin_user)
    agenda_services.confirm(Event.objects.get(idea=idea), user=admin_user)
    idea.refresh_from_db()
    assert idea.status == Idea.Status.PLANNED


def test_owner_edit_syncs_provisional_event(make_idea, at, admin_user):
    idea = make_idea(slots=[{"start": at(1, 10)}])
    services.accept(idea, user=admin_user)
    services.update_by_owner(idea, title="Nouveau titre", description="Nouvelle description")
    event = Event.objects.get(idea=idea)
    assert (event.title, event.description) == ("Nouveau titre", "Nouvelle description")


def test_owner_cannot_edit_once_planned(make_idea, at, admin_user):
    idea = make_idea(slots=[{"start": at(1, 10)}])
    services.accept(idea, user=admin_user)
    agenda_services.confirm(Event.objects.get(idea=idea), user=admin_user)
    with pytest.raises(services.TransitionError):
        services.update_by_owner(idea, title="Trop tard")
