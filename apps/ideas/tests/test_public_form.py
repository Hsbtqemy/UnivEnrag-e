"""Formulaire public : enregistrement, anti-spam, lien de suivi."""

import pytest
from django.core import signing
from django.urls import reverse

from apps.core.antispam import SALT
from apps.ideas.models import Idea

pytestmark = pytest.mark.django_db


def form_data(token, at, **overrides):
    start = at(1, 14)
    data = {
        "owner_name": "Camille Martin",
        "owner_email": "camille.martin@univ.example",
        "title": "Séminaire",
        "description": "Une description.",
        "duration_minutes": "120",
        "slot1_date": start.date().isoformat(),
        "slot1_time": "14:00",
        "slot2_period": "Un jeudi après-midi",
        "rendered_at": token,
        "website": "",
    }
    data.update(overrides)
    return data


def test_valid_submission_redirects_to_tracking_page(client, old_enough_token, at):
    response = client.post(reverse("ideas:propose"), form_data(old_enough_token, at))
    idea = Idea.objects.get()
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("ideas:track", args=[idea.tracking_token]))
    assert idea.slots.count() == 2
    page = client.get(response["Location"])
    assert "Gardez le lien de cette page" in page.content.decode()


def test_honeypot_is_silently_ignored(client, old_enough_token, at):
    response = client.post(
        reverse("ideas:propose"), form_data(old_enough_token, at, website="http://spam")
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("ideas:sent")
    assert not Idea.objects.exists()


def test_too_fast_submission_is_silently_ignored(client, at):
    fresh = signing.TimestampSigner(salt=SALT).sign("form")
    client.post(reverse("ideas:propose"), form_data(fresh, at))
    assert not Idea.objects.exists()


def test_forged_token_is_silently_ignored(client, at):
    client.post(reverse("ideas:propose"), form_data("form:faux:jeton", at))
    assert not Idea.objects.exists()


def test_rate_limit_after_five_submissions(client, old_enough_token, at):
    for _ in range(5):
        client.post(reverse("ideas:propose"), form_data(old_enough_token, at))
    response = client.post(reverse("ideas:propose"), form_data(old_enough_token, at))
    assert response.status_code == 429
    assert Idea.objects.count() == 5


def test_past_slot_is_refused(client, old_enough_token, at):
    response = client.post(
        reverse("ideas:propose"), form_data(old_enough_token, at, slot1_date="2020-01-06")
    )
    assert response.status_code == 200
    assert "Ce créneau est déjà passé." in response.content.decode()
    assert not Idea.objects.exists()


def test_too_many_links_are_refused(client, old_enough_token, at):
    links = " ".join(f"https://exemple.org/{i}" for i in range(4))
    response = client.post(
        reverse("ideas:propose"), form_data(old_enough_token, at, description=links)
    )
    assert response.status_code == 200
    assert not Idea.objects.exists()


def test_tracking_page_requires_exact_token(client):
    response = client.get(reverse("ideas:track", args=["00000000-0000-0000-0000-000000000000"]))
    assert response.status_code == 404


def test_tracking_page_shows_refusal_reason(client, make_idea, admin_user):
    from apps.ideas import services

    idea = make_idea()
    services.refuse(idea, user=admin_user, reason="Hors sujet.")
    page = client.get(reverse("ideas:track", args=[idea.tracking_token])).content.decode()
    assert "Non retenue" in page and "Hors sujet." in page
    assert "Corriger votre proposition" not in page


def test_moderation_requires_staff(client):
    response = client.get(reverse("ideas:moderation"))
    assert response.status_code == 302
    assert "/gestion/admin/login/" in response["Location"]


def test_extra_slots_and_details_are_folded_on_a_fresh_form(client, site):
    body = client.get(reverse("ideas:propose")).content.decode()
    assert '<details class="more">' in body
    assert "<details class=\"more\" open>" not in body
    assert "Créneau souhaité" in body


def test_folded_sections_reopen_when_already_filled(client, old_enough_token, at):
    """Après une erreur, ce que la personne avait déplié et rempli reste visible."""
    data = form_data(old_enough_token, at, title="", audience="Étudiants")
    body = client.post(reverse("ideas:propose"), data).content.decode()
    assert body.count('<details class="more" open>') == 2
    assert 'value="Un jeudi après-midi"' in body


def test_tracking_page_offers_to_copy_the_link(client, old_enough_token, at):
    response = client.post(reverse("ideas:propose"), form_data(old_enough_token, at))
    page = client.get(response["Location"]).content.decode()
    assert 'id="copier-lien"' in page
    assert "js/tracking" in page
