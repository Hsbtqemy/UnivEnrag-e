"""Mise en forme des événements pour @event-calendar.

Deux formats bien séparés : le public ne reçoit jamais l'e-mail du porteur ni aucun
événement non public (CLAUDE.md PUB-1, PUB-2).
"""

from django.http import Http404
from django.urls import reverse

from apps.core.dates import to_wall_clock
from apps.rooms.models import Room

from .models import Event

FREE_PLACE_RESOURCE = "lieu-libre"


def resource_id(event: Event) -> str:
    return str(event.room_id) if event.room_id else FREE_PLACE_RESOURCE


def room_from_resource(value):
    """Inverse de `resource_id` : `lieu-libre` ou vide → pas de salle."""
    if value in (None, "", FREE_PLACE_RESOURCE):
        return None
    try:
        return Room.objects.get(pk=int(value))
    except (Room.DoesNotExist, TypeError, ValueError):
        raise Http404("Salle inconnue.") from None


def public_event(event: Event) -> dict:
    return {
        "id": event.pk,
        "title": event.title,
        "start": to_wall_clock(event.start),
        "end": to_wall_clock(event.end),
        "color": event.room.color if event.room_id else None,
        "extendedProps": {
            "url": reverse("agenda:public_detail", args=[event.pk]),
            "place": event.place_label,
            "owner": event.owner.display_name,
        },
    }


def programming_event(
    event: Event, warnings: list[str], *, editable: bool, show_email: bool
) -> dict:
    """Vue de programmation : ouverte aux membres, l'e-mail du porteur reste à la gestion
    (CLAUDE.md PUB-2)."""
    classes = [f"ev-{event.status}"]
    if warnings:
        classes.append("ev-warning")
    if not event.is_public:
        classes.append("ev-private")
    if event.is_locked:
        classes.append("ev-locked")
    idea = event.idea if event.idea_id else None
    return {
        "id": str(event.pk),
        "title": event.title,
        "start": to_wall_clock(event.start),
        "end": to_wall_clock(event.end),
        "resourceId": resource_id(event),
        "color": event.display_color,
        "classNames": classes,
        "editable": editable and event.status != Event.Status.CANCELLED,
        "extendedProps": {
            "kind": "event",
            "status": event.status,
            "statusLabel": event.get_status_display(),
            "revision": event.revision,
            "owner": event.owner.display_name,
            "ownerEmail": event.owner_email if show_email else "",
            "place": event.place_label,
            "roomId": event.room_id,
            "spaceId": event.space_id,
            "ideaKind": idea.kind if idea else "",
            "audience": idea.audience if idea else "",
            "ideaUrl": reverse("ideas:detail", args=[idea.pk]) if idea else "",
            "isPublic": event.is_public,
            "locked": event.is_locked,
            "warnings": warnings,
            "url": reverse("agenda:detail", args=[event.pk]),
        },
    }


def alternative_slot(event: Event, slot) -> dict:
    """Autre créneau envisagé d'une idée placée, affiché en pointillé (IDE-2)."""
    return {
        "id": f"alt-{slot.pk}",
        "title": f"Autre créneau : {event.title}",
        "start": to_wall_clock(slot.start),
        "end": to_wall_clock(slot.end),
        "resourceId": resource_id(event),
        "classNames": ["ev-alternative"],
        "editable": False,
        "extendedProps": {
            "kind": "alternative",
            "status": event.status,
            "spaceId": event.space_id,
            "ideaKind": event.idea.kind,
            "audience": event.idea.audience,
            "eventId": event.pk,
            "eventTitle": event.title,
            "revision": event.revision,
            "start": to_wall_clock(slot.start),
            "end": to_wall_clock(slot.end),
        },
    }


def member_event(event: Event, *, editable: bool) -> dict:
    """Agenda des membres : tous les événements, annulés compris (barrés), sans e-mail."""
    classes = [f"ev-{event.status}"]
    if event.is_locked:
        classes.append("ev-locked")
    if event.room_pending:
        classes.append("ev-room-pending")
    return {
        "id": str(event.pk),
        "title": event.title,
        "start": to_wall_clock(event.start),
        "end": to_wall_clock(event.end),
        "color": event.display_color,
        "classNames": classes,
        "editable": editable and event.status != Event.Status.CANCELLED,
        "extendedProps": {
            "url": reverse("agenda:detail", args=[event.pk]),
            "revision": event.revision,
            "status": event.status,
            "statusLabel": event.get_status_display(),
            "place": event.place_label,
            "owner": event.owner.display_name,
            "roomId": event.room_id,
            "spaceId": event.space_id,
            "roomPending": event.room_pending,
            "locked": event.is_locked,
        },
    }
