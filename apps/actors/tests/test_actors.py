import pytest

from apps.actors.services import get_or_create_for_name, normalize_name


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
