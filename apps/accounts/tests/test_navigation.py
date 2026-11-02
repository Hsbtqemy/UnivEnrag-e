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
    assert "nav__link--cta" in html and "Proposer ou écrire" in html
    assert "Espace membres" in html and "Gestion" not in html
    assert "nav__more--current" not in html  # Actualités est dans la barre du bas


def test_visitor_home_is_under_more_on_phone(client, site):
    """La page d'arrivée n'occupe pas la barre du bas : le nom du site y ramène."""
    html = Client().get(reverse("public:home")).content.decode()
    assert "nav__more--current" in html


@pytest.mark.parametrize(
    "url_name", ["public:home", "public:news_list", "agenda:public_list", "ideas:public_list"]
)
def test_member_gets_public_navigation_on_public_pages(member_client, url_name):
    html = member_client.get(reverse(url_name)).content.decode()
    assert reverse("ideas:propose") in html and "Actualités" in html
    assert reverse("presences:board") not in html
    assert f'class="nav__link" href="{reverse("agenda:home")}"' in html  # « Espace membres »
    assert html.count('<span class="nav__label">Espace membres</span>') == 1
    assert reverse("core:access") not in html
    assert "site-header__tools" not in html
    assert f'class="site-name" href="{reverse("public:home")}"' in html


def test_visitor_members_link_goes_to_access_code_page(client, site):
    html = Client().get(reverse("public:home")).content.decode()
    assert f'class="nav__link" href="{reverse("core:access")}"' in html


def test_member_keeps_internal_navigation_inside(member_client):
    html = member_client.get(reverse("agenda:home")).content.decode()
    assert reverse("presences:board") in html and "site-header__tools" in html


def test_manager_sees_management_tab_on_public_pages(member_client, admin_user):
    login_verified(member_client, admin_user)
    html = member_client.get(reverse("public:home")).content.decode()
    assert reverse("accounts:gestion_home") in html
    assert f'class="nav__link" href="{reverse("agenda:home")}"' in html


def test_manager_sees_management_tab(member_client, admin_user):
    login_verified(member_client, admin_user)
    html = member_client.get(reverse("agenda:home")).content.decode()
    assert reverse("accounts:gestion_home") in html
