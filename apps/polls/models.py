"""Sondage de dates (CDC §3, « Emplois du temps ») : où sont les disponibilités.

Toujours nominatif, sans quorum ni seuil (CLAUDE.md, décision 9). Le meilleur créneau
devient un événement de l'agenda, et le sondage se clôt.
"""

from django.db import models


class Poll(models.Model):
    owner = models.ForeignKey(
        "actors.Actor", on_delete=models.PROTECT, related_name="polls", verbose_name="porteur"
    )
    title = models.CharField("objet", max_length=120)
    description = models.TextField("précisions", blank=True)
    space = models.ForeignKey(
        "spaces.Space", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="espace"
    )
    room = models.ForeignKey(
        "rooms.Room",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="salle envisagée",
    )
    event = models.OneToOneField(
        "agenda.Event",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="poll",
        verbose_name="événement créé",
    )
    is_closed = models.BooleanField("clos", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "sondage de dates"
        verbose_name_plural = "sondages de dates"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class PollSlot(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="slots")
    start = models.DateTimeField("début")
    end = models.DateTimeField("fin")

    class Meta:
        verbose_name = "créneau proposé"
        verbose_name_plural = "créneaux proposés"
        ordering = ["start"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end__gt=models.F("start")), name="poll_slot_end_after_start"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.start:%d/%m %H:%M}"


class PollAnswer(models.Model):
    """Une réponse « oui » ou « si besoin » ; l'absence de réponse vaut « non »."""

    class Answer(models.TextChoices):
        YES = "yes", "Oui"
        MAYBE = "maybe", "Si besoin"

    slot = models.ForeignKey(PollSlot, on_delete=models.CASCADE, related_name="answers")
    actor = models.ForeignKey("actors.Actor", on_delete=models.PROTECT, related_name="+")
    answer = models.CharField(max_length=5, choices=Answer.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["slot", "actor"], name="poll_answer_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.actor} · {self.slot} · {self.get_answer_display()}"
