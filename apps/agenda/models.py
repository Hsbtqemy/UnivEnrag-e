from django.conf import settings
from django.db import models


class EventQuerySet(models.QuerySet):
    def public(self):
        """Seul point d'entrée des vues publiques (CLAUDE.md PUB-1) : confirmé ET public."""
        return self.filter(status=Event.Status.CONFIRMED, is_public=True)

    def active(self):
        return self.exclude(status=Event.Status.CANCELLED)

    def overlapping(self, start, end):
        # Chevauchement strict : deux événements bout à bout ne se chevauchent pas.
        return self.filter(start__lt=end, end__gt=start)


class Event(models.Model):
    """Un événement de l'agenda collectif ; la salle est un attribut, pas un calendrier."""

    class Status(models.TextChoices):
        PROVISIONAL = "provisional", "Provisoire"
        CONFIRMED = "confirmed", "Confirmé"
        CANCELLED = "cancelled", "Annulé"

    idea = models.OneToOneField(
        "ideas.Idea",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="event",
        verbose_name="proposition d'origine",
    )
    owner = models.ForeignKey(
        "actors.Actor", on_delete=models.PROTECT, related_name="events", verbose_name="porteur"
    )
    owner_email = models.EmailField("e-mail du porteur", blank=True)  # interne (PUB-2)
    title = models.CharField("titre", max_length=120)
    description = models.TextField("description", blank=True)
    start = models.DateTimeField("début", db_index=True)
    end = models.DateTimeField("fin")
    room = models.ForeignKey(
        "rooms.Room",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="events",
        verbose_name="salle",
    )
    place_text = models.CharField("lieu libre", max_length=200, blank=True)
    status = models.CharField(
        "statut", max_length=12, choices=Status.choices, default=Status.PROVISIONAL
    )
    is_public = models.BooleanField("public", default=False)
    # Verrouillage optimiste : un déplacement fondé sur une version périmée est refusé.
    revision = models.PositiveIntegerField(default=1)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EventQuerySet.as_manager()

    class Meta:
        verbose_name = "événement"
        verbose_name_plural = "événements"
        ordering = ["start"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end__gt=models.F("start")), name="event_end_after_start"
            ),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def place_label(self) -> str:
        if self.room_id:
            return self.room.label
        return self.place_text or "Lieu à préciser"
