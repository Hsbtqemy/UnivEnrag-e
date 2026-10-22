"""Mise en forme des événements pour @event-calendar.

Deux formats bien séparés : le public ne reçoit jamais l'e-mail du porteur ni aucun
événement non public (CLAUDE.md PUB-1, PUB-2).
"""

from django.urls import reverse

from apps.core.dates import to_wall_clock

from .models import Event

FREE_PLACE_RESOURCE = "lieu-libre"


def resource_id(event: Event) -> str:
    return str(event.room_id) if event.room_id else FREE_PLACE_RESOURCE


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


def gestion_event(event: Event, warnings: list[str]) -> dict:
    classes = [f"ev-{event.status}"]
    if warnings:
        classes.append("ev-warning")
    if not event.is_public:
        classes.append("ev-private")
    return {
        "id": str(event.pk),
        "title": event.title,
        "start": to_wall_clock(event.start),
        "end": to_wall_clock(event.end),
        "resourceId": resource_id(event),
        "color": event.room.color if event.room_id else "#6b7280",
        "classNames": classes,
        "editable": event.status != Event.Status.CANCELLED,
        "extendedProps": {
            "kind": "event",
            "status": event.status,
            "statusLabel": event.get_status_display(),
            "revision": event.revision,
            "owner": event.owner.display_name,
            "ownerEmail": event.owner_email,
            "place": event.place_label,
            "roomId": event.room_id,
            "isPublic": event.is_public,
            "warnings": warnings,
            "adminUrl": reverse("admin:agenda_event_change", args=[event.pk]),
        },
    }


def alternative_slot(event: Event, slot) -> dict:
    """Autre créneau envisagé d'une proposition placée, affiché en pointillé."""
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
            "eventId": event.pk,
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
