"""Pages des idées pour les membres : dépôt, tableau, fiche, réactions, statut (CDC §4)."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.actors.resolvers import NAME_COOKIE
from apps.actors.services import get_or_create_for_name
from apps.agenda.models import Event
from apps.ideas import services
from apps.ideas.models import Idea, Reaction
from conftest import login_verified

pytestmark = pytest.mark.django_db


@pytest.fixture
def named(member_client):
    member_client.cookies[NAME_COOKIE] = "Paul"
    return member_client


@pytest.fixture
def idea(db):
    return services.create(actor=get_or_create_for_name("Marie"), title="Un ciné-club")


@pytest.mark.parametrize("url", ["/idees/", "/idees/nouvelle/"])
def test_idea_pages_are_internal(client, site, url):
    assert client.get(url).status_code == 302


def test_deposit_with_name_title_and_kind_only(member_client):
    response = member_client.post(
        reverse("ideas:new"),
        {"title": "Un ciné-club", "kind": "wish", "duration_minutes": 120, "author_name": "Marie"},
    )
    idea = Idea.objects.get()
    assert response["Location"] == reverse("ideas:detail", args=[idea.pk])
    assert (idea.kind, idea.owner.display_name, idea.origin) == ("wish", "Marie", "member")


def test_deposit_with_precise_slot_places_it(member_client, at, room):
    start = at(2, 14)
    member_client.post(
        reverse("ideas:new"),
        {
            "title": "Atelier",
            "kind": "event",
            "duration_minutes": 90,
            "wanted_room": room.pk,
            "slot1_date": start.date().isoformat(),
            "slot1_time": "14:00",
            "author_name": "Marie",
        },
    )
    event = Idea.objects.get().events.get()
    assert (event.status, event.start, event.room) == ("provisional", start, room)


def test_list_hides_proposals_awaiting_moderation(member_client, idea, make_idea):
    make_idea(title="Proposition à modérer")
    body = member_client.get(reverse("ideas:list")).content.decode()
    assert "Un ciné-club" in body
    assert "Proposition à modérer" not in body


def test_list_filters_and_sorts_by_interest(member_client, idea):
    popular = services.create(
        actor=get_or_create_for_name("Hugo"), title="Journée d'étude", kind=Idea.Kind.PROJECT
    )
    for name in ("Inès", "Léa"):
        services.toggle_reaction(popular, actor=get_or_create_for_name(name), kind="interested")
    ideas = member_client.get(reverse("ideas:list"), {"tri": "interet"}).context["ideas"]
    assert [i.title for i in ideas] == ["Journée d'étude", "Un ciné-club"]
    assert ideas[0].interest == 2
    ideas = member_client.get(reverse("ideas:list"), {"kind": "project"}).context["ideas"]
    assert [i.title for i in ideas] == ["Journée d'étude"]


def test_list_hides_abandoned_ideas_by_default(member_client, idea):
    services.set_status(idea, Idea.Status.ABANDONED, actor=idea.owner)
    assert not member_client.get(reverse("ideas:list")).context["ideas"]
    ideas = member_client.get(reverse("ideas:list"), {"status": "toutes"}).context["ideas"]
    assert [i.title for i in ideas] == ["Un ciné-club"]


def test_pending_proposal_is_hidden_from_members(member_client, make_idea, admin_user):
    pending = make_idea()
    url = reverse("ideas:detail", args=[pending.pk])
    assert member_client.get(url).status_code == 404
    assert login_verified(Client(), admin_user).get(url).status_code == 200


def test_owner_email_is_shown_to_managers_only(member_client, make_idea, admin_user):
    """CLAUDE.md PUB-2 : l'e-mail d'un porteur extérieur reste réservé à la gestion."""
    proposal = make_idea()
    services.accept(proposal, user=admin_user)
    url = reverse("ideas:detail", args=[proposal.pk])
    assert "camille.martin@univ.example" not in member_client.get(url).content.decode()
    manager = login_verified(Client(), admin_user)
    assert "mailto:camille.martin@univ.example" in manager.get(url).content.decode()


def test_reaction_is_toggled_under_the_remembered_name(named, idea):
    url = reverse("ideas:react", args=[idea.pk])
    named.post(url, {"kind": "participate", "author_name": "Paul"})
    body = named.get(reverse("ideas:detail", args=[idea.pk])).content.decode()
    assert "Je participe · 1" in body
    assert "Paul" in body
    named.post(url, {"kind": "participate", "author_name": "Paul"})
    assert not Reaction.objects.exists()


def test_reaction_needs_a_name(member_client, idea):
    member_client.post(reverse("ideas:react", args=[idea.pk]), {"kind": "help"})
    assert not Reaction.objects.exists()


def test_status_change_and_automatic_statuses_are_refused(named, idea):
    url = reverse("ideas:status", args=[idea.pk])
    named.post(url, {"status": "preparing", "author_name": "Paul"})
    idea.refresh_from_db()
    assert idea.status == "preparing"
    named.post(url, {"status": "done", "author_name": "Paul"})
    idea.refresh_from_db()
    assert idea.status == "preparing"


def test_any_participant_completes_an_idea(named, idea):
    named.post(
        reverse("ideas:edit", args=[idea.pk]),
        {
            "title": "Un ciné-club mensuel",
            "kind": "project",
            "duration_minutes": 120,
            "needs": "Un vidéoprojecteur",
            "author_name": "Paul",
        },
    )
    idea.refresh_from_db()
    assert (idea.title, idea.needs, idea.updated_by.display_name) == (
        "Un ciné-club mensuel",
        "Un vidéoprojecteur",
        "Paul",
    )


def test_event_from_idea_is_provisional_and_linked(named, idea, at, room):
    """Décision 10 : un événement issu d'une idée commence provisoire, même sans conflit."""
    idea.wanted_room = room
    idea.save()
    form = named.get(reverse("agenda:new"), {"idee": idea.pk}).context["form"]
    assert (form.initial["title"], form.initial["room"]) == ("Un ciné-club", room)
    start = at(3, 18)
    named.post(
        reverse("agenda:new"),
        {
            "idee": idea.pk,
            "title": "Ciné-club : première séance",
            "day": start.date().isoformat(),
            "start_time": "18:00",
            "end_time": "20:00",
            "room": room.pk,
            "author_name": "Paul",
        },
    )
    event = Event.objects.get()
    assert (event.idea, event.status, event.owner.display_name) == (idea, "provisional", "Paul")
