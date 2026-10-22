"""Flux iCal public : événements confirmés et publics uniquement."""

from django.utils import timezone
from icalendar import Calendar
from icalendar import Event as IcalEvent

from .models import Event


def public_calendar(events, *, base_url: str, name: str) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//Plateforme du collectif//Agenda//FR")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", name)
    cal.add("x-wr-timezone", "Europe/Paris")
    now = timezone.now()
    for event in events:
        item = IcalEvent()
        item.add("uid", f"evenement-{event.pk}@{base_url.split('://')[-1].rstrip('/')}")
        item.add("dtstamp", now)
        item.add("dtstart", event.start)
        item.add("dtend", event.end)
        item.add("summary", event.title)
        # Le nom du porteur est public, son e-mail jamais (CLAUDE.md PUB-2).
        description = f"Porté par {event.owner.display_name}"
        if event.description:
            description += f"\n\n{event.description}"
        item.add("description", description)
        item.add("location", event.place_label)
        item.add("url", f"{base_url.rstrip('/')}/agenda/{event.pk}/")
        item.add("status", "CONFIRMED")
        cal.add_component(item)
    return cal.to_ical()


def public_events():
    return Event.objects.public().select_related("owner", "room").order_by("start")
