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
    assert "Atelier fini" not in panel(body, "jour")
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


def panel(body: str, view: str) -> str:
    """Le HTML d'une des trois vues du grand écran."""
    start = body.index(f'data-view="{view}"')
    following = [body.find(f'data-view="{v}"', start + 1) for v in ("semaine", "mois")]
    ends = [i for i in following if i > start]
    return body[start : min(ends)] if ends else body[start:]


def test_upcoming_is_limited(client, frozen, add):
    for offset in range(1, 12):
        add(f"Rendez-vous {offset:02d}", NOW + timedelta(days=offset))
    day = panel(client.get(URL).content.decode(), "jour")
    assert "Rendez-vous 08" in day
    assert "Rendez-vous 09" not in day


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


# --- Vues qui tournent : 7 jours et le mois ------------------------------------------------


def test_week_view_lists_the_next_seven_days(client, frozen, add):
    add("Ciné-débat", NOW + timedelta(days=3))
    add("Trop loin pour la semaine", NOW + timedelta(days=8))
    week = panel(client.get(URL).content.decode(), "semaine")
    assert "Les 7 prochains jours" in week
    assert "Ciné-débat" in week
    assert "Trop loin pour la semaine" not in week
    assert "data-empty" not in week


def test_busy_day_in_week_view_says_how_many_more(client, frozen, add, other_room):
    tomorrow = NOW.replace(hour=8) + timedelta(days=1)
    for hour in range(8):
        add(f"Atelier {hour}", tomorrow + timedelta(hours=hour), hours=1, place=None)
    week = panel(client.get(URL).content.decode(), "semaine")
    assert "Atelier 5" in week
    assert "Atelier 6" not in week
    assert "+ 2 autres" in week


def test_month_view_covers_five_weeks_from_monday(client, frozen, add):
    add("Dans trois semaines", NOW + timedelta(days=20))
    add("Dans six semaines", NOW + timedelta(days=42))
    month = panel(client.get(URL).content.decode(), "mois")
    assert "Dans trois semaines" in month
    assert "Dans six semaines" not in month
    assert "9 novembre" in month  # le lundi de la semaine en cours, en premier


def test_empty_views_are_marked_to_be_skipped(client, frozen):
    body = client.get(URL).content.decode()
    assert "data-empty" in panel(body, "semaine")
    assert "data-empty" in panel(body, "mois")


def test_views_and_duration_come_from_the_address(client, frozen):
    response = client.get(f"{URL}?vues=mois,jour,inconnue&duree=500")
    config = response.context["config"]
    assert config["views"] == ["mois", "jour"]
    assert config["duration"] == 120


def test_default_views_and_duration(client, frozen):
    config = client.get(f"{URL}?duree=abc").context["config"]
    assert config["views"] == ["jour", "semaine", "mois"]
    assert config["duration"] == 20


@pytest.mark.parametrize("name", ["agenda:public_list", "agenda:calendar"])
def test_agendas_link_to_the_board(client, member_client, name):
    browser = member_client if name == "agenda:calendar" else client
    assert URL in browser.get(reverse(name)).content.decode()
