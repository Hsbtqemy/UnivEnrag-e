"""Cycle de vie d'une proposition d'événement extérieure.

Transitions autorisées (toute autre lève `TransitionError`) :
  pending → accepted | refused   (modération par un admin)
  accepted → planned             (automatique, à la confirmation de l'événement)
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.actors.services import get_or_create_for_name
from apps.agenda import services as agenda_services

from .models import Idea, IdeaSlot

ALLOWED_TRANSITIONS = {
    Idea.Status.PENDING: {Idea.Status.ACCEPTED, Idea.Status.REFUSED},
    Idea.Status.ACCEPTED: {Idea.Status.PLANNED},
}

OWNER_EDITABLE_FIELDS = ["title", "description", "audience", "expected_count", "owner_email"]


class TransitionError(Exception):
    pass


def _transition(idea: Idea, target: str) -> None:
    if target not in ALLOWED_TRANSITIONS.get(idea.status, set()):
        raise TransitionError(
            f"Passage impossible de « {idea.get_status_display()} » "
            f"à « {Idea.Status(target).label} »."
        )
    idea.status = target


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
    """Enregistre une proposition reçue du formulaire public.

    `slots` : suite de dictionnaires `{"start": datetime}` (créneau précis, la fin découle de
    la durée) ou `{"period_text": str}` (période libre), dans l'ordre de préférence.
    """
    idea = Idea.objects.create(
        owner=get_or_create_for_name(owner_name),
        owner_email=owner_email,
        title=title,
        description=description,
        duration_minutes=duration_minutes,
        audience=audience,
        expected_count=expected_count,
        wanted_room=wanted_room,
    )
    for rank, slot in enumerate(slots, start=1):
        start = slot.get("start")
        IdeaSlot.objects.create(
            idea=idea,
            rank=rank,
            start=start,
            end=start + timedelta(minutes=duration_minutes) if start else None,
            period_text=slot.get("period_text", ""),
        )
    return idea


@transaction.atomic
def accept(idea: Idea, *, user) -> Idea:
    """Accepte une proposition ; si elle a un créneau précis, elle y est placée en provisoire."""
    idea = Idea.objects.select_for_update().get(pk=idea.pk)
    _transition(idea, Idea.Status.ACCEPTED)
    idea.moderated_at, idea.moderated_by = timezone.now(), user
    idea.save()
    slot = idea.preferred_precise_slot
    if slot is not None:
        agenda_services.create_from_idea(
            idea, start=slot.start, end=slot.end, room=idea.wanted_room
        )
    return idea


@transaction.atomic
def refuse(idea: Idea, *, user, reason: str) -> Idea:
    """Refuse une proposition. Rien n'est supprimé (CLAUDE.md MOD-1)."""
    idea = Idea.objects.select_for_update().get(pk=idea.pk)
    _transition(idea, Idea.Status.REFUSED)
    idea.refusal_reason = reason.strip()
    idea.moderated_at, idea.moderated_by = timezone.now(), user
    idea.save()
    return idea


@transaction.atomic
def place(idea: Idea, *, start, end, room):
    """Place à la main une proposition acceptée qui n'est pas encore dans le calendrier."""
    idea = Idea.objects.select_for_update().get(pk=idea.pk)
    if idea.status != Idea.Status.ACCEPTED:
        raise TransitionError("Seule une proposition acceptée peut être placée.")
    if hasattr(idea, "event"):
        raise TransitionError("Cette proposition est déjà dans le calendrier.")
    return agenda_services.create_from_idea(idea, start=start, end=end, room=room)


def mark_planned(idea: Idea) -> Idea:
    """Appelé par l'agenda quand l'événement issu de la proposition est confirmé."""
    if idea.status != Idea.Status.PLANNED:
        _transition(idea, Idea.Status.PLANNED)
        idea.save(update_fields=["status", "updated_at"])
    return idea


@transaction.atomic
def update_by_owner(idea: Idea, **changes) -> Idea:
    """Correction par le porteur, via son lien de suivi, tant que rien n'est planifié."""
    idea = Idea.objects.select_for_update().get(pk=idea.pk)
    if not idea.is_editable_by_owner:
        raise TransitionError("Cette proposition ne peut plus être modifiée.")
    for name in OWNER_EDITABLE_FIELDS:
        if name in changes:
            setattr(idea, name, changes[name])
    idea.save()
    event = getattr(idea, "event", None)
    if event is not None and event.status == event.Status.PROVISIONAL:
        event.title, event.description = idea.title, idea.description
        event.owner_email = idea.owner_email
        event.revision += 1
        event.save(update_fields=["title", "description", "owner_email", "revision", "updated_at"])
    return idea
