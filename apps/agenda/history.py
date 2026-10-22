"""Instantanés et différences d'un événement, pour l'historique (CLAUDE.md AGE-4)."""

from datetime import datetime

from django.utils import timezone

from apps.rooms.models import Room

from .models import Event, EventChange

# Champs suivis, dans l'ordre d'affichage.
FIELD_LABELS = {
    "title": "titre",
    "start": "début",
    "end": "fin",
    "room": "salle",
    "place_text": "lieu libre",
    "description": "description",
    "visio_link": "lien visio",
    "status": "statut",
    "is_public": "public",
    "public_requested": "publication demandée",
    "is_locked": "verrouillé",
}

# Champs qu'une restauration remet en place ; le verrou et la publication restent des
# décisions du moment, pas des éléments de la version restaurée.
RESTORABLE_FIELDS = ["title", "start", "end", "room", "place_text", "description", "visio_link"]


def snapshot(event: Event) -> dict:
    data = {}
    for name in FIELD_LABELS:
        value = event.room_id if name == "room" else getattr(event, name)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[name] = value
    return data


def diff(before: dict, after: dict) -> dict:
    return {
        name: [before.get(name), after.get(name)]
        for name in FIELD_LABELS
        if before.get(name) != after.get(name)
    }


def record(event: Event, action: str, *, actor=None, user=None, before: dict | None = None):
    after = snapshot(event)
    return EventChange.objects.create(
        event=event,
        action=action,
        actor=actor,
        user=user if user is not None and user.is_authenticated else None,
        # Une création n'a pas d'« avant » : l'instantané suffit, sans liste de différences.
        changes=diff(before, after) if before else {},
        snapshot=after,
    )


def restore_values(change: EventChange) -> dict:
    """Valeurs à remettre en place pour revenir à l'état d'après `change`."""
    values = {}
    for name in RESTORABLE_FIELDS:
        value = change.snapshot.get(name)
        if name in ("start", "end") and value:
            value = datetime.fromisoformat(value)
        if name == "room":
            value = Room.objects.filter(pk=value).first() if value else None
        values[name] = value
    return values


def _display(name: str, value) -> str:
    if value in (None, ""):
        return "—"
    if name in ("start", "end"):
        return f"{timezone.localtime(datetime.fromisoformat(value)):%d/%m/%Y %H:%M}"
    if name == "room":
        room = Room.objects.filter(pk=value).first()
        return room.name if room else "salle supprimée"
    if name == "status":
        return Event.Status(value).label
    if isinstance(value, bool):
        return "oui" if value else "non"
    text = str(value)
    return text if len(text) <= 60 else f"{text[:57]}…"


def describe(change: EventChange) -> list[str]:
    """Lignes lisibles : « début : 10/11/2026 10:00 → 10/11/2026 14:00 »."""
    return [
        f"{FIELD_LABELS[name]} : {_display(name, old)} → {_display(name, new)}"
        for name, (old, new) in change.changes.items()
        if name in FIELD_LABELS
    ]
