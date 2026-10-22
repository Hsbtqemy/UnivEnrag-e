"""Droits des gestionnaires (CLAUDE.md ACC-4, ACC-5)."""

import pytest
from django.urls import reverse

from apps.accounts.capabilities import capabilities_of, has_capability
from conftest import login_verified

pytestmark = pytest.mark.django_db


def test_superuser_has_every_capability(admin_user):
    assert capabilities_of(admin_user) == {
        "manage_votes",
        "manage_agenda",
        "manage_rooms",
        "manage_spaces",
        "moderate",
        "manage_public",
        "export_data",
    }


def test_manager_only_has_checked_capabilities(make_manager):
    manager = make_manager("manage_rooms")
    assert has_capability(manager, "manage_rooms")
    assert not has_capability(manager, "manage_agenda")


def test_inactive_manager_has_nothing(make_manager):
    manager = make_manager("manage_rooms")
    manager.is_active = False
    assert capabilities_of(manager) == set()


def test_unknown_capability_is_an_error(admin_user):
    with pytest.raises(ValueError):
        has_capability(admin_user, "tout_faire")


def test_manager_without_agenda_right_gets_403_on_programming(client, make_manager):
    login_verified(client, make_manager("manage_rooms"))
    assert client.get(reverse("agenda:programming")).status_code == 403
    assert client.get(reverse("ideas:moderation")).status_code == 403


def test_manager_with_rights_reaches_their_tools(client, make_manager):
    login_verified(client, make_manager("manage_agenda", "moderate"))
    assert client.get(reverse("agenda:programming")).status_code == 200
    assert client.get(reverse("ideas:moderation")).status_code == 200


def test_gestion_home_lists_only_allowed_tools(client, make_manager):
    login_verified(client, make_manager("moderate"))
    body = client.get(reverse("accounts:gestion_home")).content.decode()
    assert "Modération des propositions" in body
    assert "Programmation" not in body


def test_admin_screens_follow_capabilities(client, make_manager):
    login_verified(client, make_manager("manage_rooms"))
    assert client.get("/gestion/admin/rooms/room/").status_code == 200
    assert client.get("/gestion/admin/agenda/event/").status_code == 403


def test_only_superuser_manages_accounts_settings_and_journal(client, make_manager):
    login_verified(client, make_manager("manage_rooms", "manage_agenda", "moderate"))
    for url in [
        "/gestion/admin/accounts/user/",
        "/gestion/admin/core/sitesettings/",
        "/gestion/admin/audit/auditlog/",
        "/gestion/admin/actors/actor/",
    ]:
        assert client.get(url).status_code == 403, url


def test_superuser_reaches_accounts_settings_and_journal(admin_client):
    for url in [
        "/gestion/admin/accounts/user/",
        "/gestion/admin/audit/auditlog/",
    ]:
        assert admin_client.get(url).status_code == 200, url
    assert admin_client.get("/gestion/admin/core/sitesettings/").status_code == 302


def test_deactivating_a_manager_cuts_access_immediately(client, make_manager):
    manager = make_manager("manage_agenda")
    login_verified(client, manager)
    assert client.get(reverse("agenda:programming")).status_code == 200
    manager.is_active = False
    manager.save()
    assert client.get(reverse("agenda:programming")).status_code == 302


def test_superuser_creates_manager_with_capabilities(admin_client, django_user_model):
    response = admin_client.post(
        "/gestion/admin/accounts/user/add/",
        {
            "username": "lea",
            "first_name": "Léa",
            "last_name": "",
            "password1": "un-mot-de-passe-solide-2026",
            "password2": "un-mot-de-passe-solide-2026",
            "capabilities": ["manage_rooms", "export_data"],
        },
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    lea = django_user_model.objects.get(username="lea")
    assert lea.is_staff
    assert capabilities_of(lea) == {"manage_rooms", "export_data"}
