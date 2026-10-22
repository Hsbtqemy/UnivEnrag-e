"""Écritures sur l'agenda. Toute modification d'un événement passe par ici.

Chaque fonction reçoit qui agit : `actor` (le nom saisi par un participant) et/ou `user`
(un compte de gestion). Toute écriture est tracée dans l'historique de l'événement, et
dans le journal d'activité quand l'auteur est un compte de gestion.
"""

from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from apps.accounts.capabilities import has_capability
from apps.actors.services import normalize_name
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


class RoomClosedError(EventError):
    """Réservation hors des plages d'ouverture de la salle (CLAUDE.md SAL-3)."""

    def __init__(self, room):
        super().__init__(
            f"« {room.name} » n'est pas ouverte sur ce créneau ({room.opening_summary()})."
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
    """Avertissements non bloquants (AGE-7) : même salle, ou mêmes intervenants."""
    if event.status == Event.Status.CANCELLED:
        return []
    return slot_warnings(
        event.room, event.start, event.end, exclude_id=event.pk, speakers=event.speakers
    )


def _speaker_keys(text: str) -> dict[str, str]:
    """Noms normalisés (casse, accents) → nom tel qu'écrit."""
    names = (name.strip() for name in text.split(","))
    return {normalize_name(name): name for name in names if normalize_name(name)}


def slot_warnings(room, start, end, *, exclude_id=None, speakers="") -> list[str]:
    return room_warnings(room, start, end, exclude_id=exclude_id) + speaker_warnings(
        speakers, start, end, exclude_id=exclude_id
    )


def _others(start, end, exclude_id):
    others = Event.objects.active().overlapping(start, end)
    return others.exclude(pk=exclude_id) if exclude_id is not None else others


def room_warnings(room, start, end, *, exclude_id=None) -> list[str]:
    """La salle est aussi visée par un autre événement sur ce créneau."""
    if room is None:
        return []
    others = _others(start, end, exclude_id).filter(room=room)
    return [f"Même salle que « {o.title} » ({describe_slot(o)})" for o in others]


def speaker_warnings(speakers, start, end, *, exclude_id=None) -> list[str]:
    """Un même intervenant est attendu ailleurs au même moment, quelle que soit la salle."""
    wanted = _speaker_keys(speakers)
    if not wanted:
        return []
    warnings = []
    for other in _others(start, end, exclude_id).exclude(speakers=""):
        shared = [wanted[key] for key in _speaker_keys(other.speakers) if key in wanted]
        if shared:
            warnings.append(
                f"Mêmes intervenants que « {other.title} » ({describe_slot(other)}) : "
                + ", ".join(shared)
            )
    return warnings


def _check_slot(start, end):
    if not start or not end or end <= start:
        raise EventError("La fin doit être après le début.")


def can_override(user) -> bool:
    """Dérogation (salle occupée ou fermée) : droit « salles » seulement (SAL-2, SAL-3)."""
    return has_capability(user, "manage_rooms")


def _check_booking(status, room, start, end, *, exclude_id=None, user=None, override=False):
    """Contrôle une réservation de salle ; renvoie les dérogations accordées.

    Seul un événement confirmé réserve : un provisoire ne fait qu'avertir.
    """
    if status != Event.Status.CONFIRMED or room is None:
        return []
    forced = override and can_override(user)
    derogations = []
    if not room.is_open(start, end):
        if not forced:
            raise RoomClosedError(room)
        derogations.append("hors des plages d'ouverture")
    conflicts = room_conflicts(room, start, end, exclude_id=exclude_id)
    if conflicts.exists():
        if not forced:
            raise RoomConflictError(conflicts)
        derogations.append("salle déjà occupée : " + ", ".join(e.title for e in conflicts))
    return derogations


def _new_booking_status(room, user) -> str:
    """Une salle « soumise à validation » met la réservation en attente (SAL-4)."""
    if room is None or not room.needs_approval or can_override(user):
        return Event.RoomStatus.APPROVED
    return Event.RoomStatus.PENDING


def _room_status_for(event: Event, room, start, end, user) -> str:
    """Comme `_new_booking_status`, mais garde la décision déjà prise tant que ni la salle
    ni le créneau ne changent."""
    unchanged = (
        event.pk
        and event.room_id == getattr(room, "pk", None)
        and (event.start == start and event.end == end)
    )
    if unchanged and not can_override(user):
        return event.room_status
    return _new_booking_status(room, user)


def _log_derogations(user, event, derogations):
    if derogations:
        audit.log(user, "rooms.derogation", event, reasons=derogations)


def _check_space(space):
    if space is not None and space.is_archived:
        raise EventError(
            f"L'espace « {space} » est archivé : on ne peut plus y ajouter d'événement."
        )


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
    space=None,
    place_text="",
    description="",
    visio_link="",
    speakers="",
    speakers_public=False,
    wants_public=False,
    override=False,
    idea=None,
) -> Event:
    """Un participant crée un événement : confirmé d'emblée s'il ne bloque aucune salle.

    CLAUDE.md, décision 10 : seuls les événements issus d'une idée (`idea`) commencent
    provisoires ; ils ne réservent la salle qu'à la confirmation.
    """
    _check_slot(start, end)
    _check_space(space)
    status = Event.Status.PROVISIONAL if idea is not None else Event.Status.CONFIRMED
    derogations = _check_booking(status, room, start, end, user=user, override=override)
    event = Event(
        idea=idea,
        owner=actor,
        title=title,
        start=start,
        end=end,
        room=room,
        space=space,
        place_text=place_text,
        description=description,
        visio_link=visio_link,
        speakers=speakers,
        speakers_public=speakers_public,
        status=status,
    )
    if status == Event.Status.CONFIRMED:
        event.confirmed_at = timezone.now()
        event.confirmed_by = user if can_manage(user) else None
    event.room_status = _room_status_for(event, room, start, end, user)
    _apply_public_wish(event, wants_public, user)
    event.save()
    history.record(event, Action.CREATED, actor=actor, user=user, before={})
    audit.log(user, "agenda.event_created", event)
    _log_derogations(user, event, derogations)
    return event


def create_from_idea(idea, *, start, end, room, actor=None, user=None) -> Event:
    """Place une idée dans le calendrier, en provisoire (hachuré), pré-remplie : titre,
    description, intervenants, salle (IDE-3)."""
    _check_slot(start, end)
    event = Event.objects.create(
        idea=idea,
        owner=idea.owner,
        owner_email=idea.owner_email,
        title=idea.title,
        description=idea.description,
        speakers=idea.speakers_text,
        start=start,
        end=end,
        room=room,
        space=idea.space if idea.space_id and not idea.space.is_archived else None,
        status=Event.Status.PROVISIONAL,
        # Une proposition extérieure est faite pour être vue : public par défaut, la case
        # reste modifiable par l'admin (fiche du POC, « Confirmer et publier »). L'idée
        # d'un membre suit la règle commune : rien n'est public par défaut (PUB-1).
        is_public=idea.is_external,
    )
    history.record(event, Action.PLACED, actor=actor, user=user, before={})
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
    space=None,
    place_text="",
    description="",
    visio_link="",
    speakers="",
    speakers_public=False,
    wants_public=None,
    override=False,
) -> Event:
    """Modification par le formulaire. `wants_public=None` laisse la publication en l'état."""
    event = _lock_for_update(event, user=user, revision=revision)
    if event.status == Event.Status.CANCELLED:
        raise EventError("Un événement annulé ne se modifie plus.")
    _check_slot(start, end)
    if space is not None and space.pk != event.space_id:
        _check_space(space)
    derogations = _check_booking(
        event.status, room, start, end, exclude_id=event.pk, user=user, override=override
    )
    before = history.snapshot(event)
    event.room_status = _room_status_for(event, room, start, end, user)
    event.title, event.start, event.end, event.room = title, start, end, room
    event.space = space
    event.place_text, event.description, event.visio_link = place_text, description, visio_link
    event.speakers, event.speakers_public = speakers, speakers_public
    if wants_public is not None:
        _apply_public_wish(event, wants_public, user)
    _save(
        event,
        Action.UPDATED,
        actor=actor,
        user=user,
        before=before,
        audit_action="agenda.event_updated",
    )
    _log_derogations(user, event, derogations)
    return event


@transaction.atomic
def move(
    event: Event, *, start, end, room, revision: int, actor=None, user=None, override=False
) -> Event:
    """Déplace ou redimensionne un événement (glisser-déposer ou formulaire)."""
    event = _lock_for_update(event, user=user, revision=revision)
    if event.status == Event.Status.CANCELLED:
        raise EventError("Un événement annulé ne se déplace pas.")
    _check_slot(start, end)
    derogations = _check_booking(
        event.status, room, start, end, exclude_id=event.pk, user=user, override=override
    )
    _log_derogations(user, event, derogations)
    before = history.snapshot(event)
    event.room_status = _room_status_for(event, room, start, end, user)
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
    from apps.ideas import services as ideas_services  # les idées dépendent de l'agenda

    event = _lock_for_update(event, user=user, revision=revision)
    if event.status == Event.Status.CANCELLED:
        return event
    before = history.snapshot(event)
    event.status = Event.Status.CANCELLED
    _save(
        event,
        Action.CANCELLED,
        actor=actor,
        user=user,
        before=before,
        audit_action="agenda.event_cancelled",
    )
    if event.idea_id:
        ideas_services.event_cancelled(event.idea)
    return event


@transaction.atomic
def confirm(event: Event, *, user, actor=None, override=False) -> Event:
    """Passe un événement en confirmé. Seul un conflit de salle l'empêche."""
    from apps.ideas import services as ideas_services  # les idées dépendent de l'agenda

    if not can_manage(user):
        raise EventError("Seul un gestionnaire de l'agenda peut confirmer un événement.")
    event = Event.objects.select_for_update().get(pk=event.pk)
    if event.status == Event.Status.CONFIRMED:
        return event
    if event.status == Event.Status.CANCELLED:
        raise EventError("Un événement annulé ne peut pas être confirmé.")
    derogations = _check_booking(
        Event.Status.CONFIRMED,
        event.room,
        event.start,
        event.end,
        exclude_id=event.pk,
        user=user,
        override=override,
    )
    _log_derogations(user, event, derogations)
    before = history.snapshot(event)
    # Confirmer, c'est réserver : une salle soumise à validation passe en attente.
    event.room_status = _new_booking_status(event.room, user)
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
    _check_booking(
        event.status, values["room"], values["start"], values["end"], exclude_id=event.pk, user=user
    )
    before = history.snapshot(event)
    event.room_status = _room_status_for(
        event, values["room"], values["start"], values["end"], user
    )
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


# --- Validation des réservations de salle -------------------------------------------------


@transaction.atomic
def approve_room(event: Event, *, user) -> Event:
    if not can_override(user):
        raise EventError("Seul un gestionnaire des salles peut valider une réservation.")
    event = Event.objects.select_for_update().get(pk=event.pk)
    if not event.room_pending:
        return event
    before = history.snapshot(event)
    event.room_status = Event.RoomStatus.APPROVED
    return _save(
        event,
        Action.ROOM,
        actor=None,
        user=user,
        before=before,
        audit_action="rooms.booking_approved",
    )


@transaction.atomic
def refuse_room(event: Event, *, user, reason: str = "") -> Event:
    """Refus : l'événement garde sa date mais perd la salle (« Lieu à préciser »)."""
    if not can_override(user):
        raise EventError("Seul un gestionnaire des salles peut refuser une réservation.")
    event = Event.objects.select_for_update().get(pk=event.pk)
    if not event.room_pending:
        raise EventError("Cette réservation n'est pas en attente.")
    before = history.snapshot(event)
    room_name = event.room.name
    event.room = None
    event.room_status = Event.RoomStatus.APPROVED
    _save(
        event,
        Action.ROOM,
        actor=None,
        user=user,
        before=before,
        audit_action="rooms.booking_refused",
    )
    audit.log(user, "rooms.booking_refused_reason", event, room=room_name, reason=reason)
    return event
