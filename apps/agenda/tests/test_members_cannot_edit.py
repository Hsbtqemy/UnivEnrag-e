"""Réglage de lancement : les membres consultent et proposent, les habilités « agenda »
écrivent (CLAUDE.md AGE-3, décision 22)."""

import json

import pytest
from django.urls import reverse

from apps.actors.resolvers import NAME_COOKIE
from apps.actors.services import get_or_create_for_name
from apps.agenda import services
from apps.agenda.models import Event
from apps.core.dates import to_wall_clock
from apps.core.models import SiteSettings
from apps.ideas import services as ideas_services
from conftest import login_verified

pytestmark = pytest.mark.django_db


def post_json(client, url, payload):
    return client.post(url, json.dumps(payload), content_type="application/json")


@pytest.fixture
def named(member_client, members_cannot_edit):
    member_client.cookies[NAME_COOKIE] = "Paul"
    return member_client


@pytest.fixture
def event(at, room):
    return services.create(
        actor=get_or_create_for_name("Marie"),
        title="Séminaire",
        start=at(1, 10),
        end=at(1, 12),
        room=room,
    )


def test_editing_is_closed_by_default(db):
    assert SiteSettings.get().members_edit_agenda is False


def test_new_event_sends_member_to_idea_form(named, at):
    response = named.get(reverse("agenda:new"))
    assert response.status_code == 302
    assert response["Location"] == reverse("ideas:new")
    response = named.post(
        reverse("agenda:new"),
        {"title": "Assemblée", "day": at(1, 14).date().isoformat(), "author_name": "Paul"},
    )
    assert response.status_code == 302
    assert not Event.objects.exists()


def test_member_cannot_edit_or_cancel(named, event):
    response = named.get(reverse("agenda:edit", args=[event.pk]))
    assert response.status_code == 302
    named.post(
        reverse("agenda:cancel", args=[event.pk]),
        {"revision": event.revision, "author_name": "Paul"},
    )
    event.refresh_from_db()
    assert event.status == Event.Status.CONFIRMED


def test_member_cannot_drag_and_drop(named, event, at):
    response = post_json(
        named,
        reverse("agenda:move", args=[event.pk]),
        {
            "start": to_wall_clock(at(2, 10)),
            "end": to_wall_clock(at(2, 12)),
            "revision": event.revision,
        },
    )
    assert response.status_code == 403
    event.refresh_from_db()
    assert event.start == at(1, 10)


def test_member_cannot_place_an_idea(named, make_idea, admin_user, at):
    idea = make_idea(slots=[{"period_text": "Un midi"}])
    ideas_services.accept(idea, user=admin_user)
    response = post_json(
        named, reverse("agenda:place_idea", args=[idea.pk]), {"start": to_wall_clock(at(2, 12))}
    )
    assert response.status_code == 403
    assert not idea.events.exists()


def test_events_are_read_only_for_members(named, event):
    data = named.get(reverse("agenda:events_json")).json()
    assert [e["editable"] for e in data] == [False]
    body = named.get(reverse("agenda:calendar")).content.decode()
    assert "Proposer un événement" in body
    assert f'href="{reverse("agenda:new")}"' not in body
    assert '"canCreate": false' in body


def test_member_still_proposes_an_idea_with_a_slot(named, at):
    """Déposer une idée reste ouvert : avec un créneau précis, elle est placée en provisoire
    (IDE-2), comme une proposition."""
    response = named.post(
        reverse("ideas:new"),
        {
            "title": "Atelier",
            "kind": "event",
            "duration_minutes": "120",
            "slot1_date": at(2, 14).date().isoformat(),
            "slot1_time": "14:00",
            "author_name": "Paul",
        },
    )
    assert response.status_code == 302
    assert Event.objects.get().status == Event.Status.PROVISIONAL


def test_agenda_manager_still_edits(client, members_cannot_edit, make_manager, event, at):
    login_verified(client, make_manager("manage_agenda"))
    assert client.get(reverse("agenda:new")).status_code == 200
    response = post_json(
        client,
        reverse("agenda:move", args=[event.pk]),
        {
            "start": to_wall_clock(at(2, 10)),
            "end": to_wall_clock(at(2, 12)),
            "revision": event.revision,
        },
    )
    assert response.json()["ok"] is True


def test_other_manager_cannot_edit(client, members_cannot_edit, make_manager):
    """Un droit d'un autre domaine ne suffit pas (ACC-5)."""
    login_verified(client, make_manager("moderate"))
    assert client.get(reverse("agenda:new")).status_code == 302
