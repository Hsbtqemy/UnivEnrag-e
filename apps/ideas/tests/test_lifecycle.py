"""Cycle de vie des idées : modération, placement, statuts manuels et automatiques."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.actors.services import get_or_create_for_name
from apps.agenda import services as agenda_services
from apps.agenda.models import Event
from apps.ideas import services
from apps.ideas.forms import IdeaForm
from apps.ideas.models import Idea, Reaction
from apps.spaces.models import Space

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


# --- Idées des membres -------------------------------------------------------------------


@pytest.fixture
def marie(db):
    return get_or_create_for_name("Marie")


def test_member_idea_needs_only_title_and_kind(marie):
    idea = services.create(actor=marie, title="Un ciné-club", kind=Idea.Kind.WISH)
    assert (idea.origin, idea.status, idea.owner_email) == (Idea.Origin.MEMBER, "new", "")
    assert not idea.events.exists()


def test_member_idea_with_precise_slot_is_placed_provisional_and_private(marie, at, room):
    space = Space.objects.create(name="Séminaire")
    idea = services.create(
        actor=marie,
        title="Atelier",
        space=space,
        wanted_room=room,
        duration_minutes=90,
        slots=[{"period_text": "Ou un jeudi"}, {"start": at(2, 14)}],
    )
    event = idea.events.get()
    assert event.status == Event.Status.PROVISIONAL
    assert (event.start, event.end, event.room, event.space) == (
        at(2, 14),
        at(2, 15, 30),
        room,
        space,
    )
    # PUB-1 : rien de public par défaut ; seule une proposition extérieure l'est.
    assert (event.is_public, event.owner) == (False, marie)
    assert event.changes.get().actor == marie


def test_manual_statuses(marie):
    idea = services.create(actor=marie, title="Projet", kind=Idea.Kind.PROJECT)
    services.set_status(idea, Idea.Status.PREPARING, actor=marie)
    idea.refresh_from_db()
    assert idea.status == Idea.Status.PREPARING
    for automatic in (Idea.Status.PLANNED, Idea.Status.DONE):
        with pytest.raises(services.TransitionError):
            services.set_status(idea, automatic, actor=marie)


def test_abandoning_cancels_provisional_placements(marie, at):
    idea = services.create(actor=marie, title="Atelier", slots=[{"start": at(1, 10)}])
    services.set_status(idea, Idea.Status.ABANDONED, actor=marie)
    assert idea.events.get().status == Event.Status.CANCELLED
    idea.refresh_from_db()
    assert idea.status == Idea.Status.ABANDONED
    # Une idée abandonnée peut reprendre.
    services.set_status(idea, Idea.Status.NEW, actor=marie)


def test_planned_idea_status_is_not_manual(marie, at, admin_user):
    idea = services.create(actor=marie, title="Atelier", slots=[{"start": at(1, 10)}])
    agenda_services.confirm(idea.events.get(), user=admin_user)
    with pytest.raises(services.TransitionError):
        services.set_status(idea, Idea.Status.ABANDONED, actor=marie)


def test_cancelling_the_confirmed_event_brings_idea_back_to_preparing(marie, at, admin_user):
    idea = services.create(actor=marie, title="Atelier", slots=[{"start": at(1, 10)}])
    event = agenda_services.confirm(idea.events.get(), user=admin_user)
    agenda_services.cancel(event, actor=marie, revision=event.revision)
    idea.refresh_from_db()
    assert idea.status == Idea.Status.PREPARING


def test_idea_is_done_once_its_last_confirmed_event_is_over(marie, at, admin_user):
    """Décision 13 : une idée peut donner plusieurs événements."""
    idea = services.create(actor=marie, title="Cycle", kind=Idea.Kind.PROJECT)
    first = agenda_services.create(
        actor=marie, title="Séance 1", start=at(1, 10), end=at(1, 12), idea=idea
    )
    second = agenda_services.create(
        actor=marie, title="Séance 2", start=at(8, 10), end=at(8, 12), idea=idea
    )
    assert first.status == second.status == Event.Status.PROVISIONAL
    agenda_services.confirm(first, user=admin_user)
    agenda_services.confirm(second, user=admin_user)
    assert services.mark_done(now=at(2, 0)) == 0
    assert services.mark_done(now=at(8, 12)) == 1
    idea.refresh_from_db()
    assert idea.status == Idea.Status.DONE


def test_mark_done_command(marie, at, admin_user):
    idea = services.create(actor=marie, title="Hier", kind=Idea.Kind.EVENT)
    event = agenda_services.create(
        actor=marie, title="Hier", start=at(-10, 10), end=at(-10, 12), idea=idea
    )
    agenda_services.confirm(event, user=admin_user)
    call_command("ideas_mark_done")
    idea.refresh_from_db()
    assert idea.status == Idea.Status.DONE


def test_member_edit_replaces_slots_and_records_editor(marie, at):
    idea = services.create(actor=marie, title="Idée", slots=[{"period_text": "Un jour"}])
    paul = get_or_create_for_name("Paul")
    services.update(idea, actor=paul, title="Idée complétée", slots=[{"period_text": "Mardi"}])
    idea.refresh_from_db()
    assert (idea.title, idea.updated_by) == ("Idée complétée", paul)
    assert [s.period_text for s in idea.slots.all()] == ["Mardi"]


def test_reaction_toggles(marie):
    idea = services.create(actor=marie, title="Idée")
    paul = get_or_create_for_name("Paul")
    assert services.toggle_reaction(idea, actor=paul, kind="participate") is True
    assert services.toggle_reaction(idea, actor=paul, kind="help") is True
    assert Reaction.objects.filter(idea=idea, actor=paul).count() == 2
    assert services.toggle_reaction(idea, actor=paul, kind="participate") is False
    by_kind = {r["kind"]: r["actors"] for r in services.reactions_by_kind(idea)}
    assert by_kind == {"participate": [], "help": [paul], "interested": []}


def test_cannot_react_to_pending_proposal(make_idea, marie):
    with pytest.raises(services.TransitionError):
        services.toggle_reaction(make_idea(), actor=marie, kind="interested")


def test_to_place_lists_event_ideas_without_active_event(marie, at, make_idea, admin_user):
    waiting = services.create(actor=marie, title="Sans date")
    services.create(actor=marie, title="Projet", kind=Idea.Kind.PROJECT)
    placed = services.create(actor=marie, title="Placée", slots=[{"start": at(1, 10)}])
    make_idea(title="À modérer")
    assert list(Idea.objects.to_place()) == [waiting]
    event = placed.events.get()
    agenda_services.cancel(event, actor=marie, revision=event.revision)
    assert set(Idea.objects.to_place()) == {waiting, placed}


def test_dates_in_the_past_are_rejected_on_new_ideas_only(at):
    past = at(-14, 10)
    data = {
        "title": "Idée",
        "kind": "event",
        "duration_minutes": 120,
        "author_name": "Marie",
        "slot1_date": past.date().isoformat(),
        "slot1_time": "10:00",
    }
    assert not IdeaForm(data).is_valid()
    idea = services.create(actor=get_or_create_for_name("Marie"), title="Ancienne")
    assert IdeaForm(data, instance=idea).is_valid()


def test_precise_slot_end_follows_wanted_duration(marie, at):
    idea = services.create(actor=marie, title="Idée", slots=[{"start": at(1, 10)}])
    slot = idea.slots.get()
    assert slot.end - slot.start == timedelta(minutes=idea.duration_minutes)


def test_recent_moderation_lists_only_external_proposals(admin_client, make_idea, admin_user):
    """Les idées des membres ne passent pas par la modération : pas dans ses décisions."""
    services.accept(make_idea("Venue de l'extérieur"), user=admin_user)
    services.create(actor=get_or_create_for_name("Inès"), title="Idée de membre", kind="event")
    body = admin_client.get(reverse("ideas:moderation")).content.decode()
    assert "Venue de l&#x27;extérieur" in body
    assert "Idée de membre" not in body
