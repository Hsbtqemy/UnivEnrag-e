"""Idées des membres et propositions d'événements reçues de l'extérieur (CDC §4).

Une proposition d'événement extérieure est une `Idea` d'origine `external` : elle passe
d'abord par la modération, puis suit le même cycle que les idées des membres.
`Proposal` reste réservé aux propositions à voter de la phase 2.
"""

import uuid

from django.conf import settings
from django.db import models

# Suggestions du CDC §4 pour le public visé ; le champ reste libre.
AUDIENCE_SUGGESTIONS = [
    "Tout le collectif",
    "Un groupe de travail",
    "Enseignants-chercheurs",
    "Personnels BIATSS",
    "Étudiants",
    "Extérieurs",
    "Tout public",
]


class IdeaQuerySet(models.QuerySet):
    def visible(self):
        """Les idées que voient les membres (ni à modérer, ni écartées)."""
        return self.filter(status__in=Idea.VISIBLE_STATUSES)

    def to_place(self):
        """Colonne « À placer » : idées d'événement sans événement en cours (IDE-2)."""
        from apps.agenda.models import Event  # les idées dépendent de l'agenda

        active = Event.objects.filter(idea=models.OuterRef("pk")).exclude(
            status=Event.Status.CANCELLED
        )
        return self.filter(
            kind=Idea.Kind.EVENT, status__in=[Idea.Status.NEW, Idea.Status.PREPARING]
        ).exclude(models.Exists(active))


class Idea(models.Model):
    class Origin(models.TextChoices):
        MEMBER = "member", "Membre"
        EXTERNAL = "external", "Proposition extérieure"

    class Kind(models.TextChoices):
        EVENT = "event", "Idée d'événement"
        PROJECT = "project", "Projet"
        WISH = "wish", "Envie"

    class Status(models.TextChoices):
        PENDING = "pending", "À modérer"  # propositions extérieures seulement
        NEW = "new", "Nouvelle"
        PREPARING = "preparing", "En préparation"
        PLANNED = "planned", "Planifiée"
        DONE = "done", "Réalisée"
        ABANDONED = "abandoned", "Abandonnée"
        REFUSED = "refused", "Non retenue"  # propositions extérieures seulement

    class Format(models.TextChoices):
        IN_PERSON = "in_person", "Présentiel"
        VISIO = "visio", "Visio"
        HYBRID = "hybrid", "Hybride"

    class Duration(models.IntegerChoices):
        ONE_HOUR = 60, "1 h"
        NINETY_MIN = 90, "1 h 30"
        TWO_HOURS = 120, "2 h"
        THREE_HOURS = 180, "3 h"
        HALF_DAY = 240, "Une demi-journée (4 h)"
        FULL_DAY = 480, "Une journée (8 h)"

    # Statuts que tout participant peut choisir ; « Planifiée » et « Réalisée » ne
    # s'obtiennent qu'automatiquement (CLAUDE.md, décision 13).
    MANUAL_STATUSES = (Status.NEW, Status.PREPARING, Status.ABANDONED)
    # Ce que voient les membres : ni les propositions à modérer, ni celles écartées.
    VISIBLE_STATUSES = (
        Status.NEW,
        Status.PREPARING,
        Status.PLANNED,
        Status.DONE,
        Status.ABANDONED,
    )

    origin = models.CharField(
        "origine", max_length=10, choices=Origin.choices, default=Origin.MEMBER
    )
    kind = models.CharField("type", max_length=10, choices=Kind.choices, default=Kind.EVENT)
    owner = models.ForeignKey(
        "actors.Actor", on_delete=models.PROTECT, related_name="ideas", verbose_name="porteur"
    )
    # CLAUDE.md PUB-2 : demandé aux seules personnes extérieures, réservé à l'interne,
    # jamais affiché publiquement, jamais utilisé par le site pour envoyer quoi que ce soit.
    owner_email = models.EmailField("e-mail du porteur", blank=True)
    title = models.CharField("titre", max_length=120)
    description = models.TextField("description", max_length=3000, blank=True)
    space = models.ForeignKey(
        "spaces.Space",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ideas",
        verbose_name="espace",
    )
    format = models.CharField("format", max_length=10, choices=Format.choices, blank=True)
    duration_minutes = models.PositiveIntegerField(
        "durée souhaitée", choices=Duration.choices, default=Duration.TWO_HOURS
    )
    audience = models.CharField("public visé", max_length=120, blank=True)
    expected_count = models.PositiveIntegerField("personnes attendues", null=True, blank=True)
    speakers_text = models.CharField(
        "organisateurs et intervenants pressentis", max_length=300, blank=True
    )
    needs = models.CharField("besoins (matériel, budget…)", max_length=500, blank=True)
    constraints = models.CharField(
        "contraintes (jours impossibles, date limite…)", max_length=500, blank=True
    )
    wanted_room = models.ForeignKey(
        "rooms.Room",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="salle souhaitée",
    )
    status = models.CharField(
        "état", max_length=10, choices=Status.choices, default=Status.NEW, db_index=True
    )
    refusal_reason = models.CharField("motif", max_length=300, blank=True)
    tracking_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    updated_by = models.ForeignKey(
        "actors.Actor",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="dernière modification par",
    )
    created_at = models.DateTimeField("déposée le", auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = IdeaQuerySet.as_manager()

    class Meta:
        verbose_name = "idée"
        verbose_name_plural = "idées"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

    @property
    def is_external(self) -> bool:
        return self.origin == self.Origin.EXTERNAL

    @property
    def preferred_precise_slot(self):
        return next((s for s in self.slots.all() if s.is_precise), None)

    @property
    def is_editable_by_owner(self) -> bool:
        """Lien de suivi d'une proposition extérieure : corrigeable tant que rien n'est fixé."""
        return self.status in (self.Status.PENDING, self.Status.NEW, self.Status.PREPARING)

    @property
    def is_editable(self) -> bool:
        return self.status in self.VISIBLE_STATUSES

    @property
    def tracking_status_label(self) -> str:
        """Ce que la personne extérieure lit sur son lien de suivi."""
        if self.status in (self.Status.NEW, self.Status.PREPARING):
            return "Acceptée"
        return self.get_status_display()


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


class Reaction(models.Model):
    """Réaction en un clic, sous son nom ; la liste des personnes est visible (CDC §4)."""

    class Kind(models.TextChoices):
        PARTICIPATE = "participate", "Je participe"
        HELP = "help", "Je peux aider"
        INTERESTED = "interested", "Intéressé·e"

    idea = models.ForeignKey(Idea, on_delete=models.CASCADE, related_name="reactions")
    actor = models.ForeignKey(
        "actors.Actor", on_delete=models.PROTECT, related_name="+", verbose_name="personne"
    )
    kind = models.CharField("réaction", max_length=12, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "réaction"
        verbose_name_plural = "réactions"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["idea", "actor", "kind"], name="reaction_one_per_kind"),
        ]

    def __str__(self) -> str:
        return f"{self.actor} · {self.get_kind_display()}"
