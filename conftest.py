from datetime import date, time, timedelta

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.core.dates import combine
from apps.core.models import SiteSettings
from apps.ideas import services as ideas_services
from apps.rooms.models import Room


@pytest.fixture(autouse=True)
def two_factor_required(settings):
    """Les tests tournent avec la double authentification obligatoire, comme en production."""
    settings.ADMIN_2FA_REQUIRED = True


def login_verified(client, user):
    """Connecte un compte de gestion avec une session déjà vérifiée par TOTP."""
    device, _ = TOTPDevice.objects.get_or_create(user=user, name="Test", confirmed=True)
    client.force_login(user)
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()
    return client


@pytest.fixture
def admin_user(django_user_model):
    return django_user_model.objects.create_superuser("admin", password="mot-de-passe-de-test")


@pytest.fixture
def admin_client(client, admin_user):
    return login_verified(client, admin_user)


@pytest.fixture
def make_manager(django_user_model):
    def build(*codenames, username="gestionnaire"):
        user = django_user_model.objects.create_user(
            username, password="mot-de-passe-de-test", is_staff=True
        )
        user.user_permissions.set(
            Permission.objects.filter(content_type__app_label="accounts", codename__in=codenames)
        )
        return user

    return build


ACCESS_CODE = "code-du-collectif"


@pytest.fixture
def site(db):
    settings_obj = SiteSettings.get()
    settings_obj.set_access_code(ACCESS_CODE)
    return settings_obj


@pytest.fixture
def member_client(client, site):
    """Un navigateur qui a saisi le code d'accès commun."""
    response = client.post(reverse("core:access"), {"code": ACCESS_CODE})
    assert response.status_code == 302
    return client


@pytest.fixture
def room(db):
    return Room.objects.create(name="Salle du collectif", color="#2f5d8c")


@pytest.fixture
def other_room(db):
    return Room.objects.create(name="Petite salle", color="#2e7d4f")


@pytest.fixture
def at():
    """`at(jour, heure)` : une date consciente, `jour` jours après lundi prochain."""
    today = date.today()
    monday = today + timedelta(days=7 - today.weekday())

    def build(day_offset, hour, minute=0):
        return combine(monday + timedelta(days=day_offset), time(hour, minute))

    return build


@pytest.fixture
def make_idea(db):
    def build(
        title="Séminaire",
        *,
        slots=(),
        room=None,
        minutes=120,
        name="Camille Martin",
        email="camille.martin@univ.example",
    ):
        return ideas_services.submit(
            owner_name=name,
            owner_email=email,
            title=title,
            description="Une description.",
            duration_minutes=minutes,
            wanted_room=room,
            slots=slots,
        )

    return build
