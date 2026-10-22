"""Exporter ou imprimer l'agenda (CDC §7) : CSV, .ics, vue imprimable ; PUB-1 et PUB-2."""

import pytest
from django.urls import reverse

from apps.actors.services import get_or_create_for_name
from apps.agenda import services
from apps.ideas import services as ideas_services

pytestmark = pytest.mark.django_db


@pytest.fixture
def agenda(at, room, other_room, admin_user, make_idea):
    marie = get_or_create_for_name("Marie")
    confirmed = services.create(
        actor=marie,
        title="Réunion confirmée",
        start=at(1, 10),
        end=at(1, 11),
        room=room,
        speakers="Une intervenante",
        visio_link="https://visio.example/secret",
    )
    services.set_public(confirmed, is_public=True, user=admin_user)
    cancelled = services.create(
        actor=marie, title="Réunion annulée", start=at(2, 10), end=at(2, 11), room=other_room
    )
    services.cancel(cancelled, actor=marie, revision=cancelled.revision)
    idea = make_idea(
        title="Proposition provisoire", slots=[{"start": at(3, 14)}], email="porteur@univ.example"
    )
    ideas_services.accept(idea, user=admin_user)
    return {"confirmed": confirmed, "cancelled": cancelled, "provisional": idea.events.get()}


def params(at, **extra):
    data = {
        "du": at(0, 0).date().isoformat(),
        "au": at(6, 0).date().isoformat(),
        "provisoires": "on",
    }
    return data | extra


def test_export_page_is_internal(client, site):
    assert client.get(reverse("agenda:export")).status_code == 302


def test_export_form_has_defaults(member_client):
    response = member_client.get(reverse("agenda:export"))
    assert response.status_code == 200
    assert response.context["form"]["provisoires"].value() is True


def test_csv_for_a_spreadsheet(member_client, agenda, at):
    response = member_client.get(reverse("agenda:export"), params(at, format="csv"))
    assert response["Content-Disposition"].startswith('attachment; filename="agenda-')
    body = response.content.decode("utf-8")
    assert body.startswith("﻿Date;Début;Fin;Titre")
    assert "Réunion confirmée" in body and "Proposition provisoire" in body
    assert "Réunion annulée" not in body
    assert "porteur@univ.example" not in body  # PUB-2 : jamais dans un export


def test_cancelled_and_provisional_are_optional(member_client, agenda, at):
    url = reverse("agenda:export")
    with_cancelled = member_client.get(url, params(at, format="csv", annules="on"))
    assert "Réunion annulée" in with_cancelled.content.decode()
    data = params(at, format="csv")
    data.pop("provisoires")
    without_provisional = member_client.get(url, data).content.decode()
    assert "Proposition provisoire" not in without_provisional


def test_room_filter(member_client, agenda, at, other_room):
    body = member_client.get(
        reverse("agenda:export"), params(at, format="csv", annules="on", salle=other_room.pk)
    ).content.decode()
    assert "Réunion annulée" in body and "Réunion confirmée" not in body


def test_ics_download_for_members_keeps_visio(member_client, agenda, at):
    response = member_client.get(reverse("agenda:export"), params(at, format="ics"))
    assert response["Content-Type"].startswith("text/calendar")
    assert response["Content-Disposition"].startswith("attachment;")
    body = response.content.decode()
    assert "Réunion confirmée" in body and "visio.example" in body


def test_print_view_groups_by_day(member_client, agenda, at):
    response = member_client.get(reverse("agenda:export"), params(at, format="imprimer"))
    body = response.content.decode()
    assert response.templates[0].name == "agenda/print.html"
    assert "Réunion confirmée" in body and "Une intervenante" in body
    assert len(response.context["days"]) == 2  # provisoire + confirmé, sans l'annulé


def test_period_longer_than_a_year_is_refused(member_client, at):
    response = member_client.get(
        reverse("agenda:export"), params(at, format="csv", au="2099-01-01")
    )
    assert response.templates[0].name == "agenda/export.html"
    assert response.context["form"].errors["au"]


def test_public_print_and_download_show_public_events_only(client, agenda):
    printed = client.get(reverse("agenda:public_print")).content.decode()
    downloaded = client.get(reverse("agenda:public_download"))
    assert downloaded["Content-Disposition"].startswith("attachment;")
    for body in (printed, downloaded.content.decode()):
        assert "Réunion confirmée" in body
        assert "Proposition provisoire" not in body and "Réunion annulée" not in body
        assert "visio.example" not in body and "porteur@univ.example" not in body
        # Intervenants non publics : absents de l'export public (PUB-1).
        assert "Une intervenante" not in body
