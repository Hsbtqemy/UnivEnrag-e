"""Barre de navigation : une seule description, l'onglet en cours, « Plus » sur téléphone."""

import pytest
from django.test import Client
from django.urls import reverse

from conftest import login_verified

pytestmark = pytest.mark.django_db


def test_member_secondary_page_marks_tab_and_more(member_client):
    html = member_client.get(reverse("agenda:rooms")).content.decode()
    assert "nav__more--current" in html
    assert html.count('aria-current="page"') == 2  # l'onglet et sa copie sous « Plus »


def test_member_primary_page_does_not_mark_more(member_client):
    html = member_client.get(reverse("agenda:calendar")).content.decode()
    assert "nav__more--current" not in html
    assert html.count('aria-current="page"') == 1


def test_visitor_navigation_has_call_to_action(client, site):
    html = Client().get(reverse("public:news_list")).content.decode()
    assert "nav__link--cta" in html and "Proposer une idée" in html
    assert "Espace membres" in html and "Gestion" not in html
    assert "nav__more--current" not in html  # Actualités est dans la barre du bas


def test_visitor_home_is_under_more_on_phone(client, site):
    """La page d'arrivée n'occupe pas la barre du bas : le nom du site y ramène."""
    html = Client().get(reverse("public:home")).content.decode()
    assert "nav__more--current" in html


def test_manager_sees_management_tab(member_client, admin_user):
    login_verified(member_client, admin_user)
    html = member_client.get(reverse("agenda:home")).content.decode()
    assert reverse("accounts:gestion_home") in html
