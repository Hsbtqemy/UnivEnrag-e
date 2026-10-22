import pytest

from apps.actors.services import anonymize, get_or_create_for_name, normalize_name
from apps.ideas import services as ideas_services


def test_normalize_ignores_case_accents_spaces_and_punctuation():
    assert normalize_name("  Marie-Hélène   DUPONT ") == normalize_name("marie helene dupont")


@pytest.mark.django_db
def test_same_name_gives_same_actor():
    first = get_or_create_for_name("Marie-Hélène Dupont")
    second = get_or_create_for_name("marie helene  dupont")
    assert first == second
    assert first.display_name == "Marie-Hélène Dupont"


@pytest.mark.django_db
def test_empty_name_is_refused():
    with pytest.raises(ValueError):
        get_or_create_for_name("  --  ")


def test_anonymize_hides_the_name_everywhere_in_one_write(db):
    marie = get_or_create_for_name("Marie Dupont")
    idea = ideas_services.create(actor=marie, title="Un ciné-club")
    anonymize(marie)
    idea.refresh_from_db()
    assert idea.owner.display_name == "Anonyme"
    # Le même nom saisi plus tard désigne une nouvelle personne.
    assert get_or_create_for_name("Marie Dupont") != marie
