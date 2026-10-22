"""Propositions d'événements déposées depuis l'extérieur (fiche du POC).

Dans le code, une proposition d'événement est une `Idea` (CDC §4, « idée d'événement ») :
`Proposal` est réservé aux propositions à voter de la phase 2.
"""

import uuid

from django.conf import settings
from django.db import models


class Idea(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "À modérer"
        ACCEPTED = "accepted", "Acceptée"
        REFUSED = "refused", "Non retenue"
        PLANNED = "planned", "Planifiée"

    class Duration(models.IntegerChoices):
        ONE_HOUR = 60, "1 h"
        NINETY_MIN = 90, "1 h 30"
        TWO_HOURS = 120, "2 h"
        THREE_HOURS = 180, "3 h"
        HALF_DAY = 240, "Une demi-journée (4 h)"
        FULL_DAY = 480, "Une journée (8 h)"

    owner = models.ForeignKey(
        "actors.Actor", on_delete=models.PROTECT, related_name="ideas", verbose_name="porteur"
    )
    # CLAUDE.md PUB-2 : réservé à l'interne, jamais affiché publiquement, jamais utilisé
    # par le site pour envoyer quoi que ce soit.
    owner_email = models.EmailField("e-mail du porteur")
    title = models.CharField("titre", max_length=120)
    description = models.TextField("description", max_length=3000)
    duration_minutes = models.PositiveIntegerField(
        "durée souhaitée", choices=Duration.choices, default=Duration.TWO_HOURS
    )
    audience = models.CharField("public visé", max_length=120, blank=True)
    expected_count = models.PositiveIntegerField("personnes attendues", null=True, blank=True)
    wanted_room = models.ForeignKey(
        "rooms.Room",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="salle souhaitée",
    )
    status = models.CharField(
        "état", max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    refusal_reason = models.CharField("motif", max_length=300, blank=True)
    tracking_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField("reçue le", auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "proposition d'événement"
        verbose_name_plural = "propositions d'événements"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

    @property
    def preferred_precise_slot(self):
        return next((s for s in self.slots.all() if s.is_precise), None)

    @property
    def is_editable_by_owner(self) -> bool:
        return self.status in (self.Status.PENDING, self.Status.ACCEPTED)


class IdeaSlot(models.Model):
    """Un créneau envisagé : précis (début et fin) ou période libre décrite en texte."""

    idea = models.ForeignKey(Idea, on_delete=models.CASCADE, related_name="slots")
    rank = models.PositiveSmallIntegerField("préférence")
    start = models.DateTimeField("début", null=True, blank=True)
    end = models.DateTimeField("fin", null=True, blank=True)
    period_text = models.CharField("période", max_length=200, blank=True)

    class Meta:
        verbose_name = "créneau envisagé"
        verbose_name_plural = "créneaux envisagés"
        ordering = ["rank"]
        constraints = [
            models.UniqueConstraint(fields=["idea", "rank"], name="idea_slot_rank_unique"),
            models.CheckConstraint(
                condition=(
                    models.Q(start__isnull=True, end__isnull=True)
                    | models.Q(start__isnull=False, end__gt=models.F("start"))
                ),
                name="idea_slot_precise_has_valid_end",
            ),
        ]

    def __str__(self) -> str:
        return self.period_text or f"{self.start:%d/%m/%Y %H:%M}"

    @property
    def is_precise(self) -> bool:
        return self.start is not None
