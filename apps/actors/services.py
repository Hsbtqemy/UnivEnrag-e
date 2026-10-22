import re
import unicodedata

from .models import Actor


def normalize_name(name: str) -> str:
    """Clé de comparaison d'un nom : sans accents, sans casse, ponctuation et espaces fusionnés.

    « Marie-Hélène  Dupont » et « marie helene dupont » donnent la même clé.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    words = re.sub(r"[^\w]+", " ", without_accents.casefold())
    return " ".join(words.split())


def clean_display_name(name: str) -> str:
    return " ".join(name.split())


def get_or_create_for_name(name: str) -> Actor:
    """Retrouve l'acteur qui porte ce nom, ou le crée. Seul point de création d'un acteur."""
    display = clean_display_name(name)
    key = normalize_name(display)
    if not key:
        raise ValueError("Un nom vide ne désigne personne.")
    actor, _ = Actor.objects.get_or_create(name_key=key, defaults={"display_name": display})
    return actor
