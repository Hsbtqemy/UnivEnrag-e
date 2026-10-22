"""Double authentification des comptes de gestion (CLAUDE.md ACC-3)."""

import pytest
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_static.models import StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts import two_factor

pytestmark = pytest.mark.django_db

PROGRAMMING = "/gestion/programmation/"


def current_code(device) -> str:
    return f"{totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits):06d}"


@pytest.fixture
def logged_in(client, admin_user):
    client.force_login(admin_user)
    return client


def test_manager_without_device_is_sent_to_setup(logged_in):
    response = logged_in.get(PROGRAMMING)
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
        reverse("accounts:2fa_setup"), {"token": current_code(device), "next": PROGRAMMING}
    )
    assert response.status_code == 200
    assert "Notez ces codes de secours" in response.content.decode()
    assert StaticToken.objects.filter(device__user=admin_user).count() == 10
    assert logged_in.get(PROGRAMMING).status_code == 200


def test_setup_with_wrong_code_is_refused(logged_in, admin_user):
    logged_in.get(reverse("accounts:2fa_setup"))
    response = logged_in.post(reverse("accounts:2fa_setup"), {"token": "000000"})
    assert "Code incorrect" in response.content.decode()
    assert not TOTPDevice.objects.filter(user=admin_user, confirmed=True).exists()


@pytest.fixture
def device(admin_user):
    return TOTPDevice.objects.create(user=admin_user, name="Téléphone", confirmed=True)


def test_new_session_must_verify(logged_in, device):
    response = logged_in.get(PROGRAMMING)
    assert response["Location"].startswith(reverse("accounts:2fa_verify"))


def test_verification_with_totp_opens_gestion(logged_in, device):
    response = logged_in.post(
        reverse("accounts:2fa_verify") + f"?next={PROGRAMMING}",
        {"token": current_code(device), "next": PROGRAMMING},
    )
    assert response["Location"] == PROGRAMMING
    assert logged_in.get(PROGRAMMING).status_code == 200


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
