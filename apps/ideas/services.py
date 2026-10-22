"""Cycle de vie des idées (CDC §4) et des propositions d'événements extérieures.

Transitions autorisées (toute autre lève `TransitionError`) :
  pending → new | refused              modération d'une proposition extérieure
  new ⇄ preparing ⇄ abandoned          à la main, par tout participant
  → planned                            automatique, à la confirmation d'un de ses événements
  planned → preparing                  automatique, quand ses événements confirmés sont annulés
  planned → done                       automatique, une fois le dernier passé (`mark_done`)

Une idée ne passe jamais par un vote (CLAUDE.md IDE-1).
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from apps.actors.services import get_or_create_for_name
from apps.agenda import history as agenda_history
from apps.agenda import services as agenda_services
from apps.agenda.models import Event
from apps.audit import audit

from .models import Idea, IdeaSlot, Reaction

Status = Idea.Status

MODERATION_TRANSITIONS = {Status.PENDING: {Status.NEW, Status.REFUSED}}

# Champs qu'un participant complète ou corrige (CDC §4 : « le reste peut être complété
# plus tard par l'auteur ou les autres participants »).
MEMBER_EDITABLE_FIELDS = [
    "title",
    "kind",
    "description",
    "space",
    "format",
    "duration_minutes",
    "audience",
    "expected_count",
    "speakers_text",
    "needs",
    "constraints",
    "wanted_room",
]
OWNER_EDITABLE_FIELDS = ["title", "description", "audience", "expected_count", "owner_email"]


class TransitionError(Exception):
    pass


def _moderate(idea: Idea, target: str) -> None:
    if target not in MODERATION_TRANSITIONS.get(idea.status, set()):
        raise TransitionError(
            f"Passage impossible de « {idea.get_status_display()} » à « {Status(target).label} »."
        )
    idea.status = target


def _save_slots(idea: Idea, slots) -> None:
    """`slots` : `{"start": datetime}` (la fin découle de la durée) ou `{"period_text": str}`,
    dans l'ordre de préférence. Remplace les créneaux existants."""
    idea.slots.all().delete()
    for rank, slot in enumerate(slots, start=1):
        start = slot.get("start")
        IdeaSlot.objects.create(
            idea=idea,
            rank=rank,
            start=start,
            end=start + timedelta(minutes=idea.duration_minutes) if start else None,
            period_text=slot.get("period_text", ""),
        )


def _place_on_preferred_slot(idea: Idea, *, actor=None, user=None):
    """Une idée avec un créneau précis est placée en provisoire sur le préféré (IDE-2)."""
    slot = idea.preferred_precise_slot
    if slot is None:
        return None
    return agenda_services.create_from_idea(
        idea, start=slot.start, end=slot.end, room=idea.wanted_room, actor=actor, user=user
    )


# --- Idées des membres -------------------------------------------------------------------


@transaction.atomic
def create(*, actor, title, kind=Idea.Kind.EVENT, slots=(), **fields) -> Idea:
    """Dépôt d'une idée par un participant : seuls le nom, le titre et le type comptent."""
    unknown = set(fields) - set(MEMBER_EDITABLE_FIELDS)
    if unknown:
        raise TypeError(f"Champs inconnus : {', '.join(sorted(unknown))}")
    idea = Idea.objects.create(
        origin=Idea.Origin.MEMBER, owner=actor, title=title, kind=kind, **fields
    )
    _save_slots(idea, slots)
    _place_on_preferred_slot(idea, actor=actor)
    return idea


@transaction.atomic
def update(idea: Idea, *, actor, slots=None, **fields) -> Idea:
    """Complément ou correction par n'importe quel participant, sous son nom.

    Les créneaux envisagés sont remplacés ; un événement déjà placé ne bouge pas : c'est
    dans l'agenda qu'on le déplace.
    """
    idea = Idea.objects.select_for_update().get(pk=idea.pk)
    if not idea.is_editable:
        raise TransitionError("Cette idée ne peut pas être modifiée.")
    for name in MEMBER_EDITABLE_FIELDS:
        if name in fields:
            setattr(idea, name, fields[name])
    idea.updated_by = actor
    idea.save()
    if slots is not None:
        _save_slots(idea, slots)
    return idea


@transaction.atomic
def set_status(idea: Idea, status: str, *, actor) -> Idea:
    """Changement de statut à la main (décision 13) : « Planifiée » et « Réalisée » ne
    s'obtiennent qu'automatiquement. Abandonner annule les placements provisoires."""
    idea = Idea.objects.select_for_update().get(pk=idea.pk)
    if status not in Idea.MANUAL_STATUSES or idea.status not in Idea.MANUAL_STATUSES:
        raise TransitionError(
            "Ce statut change tout seul : « Planifiée » à la confirmation d'un événement, "
            "« Réalisée » une fois l'événement passé."
        )
    if status == Status.ABANDONED:
        for event in idea.events.filter(status=Event.Status.PROVISIONAL):
            agenda_services.cancel(event, actor=actor, revision=event.revision)
    idea.status = status
    idea.updated_by = actor
    idea.save(update_fields=["status", "updated_by", "updated_at"])
    return idea


@transaction.atomic
def toggle_reaction(idea: Idea, *, actor, kind: str) -> bool:
    """Ajoute la réaction, ou la retire si elle existe déjà. Renvoie `True` si ajoutée."""
    if kind not in Reaction.Kind.values:
        raise ValueError(f"Réaction inconnue : {kind}")
    if not idea.is_editable:
        raise TransitionError("On ne réagit pas à cette idée.")
    deleted, _ = Reaction.objects.filter(idea=idea, actor=actor, kind=kind).delete()
    if deleted:
        return False
    Reaction.objects.create(idea=idea, actor=actor, kind=kind)
    return True


def reactions_by_kind(idea: Idea) -> list[dict]:
    """Pour chaque réaction : son libellé et la liste des personnes."""
    names = {kind: [] for kind in Reaction.Kind.values}
    for reaction in idea.reactions.select_related("actor"):
        names[reaction.kind].append(reaction.actor)
    return [
        {"kind": kind, "label": Reaction.Kind(kind).label, "actors": names[kind]}
        for kind in Reaction.Kind.values
    ]


@transaction.atomic
def place(idea: Idea, *, start, end, room, actor=None, user=None):
    """Place à la main une idée de la colonne « À placer » (glisser ou clic)."""
    idea = Idea.objects.select_for_update().get(pk=idea.pk)
    if idea.status not in (Status.NEW, Status.PREPARING):
        raise TransitionError("Seule une idée nouvelle ou en préparation peut être placée.")
    if idea.events.exclude(status=Event.Status.CANCELLED).exists():
        raise TransitionError("Cette idée est déjà dans le calendrier.")
    event = agenda_services.create_from_idea(
        idea, start=start, end=end, room=room, actor=actor, user=user
    )
    audit.log(user, "ideas.placed", idea, start=start, end=end, room=room)
    return event


# --- Statuts automatiques (appelés par l'agenda et par `ideas_mark_done`) ----------------


def mark_planned(idea: Idea) -> Idea:
    """Un événement issu de l'idée vient d'être confirmé (IDE-3)."""
    if idea.status in (Status.PENDING, Status.REFUSED):
        raise TransitionError("Une proposition non acceptée ne peut pas être planifiée.")
    if idea.status != Status.PLANNED:
        idea.status = Status.PLANNED
        idea.save(update_fields=["status", "updated_at"])
    return idea


def event_cancelled(idea: Idea) -> Idea:
    """Plus aucun événement confirmé : l'idée revient « En préparation » (décision 13)."""
    if (
        idea.status == Status.PLANNED
        and not idea.events.filter(status=Event.Status.CONFIRMED).exists()
    ):
        idea.status = Status.PREPARING
        idea.save(update_fields=["status", "updated_at"])
    return idea


def mark_done(now=None) -> int:
    """Passe à « Réalisée » les idées planifiées dont le dernier événement confirmé est fini."""
    now = now or timezone.now()
    done = (
        Idea.objects.filter(status=Status.PLANNED)
        .annotate(last_end=Max("events__end", filter=Q(events__status=Event.Status.CONFIRMED)))
        .filter(last_end__lte=now)
    )
    return Idea.objects.filter(pk__in=done.values("pk")).update(status=Status.DONE, updated_at=now)


# --- Propositions extérieures (formulaire public et modération) --------------------------


@transaction.atomic
def submit(
    *,
    owner_name,
    owner_email,
    title,
    description,
    duration_minutes,
    audience="",
    expected_count=None,
    wanted_room=None,
    slots=(),
) -> Idea:
    """Enregistre une proposition reçue du formulaire public ; elle attend la modération."""
    idea = Idea.objects.create(
        origin=Idea.Origin.EXTERNAL,
        kind=Idea.Kind.EVENT,
        status=Status.PENDING,
        owner=get_or_create_for_name(owner_name),
        owner_email=owner_email,
        title=title,
        description=description,
        duration_minutes=duration_minutes,
        audience=audience,
        expected_count=expected_count,
        wanted_room=wanted_room,
    )
    _save_slots(idea, slots)
    return idea


@transaction.atomic
def accept(idea: Idea, *, user) -> Idea:
    """Accepte une proposition : elle rejoint les idées, placée si elle a un créneau précis."""
    idea = Idea.objects.select_for_update().get(pk=idea.pk)
    _moderate(idea, Status.NEW)
    idea.moderated_at, idea.moderated_by = timezone.now(), user
    idea.save()
    audit.log(user, "ideas.accepted", idea)
    _place_on_preferred_slot(idea, user=user)
    return idea


@transaction.atomic
def refuse(idea: Idea, *, user, reason: str) -> Idea:
    """Refuse une proposition. Rien n'est supprimé (CLAUDE.md MOD-1)."""
    idea = Idea.objects.select_for_update().get(pk=idea.pk)
    _moderate(idea, Status.REFUSED)
    idea.refusal_reason = reason.strip()
    idea.moderated_at, idea.moderated_by = timezone.now(), user
    idea.save()
    audit.log(user, "ideas.refused", idea, reason=idea.refusal_reason)
    return idea


@transaction.atomic
def update_by_owner(idea: Idea, **changes) -> Idea:
    """Correction par le porteur extérieur, via son lien de suivi, tant que rien n'est fixé."""
    idea = Idea.objects.select_for_update().get(pk=idea.pk)
    if not idea.is_editable_by_owner:
        raise TransitionError("Cette proposition ne peut plus être modifiée.")
    for name in OWNER_EDITABLE_FIELDS:
        if name in changes:
            setattr(idea, name, changes[name])
    idea.save()
    for event in idea.events.filter(status=Event.Status.PROVISIONAL):
        before = agenda_history.snapshot(event)
        event.title, event.description = idea.title, idea.description
        event.owner_email = idea.owner_email
        event.revision += 1
        event.save(update_fields=["title", "description", "owner_email", "revision", "updated_at"])
        agenda_history.record(event, "updated", actor=idea.owner, before=before)
    return idea
