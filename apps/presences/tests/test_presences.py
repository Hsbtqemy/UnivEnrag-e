"""Présences annoncées : « je serai là », par demi-journée."""

from datetime import date, timedelta

import pytest
from django.urls import reverse

from apps.actors.resolvers import NAME_COOKIE
from apps.actors.services import get_or_create_for_name
from apps.presences import services
from apps.presences.models import Presence

pytestmark = pytest.mark.django_db

MONDAY = date(2030, 3, 4)


def test_week_start_is_monday():
    assert services.week_start(date(2030, 3, 7)) == MONDAY
    assert services.parse_week("2030-03-09") == MONDAY
    assert services.parse_week("n'importe quoi") == services.week_start(date.today())


def test_save_week_replaces_previous_declarations():
    marie = get_or_create_for_name("Marie")
    services.save_week(marie, MONDAY, {(MONDAY, "morning"): "Bât. A", (MONDAY, "afternoon"): ""})
    services.save_week(marie, MONDAY, {(MONDAY + timedelta(days=1), "morning"): "Local"})
    assert list(Presence.objects.values_list("day", "period", "place")) == [
        (MONDAY + timedelta(days=1), "morning", "Local")
    ]


def test_save_week_ignores_days_outside_the_week():
    marie = get_or_create_for_name("Marie")
    count = services.save_week(marie, MONDAY, {(MONDAY + timedelta(days=7), "morning"): ""})
    assert count == 0


def test_previous_week_is_shifted():
    marie = get_or_create_for_name("Marie")
    services.save_week(marie, MONDAY, {(MONDAY, "evening"): "Local"})
    next_monday = MONDAY + timedelta(days=7)
    assert services.previous_week_selections(marie, next_monday) == {
        (next_monday, "evening"): "Local"
    }


def test_board_lists_people_by_half_day():
    services.save_week(get_or_create_for_name("Marie"), MONDAY, {(MONDAY, "morning"): "Bât. A"})
    services.save_week(get_or_create_for_name("Paul"), MONDAY, {(MONDAY, "morning"): ""})
    rows = services.board(MONDAY)
    morning_monday = rows[0][0]
    assert morning_monday.people == [("Marie", "Bât. A"), ("Paul", "")]
    assert services.count_people(MONDAY) == 2


def test_old_presences_are_purged():
    marie = get_or_create_for_name("Marie")
    Presence.objects.create(actor=marie, day=date.today() - timedelta(days=90), period="morning")
    Presence.objects.create(actor=marie, day=date.today(), period="morning")
    assert services.purge() == 1


def test_my_week_form_saves_and_needs_a_name(member_client):
    url = reverse("presences:my_week") + "?semaine=2030-03-04"
    data = {"semaine": "2030-03-04", "p-2030-03-05-afternoon": "on", "lieu-2030-03-05": "Local"}
    response = member_client.post(url, data)
    assert response.status_code == 200  # pas de nom : formulaire réaffiché
    assert not Presence.objects.exists()
    response = member_client.post(url, {**data, "author_name": "Inès"})
    assert response.status_code == 302
    presence = Presence.objects.get()
    assert (presence.actor.display_name, presence.period, presence.place) == (
        "Inès",
        "afternoon",
        "Local",
    )
    page = member_client.get(reverse("presences:board") + "?semaine=2030-03-04").content.decode()
    assert "Inès" in page and "Local" in page


def test_resume_previous_week_prefills_checkboxes(member_client):
    services.save_week(get_or_create_for_name("Inès"), MONDAY, {(MONDAY, "morning"): "Local"})
    member_client.cookies[NAME_COOKIE] = "Inès"
    response = member_client.get(
        reverse("presences:my_week")
        + f"?semaine={(MONDAY + timedelta(days=7)).isoformat()}&reprendre=1"
    )
    html = response.content.decode()
    assert 'name="p-2030-03-11-morning" checked' in html
    assert 'value="Local"' in html


def test_presences_are_internal(client, site):
    assert client.get(reverse("presences:board")).status_code == 302
