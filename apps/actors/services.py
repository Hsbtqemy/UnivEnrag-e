import re
import unicodedata

from django.utils import timezone

from .models import Actor

ANONYMOUS_NAME = "Anonyme"


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


def anonymize(actor: Actor) -> Actor:
    """Anonymisation RGPD en une seule écriture : toutes les contributions qui référencent
    cet acteur affichent désormais « Anonyme » (CLAUDE.md, décision 17). Le même nom saisi
    plus tard crée une nouvelle personne.

    Les champs texte libres (e-mail du porteur, intervenants pressentis) restent à
    corriger à la main.
    """
    actor.display_name = ANONYMOUS_NAME
    actor.name_key = f"anonyme:{actor.pk}"
    actor.anonymized_at = timezone.now()
    actor.save(update_fields=["display_name", "name_key", "anonymized_at"])
    return actor
