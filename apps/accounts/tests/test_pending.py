"""Page `/gestion/` : ce qui attend, selon les droits du compte (CLAUDE.md ACC-5)."""

import pytest
from django.urls import reverse

from apps.accounts import pending
from apps.actors.services import get_or_create_for_name
from apps.agenda import services as agenda_services
from apps.public.models import ContactMessage
from conftest import login_verified

pytestmark = pytest.mark.django_db


@pytest.fixture
def queues(make_idea, at):
    make_idea("Atelier")  # une proposition extérieure, en attente de modération
    agenda_services.create(
        actor=get_or_create_for_name("Inès"),
        title="Assemblée",
        start=at(1, 14),
        end=at(1, 16),
        wants_public=True,
    )
    ContactMessage.objects.create(sender=get_or_create_for_name("Sam"), message="Bonjour")


def test_superuser_sees_every_queue(admin_user, queues):
    labels = pending.for_user(admin_user)
    assert str(labels["moderation"]) == "1 proposition à modérer"
    assert str(labels["publication"]) == "1 demande de publication"
    assert str(labels["contact"]) == "1 message à traiter"
    assert "rooms" not in labels  # file vide : rien à dire


def test_manager_sees_only_their_queues(make_manager, queues):
    labels = pending.for_user(make_manager("moderate"))
    assert list(labels) == ["moderation"]


def test_gestion_home_shows_counts(client, make_manager, queues):
    login_verified(client, make_manager("moderate"))
    body = client.get(reverse("accounts:gestion_home")).content.decode()
    assert "À traiter" in body
    assert "1 proposition à modérer" in body
    assert "demande de publication" not in body


def test_gestion_home_says_when_nothing_waits(admin_client):
    body = admin_client.get(reverse("accounts:gestion_home")).content.decode()
    assert "Rien en attente" in body


# --- Pastille de l'onglet « Gestion » ------------------------------------------------------


def test_total_counts_only_the_queues_of_the_account(admin_user, make_manager, queues):
    assert pending.total_for(admin_user) == 3
    assert pending.total_for(make_manager("moderate")) == 1
    assert pending.total_for(make_manager(username="sans-droit")) == 0


def test_gestion_tab_shows_the_badge(client, make_manager, queues, site):
    login_verified(client, make_manager("moderate"))
    html = client.get(reverse("agenda:public_list")).content.decode()
    assert 'class="nav__badge" aria-hidden="true">1<' in html
    assert "(1 à traiter)" in html


def test_no_badge_when_nothing_waits(admin_client):
    html = admin_client.get(reverse("accounts:gestion_home")).content.decode()
    assert "nav__badge" not in html


def test_visitors_and_members_never_see_a_badge(client, member_client, queues):
    assert "nav__badge" not in client.get(reverse("public:home")).content.decode()
    assert "nav__badge" not in member_client.get(reverse("agenda:calendar")).content.decode()
