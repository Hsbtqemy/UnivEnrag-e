"""Écritures sur l'agenda. Toute modification d'un événement passe par ici."""

from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from .models import Event


class EventError(Exception):
    """Opération refusée sur un événement ; le message s'affiche tel quel."""


class StaleRevisionError(EventError):
    def __init__(self):
        super().__init__(
            "Cet événement a été modifié entre-temps. L'affichage est rechargé : "
            "recommencez si besoin."
        )


class RoomConflictError(EventError):
    """Conflit de salle bloquant (CLAUDE.md SAL-2)."""

    def __init__(self, conflicts):
        self.conflicts = list(conflicts)
        names = ", ".join(f"« {e.title} » ({describe_slot(e)})" for e in self.conflicts)
        super().__init__(f"La salle est déjà occupée par un événement confirmé : {names}.")


def describe_slot(event) -> str:
    start = timezone.localtime(event.start)
    end = timezone.localtime(event.end)
    return f"{start:%d/%m %H:%M}–{end:%H:%M}"


def room_conflicts(room, start, end, *, exclude_id=None):
    """Événements confirmés qui occupent déjà cette salle sur ce créneau.

    Salles différentes, lieu libre et événements annulés ne sont jamais en conflit.
    """
    if room is None:
        return Event.objects.none()
    qs = Event.objects.filter(room=room, status=Event.Status.CONFIRMED).overlapping(start, end)
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    return qs


def warnings_for(event) -> list[str]:
    """Avertissements non bloquants : la salle est aussi visée par un autre événement."""
    if event.room_id is None or event.status == Event.Status.CANCELLED:
        return []
    others = (
        Event.objects.active()
        .filter(room_id=event.room_id)
        .overlapping(event.start, event.end)
        .exclude(pk=event.pk)
    )
    return [f"Même salle que « {o.title} » ({describe_slot(o)})" for o in others]


@dataclass
class ConfirmReport:
    confirmed: list = field(default_factory=list)
    refused: list = field(default_factory=list)  # paires (événement, message)


def create_from_idea(idea, *, start, end, room) -> Event:
    """Place une proposition dans le calendrier, en provisoire (hachuré)."""
    if end <= start:
        raise EventError("La fin doit être après le début.")
    return Event.objects.create(
        idea=idea,
        owner=idea.owner,
        owner_email=idea.owner_email,
        title=idea.title,
        description=idea.description,
        start=start,
        end=end,
        room=room,
        status=Event.Status.PROVISIONAL,
        # Une proposition extérieure est faite pour être vue : public par défaut, la case
        # reste modifiable par l'admin (fiche du POC, « Confirmer et publier »).
        is_public=True,
    )


@transaction.atomic
def move(event: Event, *, start, end, room, revision: int) -> Event:
    """Déplace ou redimensionne un événement (glisser-déposer ou formulaire)."""
    event = Event.objects.select_for_update().get(pk=event.pk)
    if revision != event.revision:
        raise StaleRevisionError()
    if event.status == Event.Status.CANCELLED:
        raise EventError("Un événement annulé ne se déplace pas.")
    if end <= start:
        raise EventError("La fin doit être après le début.")
    if event.status == Event.Status.CONFIRMED:
        conflicts = room_conflicts(room, start, end, exclude_id=event.pk)
        if conflicts.exists():
            raise RoomConflictError(conflicts)
    event.start, event.end, event.room = start, end, room
    event.revision += 1
    event.save(update_fields=["start", "end", "room", "revision", "updated_at"])
    return event


@transaction.atomic
def confirm(event: Event, *, user) -> Event:
    """Passe un événement en confirmé. Seul un conflit de salle l'empêche."""
    from apps.ideas import services as ideas_services  # les idées dépendent de l'agenda

    event = Event.objects.select_for_update().get(pk=event.pk)
    if event.status == Event.Status.CONFIRMED:
        return event
    if event.status == Event.Status.CANCELLED:
        raise EventError("Un événement annulé ne peut pas être confirmé.")
    conflicts = room_conflicts(event.room, event.start, event.end, exclude_id=event.pk)
    if conflicts.exists():
        raise RoomConflictError(conflicts)
    event.status = Event.Status.CONFIRMED
    event.confirmed_at = timezone.now()
    event.confirmed_by = user
    event.revision += 1
    event.save()
    if event.idea_id:
        ideas_services.mark_planned(event.idea)
    return event


def confirm_many(events, *, user) -> ConfirmReport:
    """Confirme une sélection, dans l'ordre chronologique.

    Chaque confirmation est indépendante : deux provisoires qui visent la même salle au
    même moment donnent un confirmé et un refus, pas un double booking.
    """
    report = ConfirmReport()
    for event in sorted(events, key=lambda e: e.start):
        try:
            report.confirmed.append(confirm(event, user=user))
        except EventError as error:
            report.refused.append((event, str(error)))
    return report


@transaction.atomic
def set_public(event: Event, *, is_public: bool) -> Event:
    event = Event.objects.select_for_update().get(pk=event.pk)
    event.is_public = is_public
    event.revision += 1
    event.save(update_fields=["is_public", "revision", "updated_at"])
    return event
