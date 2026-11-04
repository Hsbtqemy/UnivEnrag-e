"""Page publique (CDC §7) : actualités et messages de contact."""

import html
import re
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator

from apps.core.markdown import render as render_markdown

# Une actualité porte la mention « Nouveau » pendant sa première semaine.
NEW_FOR = timedelta(days=7)


class NewsPostQuerySet(models.QuerySet):
    def public(self):
        """Seul point d'entrée des vues publiques : publiée, et pas dans le futur (PUB-1)."""
        return self.filter(is_published=True, published_at__lte=timezone.now())


class NewsPost(models.Model):
    """Un court article rédigé par un habilité « page publique »."""

    title = models.CharField("titre", max_length=150)
    slug = models.SlugField("adresse", max_length=160, unique=True)
    summary = models.CharField(
        "chapô",
        max_length=300,
        blank=True,
        help_text="Une ou deux phrases, montrées dans la liste.",
    )
    body = models.TextField(
        "texte",
        help_text=(
            "Mise en forme simple : **gras**, *italique*, listes (- …), liens "
            "[texte](https://…). Une ligne vide sépare les paragraphes."
        ),
    )
    is_published = models.BooleanField("publiée", default=False)
    published_at = models.DateTimeField("date de publication", default=timezone.now)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="rédigée par",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = NewsPostQuerySet.as_manager()

    class Meta:
        verbose_name = "actualité"
        verbose_name_plural = "actualités"
        ordering = ["-published_at"]

    def __str__(self) -> str:
        return self.title

    @property
    def excerpt(self) -> str:
        """Le début du texte, sans mise en forme : pour la liste, quand le chapô manque."""
        # Les éléments d'une liste, collés une fois les balises ôtées, restent séparés.
        rendered = re.sub(r"</li>\s*", " · ", render_markdown(self.body))
        text = " ".join(html.unescape(strip_tags(rendered)).split()).rstrip(" ·")
        return Truncator(text).chars(220)

    @property
    def is_new(self) -> bool:
        return timezone.now() - self.published_at < NEW_FOR


class ContactMessage(models.Model):
    """Un message reçu par le formulaire de contact public.

    L'e-mail est facultatif (décision du porteur du projet, 22/10/2026) : on connaît les
    gens, on retrouve ceux qui n'en laissent pas. Comme celui d'un porteur (PUB-2), il est
    réservé à l'interne et le site n'y envoie jamais rien.
    """

    sender = models.ForeignKey(
        "actors.Actor", on_delete=models.PROTECT, related_name="+", verbose_name="de la part de"
    )
    email = models.EmailField("e-mail", blank=True)
    message = models.TextField("message", max_length=4000)
    created_at = models.DateTimeField("reçu le", auto_now_add=True)
    handled_at = models.DateTimeField("traité le", null=True, blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="traité par",
    )

    class Meta:
        verbose_name = "message de contact"
        verbose_name_plural = "messages de contact"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.sender} · {self.created_at:%d/%m/%Y}"

    @property
    def is_handled(self) -> bool:
        return self.handled_at is not None
