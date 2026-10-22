"""Écritures sur l'agenda. Toute modification d'un événement passe par ici.

Chaque fonction reçoit qui agit : `actor` (le nom saisi par un participant) et/ou `user`
(un compte de gestion). Toute écriture est tracée dans l'historique de l'événement, et
dans le journal d'activité quand l'auteur est un compte de gestion.
"""

from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from apps.accounts.capabilities import has_capability
from apps.audit import audit

from . import history
from .models import Event, EventChange

Action = EventChange.Action


class EventError(Exception):
    """Opération refusée sur un événement ; le message s'affiche tel quel."""


class StaleRevisionError(EventError):
    def __init__(self):
        super().__init__(
            "Cet événement a été modifié entre-temps. L'affichage est rechargé : "
            "recommencez si besoin."
        )


class LockedError(EventError):
    def __init__(self):
        super().__init__("Cet événement est verrouillé : seul un gestionnaire peut le modifier.")


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


def can_manage(user) -> bool:
    return has_capability(user, "manage_agenda")


def can_publish(user) -> bool:
    return has_capability(user, "manage_agenda") or has_capability(user, "manage_public")


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
    if event.status == Event.Status.CANCELLED:
        return []
    return slot_warnings(event.room, event.start, event.end, exclude_id=event.pk)


def slot_warnings(room, start, end, *, exclude_id=None) -> list[str]:
    if room is None:
        return []
    others = Event.objects.active().filter(room=room).overlapping(start, end)
    if exclude_id is not None:
        others = others.exclude(pk=exclude_id)
    return [f"Même salle que « {o.title} » ({describe_slot(o)})" for o in others]


def _check_slot(start, end):
    if not start or not end or end <= start:
        raise EventError("La fin doit être après le début.")


def _check_room(event_status, room, start, end, *, exclude_id=None):
    if event_status == Event.Status.CONFIRMED:
        conflicts = room_conflicts(room, start, end, exclude_id=exclude_id)
        if conflicts.exists():
            raise RoomConflictError(conflicts)


def _lock_for_update(event: Event, *, user, revision: int | None) -> Event:
    event = Event.objects.select_for_update().get(pk=event.pk)
    if revision is not None and revision != event.revision:
        raise StaleRevisionError()
    if event.is_locked and not can_manage(user):
        raise LockedError()
    return event


def _save(event: Event, action: str, *, actor, user, before: dict, audit_action: str = ""):
    event.revision += 1
    event.save()
    history.record(event, action, actor=actor, user=user, before=before)
    if audit_action:
        audit.log(user, audit_action, event, changes=history.diff(before, history.snapshot(event)))
    return event


def _apply_public_wish(event: Event, wants_public: bool, user) -> None:
    """Case « public » : décision pour un habilité, simple demande pour un participant."""
    if can_publish(user):
        event.is_public = wants_public
        event.public_requested = False
    elif wants_public:
        event.public_requested = not event.is_public
    else:
        # Un participant peut toujours retirer un événement de l'agenda public.
        event.is_public = False
        event.public_requested = False


@dataclass
class ConfirmReport:
    confirmed: list = field(default_factory=list)
    refused: list = field(default_factory=list)  # paires (événement, message)


# --- Création ----------------------------------------------------------------------------


@transaction.atomic
def create(
    *,
    actor,
    user=None,
    title,
    start,
    end,
    room=None,
    place_text="",
    description="",
    visio_link="",
    wants_public=False,
) -> Event:
    """Un participant crée un événement : confirmé d'emblée s'il ne bloque aucune salle.

    CLAUDE.md, décision 10 : seuls les événements issus d'une idée commencent provisoires.
    """
    _check_slot(start, end)
    _check_room(Event.Status.CONFIRMED, room, start, end)
    event = Event(
        owner=actor,
        title=title,
        start=start,
        end=end,
        room=room,
        place_text=place_text,
        description=description,
        visio_link=visio_link,
        status=Event.Status.CONFIRMED,
        confirmed_at=timezone.now(),
        confirmed_by=user if can_manage(user) else None,
    )
    _apply_public_wish(event, wants_public, user)
    event.save()
    history.record(event, Action.CREATED, actor=actor, user=user, before={})
    audit.log(user, "agenda.event_created", event)
    return event


def create_from_idea(idea, *, start, end, room, user=None) -> Event:
    """Place une proposition dans le calendrier, en provisoire (hachuré)."""
    _check_slot(start, end)
    event = Event.objects.create(
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
    history.record(event, Action.PLACED, user=user, before={})
    return event


# --- Modifications -----------------------------------------------------------------------


@transaction.atomic
def update(
    event: Event,
    *,
    actor,
    user=None,
    revision: int,
    title,
    start,
    end,
    room=None,
    place_text="",
    description="",
    visio_link="",
    wants_public=None,
) -> Event:
    """Modification par le formulaire. `wants_public=None` laisse la publication en l'état."""
    event = _lock_for_update(event, user=user, revision=revision)
    if event.status == Event.Status.CANCELLED:
        raise EventError("Un événement annulé ne se modifie plus.")
    _check_slot(start, end)
    _check_room(event.status, room, start, end, exclude_id=event.pk)
    before = history.snapshot(event)
    event.title, event.start, event.end, event.room = title, start, end, room
    event.place_text, event.description, event.visio_link = place_text, description, visio_link
    if wants_public is not None:
        _apply_public_wish(event, wants_public, user)
    return _save(
        event,
        Action.UPDATED,
        actor=actor,
        user=user,
        before=before,
        audit_action="agenda.event_updated",
    )


@transaction.atomic
def move(event: Event, *, start, end, room, revision: int, actor=None, user=None) -> Event:
    """Déplace ou redimensionne un événement (glisser-déposer ou formulaire)."""
    event = _lock_for_update(event, user=user, revision=revision)
    if event.status == Event.Status.CANCELLED:
        raise EventError("Un événement annulé ne se déplace pas.")
    _check_slot(start, end)
    _check_room(event.status, room, start, end, exclude_id=event.pk)
    before = history.snapshot(event)
    event.start, event.end, event.room = start, end, room
    return _save(
        event,
        Action.MOVED,
        actor=actor,
        user=user,
        before=before,
        audit_action="agenda.event_moved",
    )


@transaction.atomic
def cancel(event: Event, *, actor, user=None, revision: int) -> Event:
    """Annule un événement : il reste visible, barré (CLAUDE.md AGE-1)."""
    event = _lock_for_update(event, user=user, revision=revision)
    if event.status == Event.Status.CANCELLED:
        return event
    before = history.snapshot(event)
    event.status = Event.Status.CANCELLED
    return _save(
        event,
        Action.CANCELLED,
        actor=actor,
        user=user,
        before=before,
        audit_action="agenda.event_cancelled",
    )


@transaction.atomic
def confirm(event: Event, *, user, actor=None) -> Event:
    """Passe un événement en confirmé. Seul un conflit de salle l'empêche."""
    from apps.ideas import services as ideas_services  # les idées dépendent de l'agenda

    if not can_manage(user):
        raise EventError("Seul un gestionnaire de l'agenda peut confirmer un événement.")
    event = Event.objects.select_for_update().get(pk=event.pk)
    if event.status == Event.Status.CONFIRMED:
        return event
    if event.status == Event.Status.CANCELLED:
        raise EventError("Un événement annulé ne peut pas être confirmé.")
    _check_room(Event.Status.CONFIRMED, event.room, event.start, event.end, exclude_id=event.pk)
    before = history.snapshot(event)
    event.status = Event.Status.CONFIRMED
    event.confirmed_at = timezone.now()
    event.confirmed_by = user
    _save(
        event,
        Action.CONFIRMED,
        actor=actor,
        user=user,
        before=before,
        audit_action="agenda.event_confirmed",
    )
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
def set_public(event: Event, *, is_public: bool, user) -> Event:
    if not can_publish(user):
        raise EventError("Seul un gestionnaire peut publier un événement.")
    event = Event.objects.select_for_update().get(pk=event.pk)
    before = history.snapshot(event)
    event.is_public = is_public
    event.public_requested = False
    return _save(
        event,
        Action.PUBLIC,
        actor=None,
        user=user,
        before=before,
        audit_action="agenda.event_public_changed",
    )


@transaction.atomic
def set_locked(event: Event, *, locked: bool, user) -> Event:
    if not can_manage(user):
        raise EventError("Seul un gestionnaire de l'agenda peut verrouiller un événement.")
    event = Event.objects.select_for_update().get(pk=event.pk)
    before = history.snapshot(event)
    event.is_locked = locked
    return _save(
        event,
        Action.LOCKED,
        actor=None,
        user=user,
        before=before,
        audit_action="agenda.event_locked" if locked else "agenda.event_unlocked",
    )


@transaction.atomic
def restore(event: Event, change: EventChange, *, user) -> Event:
    """Revient à l'état d'après `change` ; la restauration est elle-même tracée (AGE-4)."""
    if not can_manage(user):
        raise EventError("Seul un gestionnaire de l'agenda peut restaurer une version.")
    if change.event_id != event.pk:
        raise EventError("Cette version n'appartient pas à cet événement.")
    event = Event.objects.select_for_update().get(pk=event.pk)
    values = history.restore_values(change)
    _check_slot(values["start"], values["end"])
    _check_room(event.status, values["room"], values["start"], values["end"], exclude_id=event.pk)
    before = history.snapshot(event)
    for name, value in values.items():
        setattr(event, name, value)
    return _save(
        event,
        Action.RESTORED,
        actor=None,
        user=user,
        before=before,
        audit_action="agenda.event_restored",
    )
