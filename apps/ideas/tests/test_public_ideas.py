"""Idées sur la page publique : dépôt de tout type, publication par un habilité, réactions
du public (CLAUDE.md PUB-1 : rien n'est public par défaut)."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.actors.services import get_or_create_for_name
from apps.audit.models import AuditLog
from apps.ideas import services
from apps.ideas.models import Idea, Reaction
from apps.ideas.tests.test_public_form import form_data
from conftest import login_verified

pytestmark = pytest.mark.django_db


@pytest.fixture
def moderator(make_manager):
    return make_manager("moderate", username="moderatrice")


@pytest.fixture
def public_idea(make_idea, moderator):
    idea = make_idea("Un ciné-club", name="Camille Martin")
    return services.accept(idea, user=moderator, public=True)


def test_public_form_accepts_a_project_and_ignores_slots(
    client,
    old_enough_token,
    at,
    room,
):
    data = form_data(old_enough_token, at, kind="project", wanted_room=room.pk, owner_hidden="on")
    response = client.post(reverse("ideas:propose"), data)
    idea = Idea.objects.get()
    assert response.status_code == 302
    assert (idea.kind, idea.status, idea.origin) == ("project", "pending", "external")
    assert idea.owner_hidden and not idea.is_public
    assert idea.wanted_room is None and not idea.slots.exists()


def test_public_form_offers_every_kind(client):
    page = client.get(reverse("ideas:propose")).content.decode()
    assert "Proposer une idée" in page
    for kind in ("event", "project", "wish"):
        assert f'value="{kind}"' in page


def test_nothing_is_public_by_default(client, make_idea, moderator):
    pending = make_idea("En attente")
    accepted = services.accept(make_idea("Acceptée"), user=moderator)
    member = services.create(actor=get_or_create_for_name("Paul"), title="Idée de membre")
    page = client.get(reverse("ideas:public_list")).content.decode()
    for idea in (pending, accepted, member):
        assert idea.title not in page
        assert client.get(reverse("ideas:public_detail", args=[idea.pk])).status_code == 404


def test_accepting_with_public_box_publishes_and_is_logged(client, make_idea, moderator):
    idea = make_idea("Un ciné-club")
    login_verified(client, moderator)
    client.post(reverse("ideas:accept", args=[idea.pk]), {"public": "1"})
    idea.refresh_from_db()
    assert idea.status == "new" and idea.is_public
    assert AuditLog.objects.filter(action="ideas.accepted", details__public=True).exists()


def test_public_page_shows_idea_without_email(client, public_idea):
    page = client.get(reverse("ideas:public_detail", args=[public_idea.pk])).content.decode()
    assert "Un ciné-club" in page and "Camille Martin" in page
    assert "camille.martin@univ.example" not in page
    assert "Un ciné-club" in client.get(reverse("ideas:public_list")).content.decode()


def test_hidden_owner_name_is_not_shown(client, public_idea, moderator):
    services.set_public(public_idea, user=moderator, is_public=True, owner_hidden=True)
    for url in (
        reverse("ideas:public_list"),
        reverse("ideas:public_detail", args=[public_idea.pk]),
    ):
        page = client.get(url).content.decode()
        assert "Un ciné-club" in page and "Camille Martin" not in page


def test_abandoned_idea_leaves_the_public_page(client, public_idea):
    services.set_status(public_idea, "abandoned", actor=get_or_create_for_name("Paul"))
    url = reverse("ideas:public_detail", args=[public_idea.pk])
    assert client.get(url).status_code == 404


def test_public_reaction_is_counted_without_name(client, public_idea):
    url = reverse("ideas:public_react", args=[public_idea.pk])
    response = client.post(url, {"author_name": "Lou Visiteur", "kind": "help"})
    assert response.status_code == 302
    reaction = Reaction.objects.get()
    assert (reaction.actor.display_name, reaction.kind) == ("Lou Visiteur", "help")
    page = client.get(reverse("ideas:public_detail", args=[public_idea.pk])).content.decode()
    assert "Je peux aider · 1" in page
    assert "Lou Visiteur" in page  # pré-rempli dans le champ « Votre nom », pour elle seule
    assert "Lou Visiteur" not in Client().get(response["Location"]).content.decode()


def test_public_reaction_is_never_removed(client, public_idea):
    url = reverse("ideas:public_react", args=[public_idea.pk])
    client.post(url, {"author_name": "Lou", "kind": "help"})
    client.post(url, {"author_name": "Lou", "kind": "help"})
    assert Reaction.objects.count() == 1


def test_cannot_react_to_a_non_public_idea(client, make_idea):
    idea = make_idea()
    response = client.post(
        reverse("ideas:public_react", args=[idea.pk]), {"author_name": "Lou", "kind": "help"}
    )
    assert response.status_code == 404
    assert not Reaction.objects.exists()


def test_publish_requires_moderation_or_public_page_right(client, make_idea, make_manager):
    idea = services.accept(make_idea(), user=make_manager("moderate", username="m"))
    url = reverse("ideas:publish", args=[idea.pk])
    assert client.post(url, {"is_public": "on"}).status_code == 302  # vers la connexion
    login_verified(client, make_manager("manage_agenda", username="agenda"))
    assert client.post(url, {"is_public": "on"}).status_code == 403
    idea.refresh_from_db()
    assert not idea.is_public
    login_verified(client, make_manager("manage_public", username="public"))
    client.post(url, {"is_public": "on"})
    idea.refresh_from_db()
    assert idea.is_public
    assert AuditLog.objects.filter(action="ideas.public").exists()


def test_pending_idea_cannot_be_published(make_idea, moderator):
    idea = make_idea()
    with pytest.raises(services.TransitionError):
        services.set_public(idea, user=moderator, is_public=True, owner_hidden=False)


def test_publish_box_only_for_entitled_managers(member_client, make_idea, moderator):
    idea = services.accept(make_idea(), user=moderator)
    url = reverse("ideas:detail", args=[idea.pk])
    assert "Page publique" not in member_client.get(url).content.decode()
    other = Client()
    login_verified(other, moderator)
    assert "Afficher cette idée sur la page publique" in other.get(url).content.decode()


def test_member_can_ask_to_hide_name_at_deposit(member_client):
    member_client.post(
        reverse("ideas:new"),
        {
            "title": "Atelier",
            "kind": "wish",
            "duration_minutes": 120,
            "author_name": "Marie",
            "owner_hidden": "on",
        },
    )
    assert Idea.objects.get().owner_hidden


def test_public_pages_need_no_access_code(client, public_idea):
    for url in (
        reverse("ideas:public_list"),
        reverse("ideas:public_detail", args=[public_idea.pk]),
    ):
        assert client.get(url).status_code == 200
