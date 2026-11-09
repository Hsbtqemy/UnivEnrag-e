"""Sondages fermés (`POLLS_ENABLED`, décision du porteur du projet du 09/11/2026) : le code
reste, plus aucun accès."""

import pytest
from django.urls import reverse

from apps.actors.services import get_or_create_for_name
from apps.polls import services

pytestmark = pytest.mark.django_db


@pytest.fixture
def poll(at, settings):
    poll = services.create(
        actor=get_or_create_for_name("Marie"),
        title="Réunion du groupe",
        slots=[(at(1, 10), at(1, 12)), (at(2, 14), at(2, 16))],
    )
    settings.POLLS_ENABLED = False
    return poll


def test_poll_pages_are_gone(member_client, poll):
    for url in [
        reverse("polls:list"),
        reverse("polls:new"),
        reverse("polls:detail", args=[poll.pk]),
    ]:
        assert member_client.get(url).status_code == 404
    response = member_client.post(reverse("polls:detail", args=[poll.pk]), {"author_name": "Paul"})
    assert response.status_code == 404


def test_no_link_left(member_client, poll):
    home = member_client.get(reverse("agenda:home")).content.decode()
    assert "/sondages/" not in home and "Sondages de dates" not in home
    help_page = member_client.get(reverse("core:help")).content.decode()
    assert "/sondages/" not in help_page and "Trouver une date" not in help_page


def test_fixing_a_slot_no_longer_works(member_client, poll, at):
    slot = poll.slots.first()
    form_page = member_client.get(reverse("agenda:new") + f"?sondage={poll.pk}&creneau={slot.pk}")
    assert form_page.context["form"].initial.get("title") != "Réunion du groupe"
    member_client.post(
        reverse("agenda:new"),
        {
            "sondage": poll.pk,
            "title": "Réunion",
            "day": at(1, 0).date().isoformat(),
            "start_time": "10:00",
            "end_time": "12:00",
            "author_name": "Paul",
        },
    )
    poll.refresh_from_db()
    assert not poll.is_closed and poll.event is None
