from django.db import models
from django.utils import timezone


class PresenceQuerySet(models.QuerySet):
    def public(self):
        """Les permanences ouvertes au public, à venir : seul point d'entrée de la page
        publique, qui n'en montre que le jour, le moment et le lieu (CLAUDE.md PUB-1,
        décision 23)."""
        return self.filter(is_open=True, day__gte=timezone.localdate()).exclude(place="")


class Presence(models.Model):
    """« Je serai là » : une personne annonce sa présence sur une demi-journée.

    On déclare des présences plutôt que des indisponibilités : c'est ce que les membres
    disent naturellement, et le but est de voir qui sera où dans la semaine. Pas de
    règle récurrente : on reprend sa semaine précédente d'un clic.
    """

    class Period(models.TextChoices):
        MORNING = "morning", "Matin"
        AFTERNOON = "afternoon", "Après-midi"
        EVENING = "evening", "Soir"

    actor = models.ForeignKey(
        "actors.Actor", on_delete=models.CASCADE, related_name="presences", verbose_name="personne"
    )
    day = models.DateField("jour", db_index=True)
    period = models.CharField("moment", max_length=10, choices=Period.choices)
    place = models.CharField("lieu", max_length=80, blank=True)
    # Décision 23 : la personne choisit d'en faire une permanence. La page publique dit
    # alors « quelqu'un du collectif est là », jamais qui.
    is_open = models.BooleanField("permanence ouverte au public", default=False)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PresenceQuerySet.as_manager()

    class Meta:
        verbose_name = "présence"
        verbose_name_plural = "présences"
        ordering = ["day", "period"]
        constraints = [
            models.UniqueConstraint(fields=["actor", "day", "period"], name="presence_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.actor} · {self.day:%d/%m} · {self.get_period_display()}"
