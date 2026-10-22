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

    class RoomStatus(models.TextChoices):
        APPROVED = "approved", "Validée"
        PENDING = "pending", "En attente de validation"

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
    # Réservation d'une salle « soumise à validation » : le créneau est bloqué dès la
    # demande, un habilité « salles » valide ou refuse (CLAUDE.md SAL-4).
    room_status = models.CharField(
        "réservation de salle",
        max_length=10,
        choices=RoomStatus.choices,
        default=RoomStatus.APPROVED,
    )
    space = models.ForeignKey(
        "spaces.Space",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="events",
        verbose_name="espace",
    )
    place_text = models.CharField("lieu libre", max_length=200, blank=True)
    visio_link = models.URLField("lien visio", blank=True)
    status = models.CharField(
        "statut", max_length=12, choices=Status.choices, default=Status.PROVISIONAL
    )
    is_public = models.BooleanField("public", default=False)
    # Un participant qui coche « public » ne fait qu'une demande ; seul un habilité
    # « agenda » ou « page publique » pose `is_public` (CLAUDE.md, décision 11).
    public_requested = models.BooleanField("publication demandée", default=False)
    # Un événement verrouillé ne se modifie plus que par un habilité « agenda » (AGE-5).
    is_locked = models.BooleanField("verrouillé", default=False)
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

    @property
    def room_pending(self) -> bool:
        return bool(self.room_id) and self.room_status == self.RoomStatus.PENDING

    @property
    def display_color(self) -> str:
        """Couleur dans l'agenda des membres : celle de l'espace, sinon de la salle (CDC §3)."""
        if self.space_id:
            return self.space.color
        if self.room_id:
            return self.room.color
        return "#6b7280"


class EventChange(models.Model):
    """Une entrée de l'historique d'un événement (CLAUDE.md AGE-4).

    `changes` décrit la modification champ par champ ({champ: [avant, après]}) ;
    `snapshot` est l'état complet après la modification, ce qui permet de restaurer
    n'importe quelle version.
    """

    class Action(models.TextChoices):
        CREATED = "created", "Création"
        PLACED = "placed", "Placement d'une proposition"
        UPDATED = "updated", "Modification"
        MOVED = "moved", "Déplacement"
        CANCELLED = "cancelled", "Annulation"
        CONFIRMED = "confirmed", "Confirmation"
        PUBLIC = "public", "Publication"
        LOCKED = "locked", "Verrou"
        RESTORED = "restored", "Restauration"
        ROOM = "room", "Réservation de salle"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="changes")
    action = models.CharField(max_length=12, choices=Action.choices)
    actor = models.ForeignKey(
        "actors.Actor", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    changes = models.JSONField(default=dict)
    snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "modification d'événement"
        verbose_name_plural = "historique des événements"
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.get_action_display()} · {self.event}"

    @property
    def author_label(self) -> str:
        if self.actor_id:
            return self.actor.display_name
        if self.user_id:
            return f"{self.user} (gestion)"
        return "Le site"
