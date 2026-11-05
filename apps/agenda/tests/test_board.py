"""Grand écran /p/affichage/ : seulement le public (PUB-1), le jour suit l'horloge."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.actors.services import get_or_create_for_name
from apps.agenda import services
from apps.presences import services as presences_services

pytestmark = pytest.mark.django_db

PARIS = ZoneInfo("Europe/Paris")
# Un mercredi après-midi.
NOW = datetime(2026, 11, 11, 15, 0, tzinfo=PARIS)
URL = "/p/affichage/"


@pytest.fixture
def frozen(monkeypatch):
    """Fige l'horloge de Django ; `frozen(moment)` la déplace."""
    clock = {"now": NOW}
    monkeypatch.setattr(timezone, "now", lambda: clock["now"])

    def move(moment):
        clock["now"] = moment

    return move


@pytest.fixture
def add(admin_user, room):
    owner = get_or_create_for_name("Camille Porteuse")

    def build(title, start, hours=2, public=True, place=room):
        event = services.create(
            actor=owner,
            user=admin_user,
            title=title,
            start=start,
            end=start + timedelta(hours=hours),
            room=place,
        )
        if public:
            event = services.set_public(event, is_public=True, user=admin_user)
        return event

    return build


def test_reverse_matches_address():
    assert reverse("agenda:public_board") == URL


def test_board_is_public_and_not_cached(client, frozen):
    response = client.get(URL)
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    assert "Mercredi 11 novembre" in response.content.decode()


def test_today_shows_current_and_later_public_events_only(client, frozen, add):
    add("Atelier fini", NOW - timedelta(hours=5))
    add("Débat en cours", NOW - timedelta(hours=1))
    add("Projection du soir", NOW + timedelta(hours=4), place=None)
    add("Réunion interne", NOW + timedelta(hours=1), public=False)
    body = client.get(URL).content.decode()
    assert "Atelier fini" not in body
    assert "Débat en cours" in body
    assert "En cours" in body
    assert "Projection du soir" in body
    assert "Lieu à préciser" in body
    assert "Porté par Camille Porteuse" in body
    assert "Réunion interne" not in body


def test_upcoming_days_are_listed(client, frozen, add):
    add("Ciné-débat", NOW + timedelta(days=2))
    body = client.get(URL).content.decode()
    assert "Pas de rendez-vous public aujourd'hui" in body
    assert "Vendredi 13 novembre" in body
    assert "Ciné-débat" in body


def test_upcoming_is_limited(client, frozen, add):
    for offset in range(1, 12):
        add(f"Rendez-vous {offset:02d}", NOW + timedelta(days=offset))
    body = client.get(URL).content.decode()
    assert "Rendez-vous 08" in body
    assert "Rendez-vous 09" not in body


def test_fragment_is_only_the_content(client, frozen, add):
    add("Débat en cours", NOW - timedelta(hours=1))
    body = client.get(f"{URL}?fragment=1").content.decode()
    assert "Débat en cours" in body
    assert "<html" not in body
    assert "board.js" not in body


def test_day_changes_by_itself(client, frozen, add):
    add("Jeudi matin", NOW + timedelta(hours=18))
    assert "Mercredi 11 novembre" in client.get(f"{URL}?fragment=1").content.decode()
    frozen(NOW + timedelta(hours=10))
    body = client.get(f"{URL}?fragment=1").content.decode()
    assert "Jeudi 12 novembre" in body
    assert "Pas de rendez-vous public aujourd'hui" not in body


def test_today_permanence_without_name(client, frozen):
    marie = get_or_create_for_name("Marie Curie")
    today = NOW.date()
    monday = presences_services.week_start(today)
    presences_services.save_week(marie, monday, {(today, "afternoon"): "Bât. A"}, open_days={today})
    body = client.get(URL).content.decode()
    assert "Permanence aujourd'hui" in body
    assert "Bât. A" in body
    assert "Marie Curie" not in body


@pytest.mark.parametrize(
    ("value", "expected"), [("sombre", 'data-theme="dark"'), ("enrage", 'data-theme="enrage"')]
)
def test_theme_can_be_forced_by_address(client, frozen, value, expected):
    assert expected in client.get(f"{URL}?theme={value}").content.decode()


def test_unknown_theme_is_ignored(client, frozen):
    assert "data-theme" not in client.get(f"{URL}?theme=<script>").content.decode()


def test_qr_code_points_to_public_agenda(client):
    response = client.get(reverse("agenda:public_board_qr"))
    assert response.status_code == 200
    assert response["Content-Type"] == "image/svg+xml"
    assert response.content.startswith(b"<svg")
