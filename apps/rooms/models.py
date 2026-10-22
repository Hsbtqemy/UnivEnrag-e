from django.core.validators import RegexValidator
from django.db import models

hex_color = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Couleur au format #RRGGBB.")


class Room(models.Model):
    """Une salle dont le collectif dispose directement (CDC §6).

    Les salles réservées ailleurs (amphi via la scolarité…) ne sont pas des `Room` :
    elles s'écrivent en « lieu libre » sur l'événement.
    """

    name = models.CharField("nom", max_length=80, unique=True)
    building = models.CharField("bâtiment", max_length=80, blank=True)
    capacity = models.PositiveIntegerField("capacité", null=True, blank=True)
    color = models.CharField("couleur", max_length=7, default="#3b6ea5", validators=[hex_color])
    order = models.PositiveSmallIntegerField("ordre d'affichage", default=0)
    is_active = models.BooleanField("proposée à la réservation", default=True)

    class Meta:
        verbose_name = "salle"
        verbose_name_plural = "salles"
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name

    @property
    def label(self) -> str:
        return f"{self.name} ({self.building})" if self.building else self.name
