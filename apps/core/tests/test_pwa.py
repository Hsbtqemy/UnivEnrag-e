"""Site installable : manifeste, service worker, page hors ligne (CLAUDE.md, « Interface »)."""

import json
import re

from django.contrib.staticfiles import finders
from django.urls import reverse

from apps.actors.resolvers import NAME_COOKIE


def test_manifest_is_public_and_points_to_existing_icons(client, site):
    response = client.get(reverse("core:manifest"))
    assert response.status_code == 200
    assert response["Content-Type"] == "application/manifest+json"
    data = json.loads(response.content)
    assert (data["display"], data["start_url"], data["lang"]) == ("standalone", "/", "fr")
    assert {"192x192", "512x512"} <= {icon["sizes"] for icon in data["icons"]}
    for icon in data["icons"]:
        assert finders.find(icon["src"].removeprefix("/static/")), icon["src"]


def test_service_worker_is_served_at_the_root_and_never_cached(client, site):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/javascript")
    assert "no-cache" in response["Cache-Control"]
    body = response.content.decode()
    offline = re.search(r'const OFFLINE = ("[^"]*");', body).group(1)
    assert json.loads(offline) == reverse("core:offline")
    # Les pages ne sont jamais mises en cache : seules la page hors ligne et les statiques.
    assert 'request.mode === "navigate"' in body


def test_offline_page_carries_no_personal_data(member_client):
    member_client.cookies[NAME_COOKIE] = "Marie Dupont"
    body = member_client.get(reverse("core:offline")).content.decode()
    assert "Pas de connexion" in body
    assert "Marie Dupont" not in body


def test_pages_link_the_manifest(client, site):
    body = client.get(reverse("agenda:public_list")).content.decode()
    assert 'rel="manifest"' in body
    assert "icons/apple-touch-icon" in body


def test_theme_toggle_is_in_every_page_and_applied_before_the_stylesheet(client, site):
    body = client.get(reverse("public:home")).content.decode()
    assert 'id="bouton-theme"' in body and 'aria-pressed="false" hidden' in body
    # Le script du thème passe avant la feuille de style : pas de clignotement.
    assert body.index("js/theme") < body.index("css/app")
