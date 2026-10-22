import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class RateLimitHit(models.Model):
    """Une tentative comptée pour la limitation de débit.

    L'adresse IP n'est jamais stockée en clair : seule son empreinte HMAC l'est
    (CLAUDE.md, « Sécurité et RGPD »). Le compteur vit en base, et non dans le cache
    local d'un processus, pour rester juste avec plusieurs workers.
    """

    bucket = models.CharField(max_length=40)
    key_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["bucket", "key_hash", "created_at"])]

    def __str__(self) -> str:
        return f"{self.bucket} · {self.created_at:%Y-%m-%d %H:%M}"


def _token() -> str:
    return secrets.token_urlsafe(24)


class SiteSettings(models.Model):
    """Réglages du site, en un seul exemplaire (pk = 1)."""

    collective_name = models.CharField(
        "nom du collectif", max_length=120, default="Université Enragée"
    )
    presentation = models.TextField(
        "présentation du collectif",
        blank=True,
        help_text=(
            "Affichée en tête de la page publique. Mise en forme simple : **gras**, "
            "*italique*, listes (- …), liens [texte](https://…)."
        ),
    )
    privacy_contact = models.CharField(
        "contact pour les données personnelles",
        max_length=200,
        blank=True,
        help_text="Affiché sur la page « Données personnelles » : une adresse, un nom, un lieu.",
    )
    access_code_hash = models.CharField(max_length=128, blank=True)
    # Empreinte posée dans le cookie des navigateurs : la changer invalide tous les cookies
    # d'un coup (CLAUDE.md ACC-1), sans jamais y mettre le code lui-même.
    access_code_stamp = models.CharField(max_length=64, default=_token)
    # Jeton des flux iCal internes, indépendant du code d'accès et révocable.
    feeds_token = models.CharField(max_length=64, default=_token)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "réglages du site"
        verbose_name_plural = "réglages du site"

    def __str__(self) -> str:
        return "Réglages du site"

    @classmethod
    def get(cls) -> "SiteSettings":
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

    @property
    def has_access_code(self) -> bool:
        return bool(self.access_code_hash)

    def set_access_code(self, raw: str) -> None:
        self.access_code_hash = make_password(raw.strip())
        self.access_code_stamp = _token()
        self.save(update_fields=["access_code_hash", "access_code_stamp", "updated_at"])

    def check_access_code(self, raw: str) -> bool:
        return self.has_access_code and check_password(raw.strip(), self.access_code_hash)

    def regenerate_feeds_token(self) -> None:
        self.feeds_token = _token()
        self.save(update_fields=["feeds_token", "updated_at"])
