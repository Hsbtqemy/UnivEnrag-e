"""Menu « Statut », événements masqués, suppression définitive (décision 26)."""

import pytest
from django.urls import reverse

from apps.actors.services import get_or_create_for_name
from apps.agenda import ical, services
from apps.agenda.models import Event, EventChange
from apps.audit.models import AuditLog
from apps.ideas import services as ideas_services
from apps.ideas.models import Idea
from apps.polls.models import Poll
from conftest import login_verified

pytestmark = pytest.mark.django_db

S = Event.Status


@pytest.fixture
def event(at, room):
    return services.create(
        actor=get_or_create_for_name("Marie"),
        title="Séminaire",
        start=at(1, 10),
        end=at(1, 12),
        room=room,
    )


@pytest.fixture
def agenda_manager(make_manager):
    return make_manager("manage_agenda")


def set_status(event, status, user, **kwargs):
    event.refresh_from_db()
    return services.set_status(event, status, user=user, revision=event.revision, **kwargs)


# --- Le menu : n'importe quel statut vers n'importe quel autre ----------------------------


def test_any_status_to_any_other(event, agenda_manager):
    assert event.status == S.CONFIRMED
    for status in [S.RESCHEDULING, S.PROVISIONAL, S.CANCELLED, S.PROVISIONAL, S.HIDDEN]:
        event = set_status(event, status, agenda_manager)
        assert Event.all_objects.get(pk=event.pk).status == status
    event = set_status(event, S.CONFIRMED, agenda_manager)
    assert event.status == S.CONFIRMED and event.confirmed_by == agenda_manager


def test_status_change_is_in_history_and_journal(event, agenda_manager):
    set_status(event, S.RESCHEDULING, agenda_manager)
    change = event.changes.first()
    assert change.action == EventChange.Action.STATUS
    assert change.changes["status"] == ["confirmed", "rescheduling"]
    assert AuditLog.objects.filter(action="agenda.event_status_changed").exists()
    set_status(event, S.CANCELLED, agenda_manager)
    assert event.changes.first().action == EventChange.Action.CANCELLED


def test_only_agenda_manager_changes_status(event, make_manager):
    with pytest.raises(services.EventError):
        set_status(event, S.CANCELLED, make_manager("manage_public"))
    with pytest.raises(services.EventError):
        set_status(event, S.CANCELLED, None)


def test_stale_revision_is_refused(event, agenda_manager):
    with pytest.raises(services.StaleRevisionError):
        services.set_status(event, S.CANCELLED, user=agenda_manager, revision=event.revision - 1)


def test_unknown_status_is_refused(event, agenda_manager):
    with pytest.raises(services.EventError):
        set_status(event, "supprime", agenda_manager)


def test_back_to_confirmed_checks_the_room(event, at, room, agenda_manager, make_manager):
    set_status(event, S.RESCHEDULING, agenda_manager)
    # La salle est libérée : un autre peut la prendre (CLAUDE.md SAL-2).
    services.create(
        actor=get_or_create_for_name("Inès"),
        title="Atelier",
        start=at(1, 9),
        end=at(1, 11),
        room=room,
    )
    with pytest.raises(services.RoomConflictError):
        set_status(event, S.CONFIRMED, agenda_manager)
    both = make_manager("manage_agenda", "manage_rooms", username="salles")
    event = set_status(event, S.CONFIRMED, both, override=True)
    assert event.status == S.CONFIRMED
    assert AuditLog.objects.filter(action="rooms.derogation").exists()


def test_cancelled_event_can_be_brought_back(event, agenda_manager):
    services.cancel(event, actor=event.owner, revision=event.revision)
    event = set_status(event, S.PROVISIONAL, agenda_manager)
    assert event.status == S.PROVISIONAL
    # Plus barré : il se modifie de nouveau.
    event = services.update(
        event,
        actor=event.owner,
        revision=event.revision,
        title="Séminaire (reporté)",
        start=event.start,
        end=event.end,
        room=event.room,
    )
    assert event.title == "Séminaire (reporté)"


def test_closed_events_are_neither_edited_nor_moved(event, agenda_manager):
    for status in [S.CANCELLED, S.HIDDEN]:
        event = set_status(event, status, agenda_manager)
        with pytest.raises(services.EventError):
            services.move(
                event,
                start=event.start,
                end=event.end,
                room=None,
                revision=event.revision,
                user=agenda_manager,
            )


def test_quick_confirm_still_refuses_cancelled(event, agenda_manager):
    set_status(event, S.CANCELLED, agenda_manager)
    with pytest.raises(services.EventError, match="annulé"):
        services.confirm(event, user=agenda_manager)


# --- À reprogrammer ---------------------------------------------------------------------


def test_rescheduling_is_never_public(event, agenda_manager):
    services.set_public(event, is_public=True, user=agenda_manager)
    assert event in ical.public_events()
    set_status(event, S.RESCHEDULING, agenda_manager)
    assert event not in ical.public_events()


def test_rescheduling_stays_in_member_agenda_and_programming(member_client, event, agenda_manager):
    set_status(event, S.RESCHEDULING, agenda_manager)
    data = member_client.get(reverse("agenda:events_json")).json()
    assert [e["extendedProps"]["statusLabel"] for e in data] == ["À reprogrammer"]
    programming = member_client.get(reverse("agenda:programming_events")).json()
    assert [e["id"] for e in programming] == [str(event.pk)]
    feed = ical.build_calendar(
        ical.member_events(),
        base_url="https://exemple.org",
        name="Agenda",
        detail_path=lambda e: "/",
        with_visio=True,
    ).decode()
    assert "À reprogrammer : Séminaire" in feed


def test_idea_goes_back_to_preparing(make_idea, at, admin_user, agenda_manager):
    idea = make_idea(slots=[{"start": at(1, 10)}])
    ideas_services.accept(idea, user=admin_user)
    event = idea.events.get()
    services.confirm(event, user=agenda_manager)
    idea.refresh_from_db()
    assert idea.status == Idea.Status.PLANNED
    set_status(event, S.RESCHEDULING, agenda_manager)
    idea.refresh_from_db()
    assert idea.status == Idea.Status.PREPARING


# --- Masqué -----------------------------------------------------------------------------


def test_hidden_event_disappears_everywhere(member_client, event, agenda_manager):
    services.set_public(event, is_public=True, user=agenda_manager)
    set_status(event, S.HIDDEN, agenda_manager)
    assert not Event.objects.filter(pk=event.pk).exists()
    assert Event.all_objects.filter(pk=event.pk).exists()
    assert event not in ical.public_events()
    assert event not in ical.member_events()
    assert member_client.get(reverse("agenda:events_json")).json() == []
    assert member_client.get(reverse("agenda:programming_events")).json() == []
    assert member_client.get(reverse("agenda:detail", args=[event.pk])).status_code == 404
    assert "Séminaire" not in member_client.get(reverse("agenda:public_board")).content.decode()


def test_manager_sees_hidden_event_and_list(client, event, agenda_manager):
    set_status(event, S.HIDDEN, agenda_manager)
    login_verified(client, agenda_manager)
    listing = client.get(reverse("agenda:hidden_list")).content.decode()
    assert "Séminaire" in listing
    page = client.get(reverse("agenda:detail", args=[event.pk])).content.decode()
    assert "est <strong>masqué</strong>" in page
    assert "Événements masqués" in client.get(reverse("accounts:gestion_home")).content.decode()


def test_hidden_idea_event_puts_idea_back_to_place(make_idea, at, admin_user, agenda_manager):
    idea = make_idea(slots=[{"start": at(1, 10)}])
    ideas_services.accept(idea, user=admin_user)
    assert idea not in Idea.objects.to_place()
    set_status(idea.events.get(), S.HIDDEN, agenda_manager)
    assert idea in Idea.objects.to_place()


# --- Le formulaire de la fiche -----------------------------------------------------------


def test_status_menu_on_detail_page(client, event, agenda_manager):
    login_verified(client, agenda_manager)
    page = client.get(reverse("agenda:detail", args=[event.pk])).content.decode()
    assert 'name="status"' in page and "Supprimer définitivement" in page
    response = client.post(
        reverse("agenda:set_status", args=[event.pk]),
        {"status": "rescheduling", "revision": event.revision},
    )
    assert response.status_code == 302
    event.refresh_from_db()
    assert event.status == S.RESCHEDULING


def test_members_have_no_status_menu(member_client, event):
    page = member_client.get(reverse("agenda:detail", args=[event.pk])).content.decode()
    assert 'name="status"' not in page and "Supprimer" not in page
    assert "Annuler l'événement" in page
    for name in ["agenda:set_status", "agenda:delete"]:
        response = member_client.post(reverse(name, args=[event.pk]), {"status": "hidden"})
        assert response.status_code == 302 and "/gestion/admin/login/" in response["Location"]
    event.refresh_from_db()
    assert event.status == S.CONFIRMED
    assert member_client.get(reverse("agenda:hidden_list")).status_code == 302


# --- Suppression définitive ------------------------------------------------------------


def test_delete_asks_for_confirmation_then_deletes(client, event, agenda_manager):
    login_verified(client, agenda_manager)
    url = reverse("agenda:delete", args=[event.pk])
    page = client.get(url).content.decode()
    assert "La suppression est définitive" in page
    assert Event.objects.filter(pk=event.pk).exists()
    response = client.post(url)
    assert response.status_code == 302
    assert not Event.all_objects.filter(pk=event.pk).exists()
    assert not EventChange.objects.filter(event_id=event.pk).exists()
    entry = AuditLog.objects.get(action="agenda.event_deleted")
    assert entry.details["title"] == "Séminaire" and entry.details["status"] == "confirmed"
    # Le journal ne garde aucun nom de participant (décision 17).
    assert "Marie" not in str(entry.details)


def test_delete_hidden_event(event, agenda_manager):
    set_status(event, S.HIDDEN, agenda_manager)
    services.delete(event, user=agenda_manager)
    assert not Event.all_objects.exists()


def test_only_agenda_manager_deletes(event, make_manager):
    with pytest.raises(services.EventError):
        services.delete(event, user=make_manager("manage_public", "moderate"))
    assert Event.objects.filter(pk=event.pk).exists()


def test_delete_updates_idea_and_keeps_poll(make_idea, at, admin_user, agenda_manager):
    idea = make_idea(slots=[{"start": at(1, 10)}])
    ideas_services.accept(idea, user=admin_user)
    event = idea.events.get()
    services.confirm(event, user=agenda_manager)
    poll = Poll.objects.create(owner=event.owner, title="Quand ?", event=event)
    services.delete(event, user=agenda_manager)
    idea.refresh_from_db()
    poll.refresh_from_db()
    assert idea.status == Idea.Status.PREPARING
    assert idea in Idea.objects.to_place()
    assert poll.event is None


# --- Admin Django : le statut ne s'y change pas ------------------------------------------


def test_admin_shows_hidden_but_cannot_change_status(admin_client, event, admin_user):
    set_status(event, S.HIDDEN, admin_user)
    changelist = admin_client.get(reverse("admin:agenda_event_changelist")).content.decode()
    assert "Séminaire" in changelist
    form = admin_client.get(reverse("admin:agenda_event_change", args=[event.pk]))
    assert 'name="status"' not in form.content.decode()
    assert form.context["has_delete_permission"] is False
