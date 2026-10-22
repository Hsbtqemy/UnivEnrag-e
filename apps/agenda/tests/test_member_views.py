"""Parcours des membres dans l'agenda : formulaire, glisser-déposer, gestion."""

import json
from urllib.parse import unquote

import pytest
from django.urls import reverse

from apps.actors.resolvers import NAME_COOKIE
from apps.actors.services import get_or_create_for_name
from apps.agenda import services
from apps.agenda.models import Event
from apps.core.dates import to_wall_clock
from conftest import login_verified

pytestmark = pytest.mark.django_db


def form_data(at, **overrides):
    start = at(1, 14)
    data = {
        "title": "Assemblée",
        "day": start.date().isoformat(),
        "start_time": "14:00",
        "end_time": "16:00",
        "room": "",
        "place_text": "",
        "description": "",
        "visio_link": "",
        "author_name": "Inès",
    }
    data.update(overrides)
    return data


@pytest.fixture
def event(at, room):
    return services.create(
        actor=get_or_create_for_name("Marie"),
        title="Séminaire",
        start=at(1, 10),
        end=at(1, 12),
        room=room,
    )


def test_agenda_requires_access_code(client, site):
    assert client.get(reverse("agenda:calendar")).status_code == 302


def test_create_event_with_name_only(member_client, at):
    response = member_client.post(reverse("agenda:new"), form_data(at))
    assert response.status_code == 302
    event = Event.objects.get()
    assert (event.title, event.owner.display_name, event.status) == (
        "Assemblée",
        "Inès",
        "confirmed",
    )
    assert unquote(member_client.cookies[NAME_COOKIE].value) == "Inès"


def test_new_form_is_prefilled_from_clicked_slot(member_client, room):
    response = member_client.get(
        reverse("agenda:new")
        + f"?debut=2030-03-04T09:30:00&fin=2030-03-04T11:00:00&salle={room.pk}"
    )
    form = response.context["form"]
    assert str(form.initial["day"]) == "2030-03-04"
    assert form.initial["start_time"].strftime("%H:%M") == "09:30"
    assert form.initial["end_time"].strftime("%H:%M") == "11:00"
    assert form.initial["room"] == room
    # Les champs date/heure HTML exigent le format ISO, quelle que soit la langue du site.
    html = response.content.decode()
    assert 'value="2030-03-04"' in html
    assert 'value="09:30"' in html


def test_room_conflict_is_shown_in_form(member_client, at, event, room):
    response = member_client.post(
        reverse("agenda:new"),
        form_data(
            at, start_time="11:00", end_time="13:00", day=at(1, 10).date().isoformat(), room=room.pk
        ),
    )
    assert response.status_code == 200
    assert "déjà occupée" in response.content.decode()
    assert Event.objects.count() == 1


def test_end_before_start_is_refused(member_client, at):
    response = member_client.post(reverse("agenda:new"), form_data(at, end_time="13:00"))
    assert response.status_code == 200
    assert not Event.objects.exists()


def test_duplicate_prefills_form(member_client, event):
    response = member_client.get(reverse("agenda:new") + f"?depuis={event.pk}")
    assert response.context["form"].initial["title"] == "Séminaire"


def test_edit_keeps_owner_and_records_editor(member_client, event, at):
    data = form_data(
        at,
        title="Séminaire modifié",
        author_name="Paul",
        revision=event.revision,
        day=at(1, 10).date().isoformat(),
        start_time="10:00",
        end_time="12:00",
    )
    response = member_client.post(reverse("agenda:edit", args=[event.pk]), data)
    assert response.status_code == 302
    event.refresh_from_db()
    assert event.title == "Séminaire modifié"
    assert event.owner.display_name == "Marie"
    assert event.changes.first().actor.display_name == "Paul"


def test_edit_with_stale_revision_shows_error(member_client, event, at):
    data = form_data(at, revision=event.revision - 1 if event.revision > 1 else 99)
    response = member_client.post(reverse("agenda:edit", args=[event.pk]), data)
    assert response.status_code == 200
    assert "modifié entre-temps" in response.content.decode()


def test_cancel_keeps_event_visible(member_client, event):
    member_client.post(
        reverse("agenda:cancel", args=[event.pk]),
        {"revision": event.revision, "author_name": "Paul"},
    )
    event.refresh_from_db()
    assert event.status == "cancelled"
    data = member_client.get(reverse("agenda:events_json")).json()
    assert data[0]["classNames"][0] == "ev-cancelled"


def test_drag_and_drop_needs_a_name(member_client, event, at):
    url = reverse("agenda:move", args=[event.pk])
    payload = {
        "start": to_wall_clock(at(2, 10)),
        "end": to_wall_clock(at(2, 12)),
        "revision": event.revision,
    }
    response = member_client.post(url, json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    member_client.cookies[NAME_COOKIE] = "Paul"
    response = member_client.post(url, json.dumps(payload), content_type="application/json")
    assert response.json()["ok"] is True
    event.refresh_from_db()
    assert event.start == at(2, 10)
    assert event.room is not None  # le glisser-déposer ne change pas la salle


def test_drag_into_taken_room_is_refused(member_client, event, at, room):
    other = services.create(
        actor=event.owner, title="Autre", start=at(2, 10), end=at(2, 12), room=room
    )
    member_client.cookies[NAME_COOKIE] = "Paul"
    response = member_client.post(
        reverse("agenda:move", args=[other.pk]),
        json.dumps(
            {
                "start": to_wall_clock(at(1, 11)),
                "end": to_wall_clock(at(1, 13)),
                "revision": other.revision,
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 409


def test_locked_event_cannot_be_dragged_by_member(member_client, event, at, admin_user):
    event = services.set_locked(event, locked=True, user=admin_user)
    member_client.cookies[NAME_COOKIE] = "Paul"
    data = member_client.get(reverse("agenda:events_json")).json()
    assert data[0]["editable"] is False
    response = member_client.post(
        reverse("agenda:move", args=[event.pk]),
        json.dumps(
            {
                "start": to_wall_clock(at(2, 10)),
                "end": to_wall_clock(at(2, 12)),
                "revision": event.revision,
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 409


def test_check_endpoint_reports_conflicts(member_client, event, at, room):
    response = member_client.get(
        reverse("agenda:check"),
        {"start": to_wall_clock(at(1, 11)), "end": to_wall_clock(at(1, 13)), "room": room.pk},
    )
    assert response.json()["conflicts"]
    response = member_client.get(
        reverse("agenda:check"),
        {
            "start": to_wall_clock(at(1, 11)),
            "end": to_wall_clock(at(1, 13)),
            "room": room.pk,
            "exclude": event.pk,
        },
    )
    assert response.json() == {"conflicts": [], "closed": "", "approval": False, "warnings": []}


def test_member_cannot_use_manager_actions(member_client, event):
    for name in ["agenda:lock", "agenda:confirm"]:
        response = member_client.post(reverse(name, args=[event.pk]))
        assert response.status_code == 302 and "/gestion/admin/login/" in response["Location"]
    assert (
        member_client.post(reverse("agenda:publish", args=[event.pk]), {"public": "1"}).status_code
        == 403
    )


def test_detail_and_feed_never_show_owner_email(member_client, make_idea, at, admin_user):
    from apps.ideas import services as ideas_services

    idea = make_idea(slots=[{"start": at(1, 10)}], email="secret@univ.example")
    ideas_services.accept(idea, user=admin_user)
    assert (
        "secret@univ.example"
        not in member_client.get(reverse("agenda:detail", args=[idea.event.pk])).content.decode()
    )
    assert (
        "secret@univ.example"
        not in member_client.get(reverse("agenda:events_json")).content.decode()
    )


def test_manager_restores_from_detail_page(client, event, at, admin_user):
    created = event.changes.get()
    services.update(
        event,
        actor=event.owner,
        revision=event.revision,
        title="Erreur",
        start=event.start,
        end=event.end,
        room=event.room,
    )
    login_verified(client, admin_user)
    page = client.get(reverse("agenda:detail", args=[event.pk])).content.decode()
    assert "Revenir à cette version" in page
    client.post(reverse("agenda:restore", args=[event.pk, created.pk]))
    event.refresh_from_db()
    assert event.title == "Séminaire"


def test_public_requests_queue(client, at, make_manager):
    services.create(
        actor=get_or_create_for_name("Inès"),
        title="Ciné-débat",
        start=at(1, 18),
        end=at(1, 20),
        wants_public=True,
    )
    login_verified(client, make_manager("manage_public"))
    page = client.get(reverse("agenda:public_requests")).content.decode()
    assert "Ciné-débat" in page
    event = Event.objects.get()
    client.post(
        reverse("agenda:publish", args=[event.pk]),
        {"public": "1", "next": "https://ailleurs.example/"},
    )
    event.refresh_from_db()
    assert event.is_public
    assert "Ciné-débat" in client.get(reverse("agenda:public_list")).content.decode()
