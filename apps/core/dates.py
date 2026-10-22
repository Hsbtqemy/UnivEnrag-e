"""Échange des dates avec @event-calendar.

La bibliothèque travaille en heure murale, sans fuseau : on lui envoie et on reçoit des
chaînes « AAAA-MM-JJTHH:MM:SS » en heure de Paris, converties ici en dates conscientes.
"""

from datetime import date, datetime, time

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime


def to_wall_clock(dt: datetime) -> str:
    return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M:%S")


def from_wall_clock(value: str) -> datetime | None:
    """Analyse une heure murale (ou une date seule, prise à minuit). None si invalide."""
    if not value:
        return None
    value = value.strip().replace(" ", "T")
    # Un éventuel décalage horaire est ignoré : la bibliothèque n'en produit pas, et
    # l'heure affichée à l'écran est celle qui fait foi.
    for sep in ("+", "Z"):
        if sep in value[10:]:
            value = value[: 10 + value[10:].index(sep)]
    try:
        parsed = parse_datetime(value)
        if parsed is None:
            day = parse_date(value)
            if day is None:
                return None
            parsed = datetime.combine(day, time.min)
    except ValueError:
        return None
    if timezone.is_aware(parsed):
        parsed = timezone.make_naive(parsed)
    return timezone.make_aware(parsed)


def combine(day: date, hour: time) -> datetime:
    return timezone.make_aware(datetime.combine(day, hour))
