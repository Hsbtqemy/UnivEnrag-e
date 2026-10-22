from datetime import time

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.validators import hex_color


class Room(models.Model):
    """Une salle dont le collectif dispose directement (CDC §6).

    Les salles réservées ailleurs (amphi via la scolarité…) ne sont pas des `Room` :
    elles s'écrivent en « lieu libre » sur l'événement.
    """

    class BookingMode(models.TextChoices):
        FREE = "free", "Réservation libre"
        APPROVAL = "approval", "Soumise à validation"

    name = models.CharField("nom", max_length=80, unique=True)
    building = models.CharField("bâtiment", max_length=80, blank=True)
    capacity = models.PositiveIntegerField("capacité", null=True, blank=True)
    color = models.CharField("couleur", max_length=7, default="#3b6ea5", validators=[hex_color])
    booking_mode = models.CharField(
        "mode de réservation", max_length=10, choices=BookingMode.choices, default=BookingMode.FREE
    )
    access_notes = models.TextField("consignes d'accès", blank=True)
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

    @property
    def needs_approval(self) -> bool:
        return self.booking_mode == self.BookingMode.APPROVAL

    def is_open(self, start, end) -> bool:
        """Le créneau tient-il dans une plage d'ouverture ? (CLAUDE.md SAL-3)

        Une salle sans plage définie est ouverte en permanence. Un créneau doit tenir
        dans une seule plage, le même jour.
        """
        hours = list(self.opening_hours.all())
        if not hours:
            return True
        start, end = timezone.localtime(start), timezone.localtime(end)
        if start.date() != end.date() and end.time() != time(0, 0):
            return False
        end_time = time(23, 59, 59) if end.time() == time(0, 0) else end.time()
        return any(
            h.weekday == start.weekday() and h.opens <= start.time() and end_time <= h.closes
            for h in hours
        )

    def opening_summary(self) -> str:
        hours = list(self.opening_hours.all())
        if not hours:
            return "Pas de restriction horaire"
        return " · ".join(str(h) for h in hours)


class OpeningHours(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "lundi"
        TUESDAY = 1, "mardi"
        WEDNESDAY = 2, "mercredi"
        THURSDAY = 3, "jeudi"
        FRIDAY = 4, "vendredi"
        SATURDAY = 5, "samedi"
        SUNDAY = 6, "dimanche"

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="opening_hours")
    weekday = models.PositiveSmallIntegerField("jour", choices=Weekday.choices)
    opens = models.TimeField("ouverture")
    closes = models.TimeField("fermeture")

    class Meta:
        verbose_name = "plage d'ouverture"
        verbose_name_plural = "plages d'ouverture"
        ordering = ["weekday", "opens"]

    def __str__(self) -> str:
        return f"{self.get_weekday_display()} {self.opens:%H:%M}–{self.closes:%H:%M}"

    def clean(self):
        if self.opens and self.closes and self.closes <= self.opens:
            raise ValidationError("La fermeture doit suivre l'ouverture.")
