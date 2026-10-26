from django.db import models
from django.utils import timezone


def hours_label(start, end) -> str:
    if start and end:
        return f"{start:%H:%M} – {end:%H:%M}"
    if start:
        return f"dès {start:%H:%M}"
    if end:
        return f"jusqu'à {end:%H:%M}"
    return ""


class PresenceQuerySet(models.QuerySet):
    def public(self):
        """Les permanences ouvertes au public, à venir : seul point d'entrée de la page
        publique, qui n'en montre que le jour, le moment, les heures et le lieu
        (CLAUDE.md PUB-1, décision 23)."""
        return self.filter(is_open=True, day__gte=timezone.localdate())


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
    # Heures facultatives : « là de 14 h à 17 h » dans l'après-midi coché.
    start_time = models.TimeField("à partir de", null=True, blank=True)
    end_time = models.TimeField("jusqu'à", null=True, blank=True)
    # Décision 23 : la personne choisit d'en faire une permanence. La page publique dit
    # alors « quelqu'un du collectif est là », jamais qui. Le lieu reste facultatif.
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

    @property
    def hours(self) -> str:
        """« 14:00 – 17:00 », « dès 14:00 », « jusqu'à 17:00 » ou rien."""
        return hours_label(self.start_time, self.end_time)
