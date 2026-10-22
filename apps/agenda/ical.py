"""Flux iCal : agenda public, et agenda des membres par jeton (global, espace, salle)."""

from datetime import timedelta

from django.utils import timezone
from icalendar import Calendar
from icalendar import Event as IcalEvent

from .models import Event

ICAL_STATUS = {
    Event.Status.CONFIRMED: "CONFIRMED",
    Event.Status.PROVISIONAL: "TENTATIVE",
    Event.Status.CANCELLED: "CANCELLED",
}


def _host(base_url: str) -> str:
    return base_url.split("://")[-1].rstrip("/")


def build_calendar(events, *, base_url: str, name: str, detail_path, with_visio=True) -> bytes:
    """`detail_path(event)` donne le chemin de la fiche à mettre en lien."""
    cal = Calendar()
    cal.add("prodid", "-//Plateforme du collectif//Agenda//FR")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", name)
    cal.add("x-wr-timezone", "Europe/Paris")
    now = timezone.now()
    for event in events:
        item = IcalEvent()
        item.add("uid", f"evenement-{event.pk}@{_host(base_url)}")
        item.add("dtstamp", now)
        item.add("last-modified", event.updated_at)
        item.add("sequence", event.revision)
        item.add("dtstart", event.start)
        item.add("dtend", event.end)
        item.add("summary", event.title)
        # Le nom du porteur est affiché, son e-mail jamais (CLAUDE.md PUB-2).
        description = f"Porté par {event.owner.display_name}"
        # Flux public : intervenants seulement s'ils sont déclarés publics (PUB-1).
        if event.speakers and (with_visio or event.speakers_public):
            description += f"\nIntervenants : {event.speakers}"
        if with_visio and event.visio_link:
            description += f"\nVisio : {event.visio_link}"
        if event.description:
            description += f"\n\n{event.description}"
        item.add("description", description)
        item.add("location", event.place_label)
        item.add("url", f"{base_url.rstrip('/')}{detail_path(event)}")
        item.add("status", ICAL_STATUS[event.status])
        cal.add_component(item)
    return cal.to_ical()


def public_calendar(events, *, base_url: str, name: str) -> bytes:
    return build_calendar(
        events,
        base_url=base_url,
        name=name,
        detail_path=lambda e: f"/p/agenda/{e.pk}/",
        with_visio=False,  # flux public : ni visio, ni intervenants non publics
    )


def public_events():
    return Event.objects.public().select_related("owner", "room").order_by("start")


def member_events():
    """Fenêtre glissante : deux mois en arrière, un an en avant, annulés compris."""
    now = timezone.now()
    return (
        Event.objects.filter(
            end__gte=now - timedelta(days=60), start__lte=now + timedelta(days=365)
        )
        .select_related("owner", "room")
        .order_by("start")
    )
