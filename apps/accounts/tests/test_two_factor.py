"""Double authentification des comptes de gestion (CLAUDE.md ACC-3)."""

import pytest
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_static.models import StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts import two_factor
from apps.agenda.models import Event
from apps.ideas import services as ideas_services
from conftest import ACCESS_CODE

pytestmark = pytest.mark.django_db

GESTION_PAGE = "/gestion/moderation/"  # une page de gestion réservée


def current_code(device) -> str:
    return f"{totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits):06d}"


@pytest.fixture
def logged_in(client, admin_user):
    client.force_login(admin_user)
    return client


def test_manager_without_device_is_sent_to_setup(logged_in):
    response = logged_in.get(GESTION_PAGE)
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("accounts:2fa_setup"))


def test_setup_shows_qr_code_as_local_svg(logged_in):
    page = logged_in.get(reverse("accounts:2fa_setup")).content.decode()
    assert reverse("accounts:2fa_qr") in page
    response = logged_in.get(reverse("accounts:2fa_qr"))
    assert response["Content-Type"] == "image/svg+xml"
    assert response.content.startswith(b"<svg")


def test_setup_with_right_code_enables_2fa_and_gives_backup_codes(logged_in, admin_user):
    logged_in.get(reverse("accounts:2fa_setup"))
    device = TOTPDevice.objects.get(user=admin_user, confirmed=False)
    response = logged_in.post(
        reverse("accounts:2fa_setup"), {"token": current_code(device), "next": GESTION_PAGE}
    )
    assert response.status_code == 200
    assert "Notez ces codes de secours" in response.content.decode()
    assert StaticToken.objects.filter(device__user=admin_user).count() == 10
    assert logged_in.get(GESTION_PAGE).status_code == 200


def test_setup_with_wrong_code_is_refused(logged_in, admin_user):
    logged_in.get(reverse("accounts:2fa_setup"))
    response = logged_in.post(reverse("accounts:2fa_setup"), {"token": "000000"})
    assert "Code incorrect" in response.content.decode()
    assert not TOTPDevice.objects.filter(user=admin_user, confirmed=True).exists()


@pytest.fixture
def device(admin_user):
    return TOTPDevice.objects.create(user=admin_user, name="Téléphone", confirmed=True)


def test_new_session_must_verify(logged_in, device):
    response = logged_in.get(GESTION_PAGE)
    assert response["Location"].startswith(reverse("accounts:2fa_verify"))


def test_verification_with_totp_opens_gestion(logged_in, device):
    response = logged_in.post(
        reverse("accounts:2fa_verify") + f"?next={GESTION_PAGE}",
        {"token": current_code(device), "next": GESTION_PAGE},
    )
    assert response["Location"] == GESTION_PAGE
    assert logged_in.get(GESTION_PAGE).status_code == 200


def test_backup_code_works_once(logged_in, client, admin_user, device):
    codes = two_factor.regenerate_backup_codes(admin_user)
    response = logged_in.post(reverse("accounts:2fa_verify"), {"token": codes[0]})
    assert response.status_code == 302
    client.logout()
    client.force_login(admin_user)
    response = client.post(reverse("accounts:2fa_verify"), {"token": codes[0]})
    assert response.status_code == 200  # déjà utilisé


def test_five_wrong_codes_block_verification(logged_in, device):
    for _ in range(5):
        logged_in.post(reverse("accounts:2fa_verify"), {"token": "000000"})
    response = logged_in.post(reverse("accounts:2fa_verify"), {"token": current_code(device)})
    assert response.status_code == 429


def test_login_page_stays_reachable_before_verification(client, db):
    assert client.get("/gestion/admin/login/").status_code == 200


def test_unverified_session_has_no_rights_outside_gestion(logged_in, device, site, make_idea, at):
    """Mot de passe seul, sans TOTP : hors de /gestion/, la session n'a aucun droit (ACC-3)."""
    idea = make_idea(slots=[{"start": at(1, 10)}])
    ideas_services.accept(idea, user=device.user)
    event = idea.events.get()
    # Sans code d'accès, la session est renvoyée vers la saisie du code, comme un inconnu.
    response = logged_in.get(reverse("agenda:calendar"))
    assert response["Location"].startswith(reverse("core:access"))
    # Avec le code, elle agit comme un participant : confirmer lui est refusé.
    logged_in.post(reverse("core:access"), {"code": ACCESS_CODE})
    response = logged_in.post(reverse("agenda:confirm", args=[event.pk]))
    assert response.status_code == 302
    event.refresh_from_db()
    assert event.status == Event.Status.PROVISIONAL


# --- Gestionnaires : double authentification proposée, pas imposée (09/11/2026) ---------


@pytest.fixture
def manager(make_manager):
    return make_manager("moderate")


@pytest.fixture
def manager_client(client, manager):
    client.force_login(manager)
    return client


def test_manager_is_offered_setup_with_a_later_button(manager_client):
    response = manager_client.get(GESTION_PAGE)
    assert response["Location"].startswith(reverse("accounts:2fa_setup"))
    page = manager_client.get(response["Location"]).content.decode()
    assert "Plus tard" in page


def test_later_lets_the_manager_in_for_this_session(manager_client):
    response = manager_client.post(reverse("accounts:2fa_postpone"), {"next": GESTION_PAGE})
    assert response["Location"] == GESTION_PAGE
    assert manager_client.get(GESTION_PAGE).status_code == 200
    # Hors de /gestion/, la session garde ses droits : pas de code d'accès demandé.
    assert manager_client.get(reverse("agenda:calendar")).status_code == 200


def test_later_reminds_on_gestion_home(manager_client):
    manager_client.post(reverse("accounts:2fa_postpone"))
    page = manager_client.get(reverse("accounts:gestion_home")).content.decode()
    assert "La double authentification n'est pas activée" in page


def test_setup_is_offered_again_at_next_login(client, manager):
    client.force_login(manager)
    client.post(reverse("accounts:2fa_postpone"))
    client.logout()
    client.force_login(manager)
    response = client.get(GESTION_PAGE)
    assert response["Location"].startswith(reverse("accounts:2fa_setup"))


def test_superuser_cannot_postpone(logged_in):
    page = logged_in.get(reverse("accounts:2fa_setup")).content.decode()
    assert "Plus tard" not in page
    logged_in.post(reverse("accounts:2fa_postpone"))
    response = logged_in.get(GESTION_PAGE)
    assert response["Location"].startswith(reverse("accounts:2fa_setup"))


def test_manager_with_device_must_verify(manager_client, manager):
    TOTPDevice.objects.create(user=manager, name="Téléphone", confirmed=True)
    manager_client.post(reverse("accounts:2fa_postpone"))
    response = manager_client.get(GESTION_PAGE)
    assert response["Location"].startswith(reverse("accounts:2fa_verify"))
    assert manager_client.get(reverse("agenda:calendar"))["Location"].startswith(
        reverse("core:access")
    )


# --- Connexion par mot de passe : 5 échecs par quart d'heure ------------------------------

LOGIN = "/gestion/admin/login/"


def test_login_with_right_password_works(client, admin_user):
    response = client.post(LOGIN, {"username": "admin", "password": "mot-de-passe-de-test"})
    assert response.status_code == 302


def test_five_wrong_passwords_block_this_username(client, admin_user, make_manager):
    for _ in range(5):
        assert client.post(LOGIN, {"username": "admin", "password": "faux"}).status_code == 200
    response = client.post(LOGIN, {"username": "Admin ", "password": "mot-de-passe-de-test"})
    assert response.status_code == 429
    # Un autre identifiant, depuis la même adresse, n'est pas bloqué.
    other = make_manager(username="camille")
    other.set_password("autre-mot-de-passe-long")
    other.save()
    response = client.post(LOGIN, {"username": "camille", "password": "autre-mot-de-passe-long"})
    assert response.status_code == 302


def test_login_failures_do_not_store_the_username(client, db):
    from apps.core.models import RateLimitHit

    client.post(LOGIN, {"username": "quelquun", "password": "faux"})
    assert "quelquun" not in RateLimitHit.objects.get().bucket
