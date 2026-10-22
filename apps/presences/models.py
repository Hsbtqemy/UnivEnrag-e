from django.db import models


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
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "présence"
        verbose_name_plural = "présences"
        ordering = ["day", "period"]
        constraints = [
            models.UniqueConstraint(fields=["actor", "day", "period"], name="presence_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.actor} · {self.day:%d/%m} · {self.get_period_display()}"
