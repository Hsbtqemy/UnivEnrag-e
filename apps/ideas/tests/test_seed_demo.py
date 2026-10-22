"""La démo se charge, puis se recharge par-dessus (--reset), sans erreur."""

import pytest
from django.core.management import call_command

from apps.agenda.models import Event
from apps.polls.models import Poll

pytestmark = pytest.mark.django_db


def test_seed_demo_twice(capsys):
    call_command("seed_demo")
    call_command("seed_demo", reset=True)
    assert Event.objects.exists()
    assert Poll.objects.count() == 1
    assert "Démo chargée." in capsys.readouterr().out
