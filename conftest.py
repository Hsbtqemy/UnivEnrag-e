from datetime import date, time, timedelta

import pytest

from apps.core.dates import combine
from apps.ideas import services as ideas_services
from apps.rooms.models import Room


@pytest.fixture
def admin_user(django_user_model):
    return django_user_model.objects.create_superuser("admin", password="mot-de-passe-de-test")


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
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
