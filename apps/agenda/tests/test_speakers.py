"""Intervenants d'un événement : avertissement (AGE-7), pré-remplissage (IDE-3), PUB-1."""

import pytest
from django.urls import reverse

from apps.actors.services import get_or_create_for_name
from apps.agenda import history, services
from apps.agenda.models import Event, EventChange
from apps.core.dates import to_wall_clock
from apps.ideas import services as ideas_services

pytestmark = pytest.mark.django_db


@pytest.fixture
def marie(db):
    return get_or_create_for_name("Marie")


def make(actor, title, start, end, **extra):
    return services.create(actor=actor, title=title, start=start, end=end, **extra)


def test_same_speaker_at_the_same_time_warns_whatever_the_room(marie, at, room, other_room):
    make(marie, "Séminaire", at(1, 10), at(1, 12), room=room, speakers="Hélène Martin, Paul")
    event = make(
        marie, "Table ronde", at(1, 11), at(1, 13), room=other_room, speakers="helene martin"
    )
    [warning] = services.warnings_for(event)
    assert warning.startswith("Mêmes intervenants que « Séminaire »")
    assert warning.endswith(": helene martin")


def test_no_speaker_warning_back_to_back_or_cancelled(marie, at):
    first = make(marie, "Avant", at(1, 10), at(1, 12), speakers="Paul")
    later = make(marie, "Après", at(1, 12), at(1, 13), speakers="Paul")
    assert services.warnings_for(later) == []
    services.cancel(first, actor=marie, revision=first.revision)
    same_time = make(marie, "Même heure", at(1, 10), at(1, 11), speakers="Paul")
    assert services.warnings_for(same_time) == []


def test_live_check_reports_speakers_without_a_room(member_client, marie, at):
    make(marie, "Séminaire", at(1, 10), at(1, 12), speakers="Paul")
    data = member_client.get(
        reverse("agenda:check"),
        {"start": to_wall_clock(at(1, 11)), "end": to_wall_clock(at(1, 12)), "speakers": "Paul"},
    ).json()
    assert data["speakers"] and data["conflicts"] == []


def test_speakers_come_from_the_idea(marie, at):
    idea = ideas_services.create(
        actor=marie, title="Atelier", speakers_text="Léa, Hugo", slots=[{"start": at(1, 10)}]
    )
    assert idea.events.get().speakers == "Léa, Hugo"


def test_speakers_are_public_only_when_chosen(client, marie, at, admin_user):
    event = make(marie, "Conférence", at(1, 10), at(1, 12), speakers="Une historienne")
    services.set_public(event, is_public=True, user=admin_user)
    url = reverse("agenda:public_detail", args=[event.pk])
    assert "Une historienne" not in client.get(url).content.decode()
    assert "Une historienne" not in client.get(reverse("agenda:public_ics")).content.decode()
    Event.objects.filter(pk=event.pk).update(speakers_public=True)
    assert "Une historienne" in client.get(url).content.decode()
    assert "Une historienne" in client.get(reverse("agenda:public_ics")).content.decode()


def test_restoring_a_version_older_than_a_field_keeps_its_value(marie, at, admin_user):
    event = make(marie, "Séminaire", at(1, 10), at(1, 12), speakers="Paul")
    old = event.changes.get()
    # Une version enregistrée avant l'ajout des intervenants n'a pas ce champ.
    EventChange.objects.filter(pk=old.pk).update(
        snapshot={k: v for k, v in old.snapshot.items() if k not in ("speakers", "space")}
    )
    old.refresh_from_db()
    assert "speakers" not in history.restore_values(old)
    services.restore(event, old, user=admin_user)
    event.refresh_from_db()
    assert event.speakers == "Paul"
