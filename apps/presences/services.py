from dataclasses import dataclass, field
from datetime import date, time, timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.dates import format_fr
from apps.rooms.models import Room

from .models import Presence, hours_label

PERIODS = list(Presence.Period)
# Une présence dit où l'on sera : au-delà de deux mois passés, elle ne sert plus à rien
# et on ne garde pas cette trace de chacun (RGPD, CDC §9).
RETENTION_DAYS = 60


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_days(monday: date) -> list[date]:
    return [monday + timedelta(days=i) for i in range(7)]


def parse_week(value: str | None) -> date:
    try:
        return week_start(date.fromisoformat(value)) if value else week_start(timezone.localdate())
    except ValueError:
        return week_start(timezone.localdate())


def _week_of(actor, monday: date):
    return Presence.objects.filter(
        actor=actor, day__gte=monday, day__lte=monday + timedelta(days=6)
    )


@dataclass(frozen=True)
class Declared:
    """Ce qu'une personne déclare pour une demi-journée : un lieu et des heures, facultatifs."""

    place: str = ""
    start: time | None = None
    end: time | None = None


def _as_declared(value) -> Declared:
    return value if isinstance(value, Declared) else Declared(place=value or "")


def selections_for(actor, monday: date) -> dict:
    """{(jour, moment): Declared} des présences déclarées par `actor` cette semaine-là."""
    if actor is None:
        return {}
    return {
        (p.day, p.period): Declared(p.place, p.start_time, p.end_time)
        for p in _week_of(actor, monday)
    }


def open_days_for(actor, monday: date) -> set[date]:
    """Les jours où `actor` tient une permanence ouverte au public."""
    if actor is None:
        return set()
    return set(_week_of(actor, monday).filter(is_open=True).values_list("day", flat=True))


def previous_week_selections(actor, monday: date) -> dict:
    """La semaine précédente, décalée d'une semaine : pour « reprendre ma semaine »."""
    previous = selections_for(actor, monday - timedelta(days=7))
    return {(day + timedelta(days=7), period): d for (day, period), d in previous.items()}


def previous_open_days(actor, monday: date) -> set[date]:
    return {day + timedelta(days=7) for day in open_days_for(actor, monday - timedelta(days=7))}


class PresenceError(ValueError):
    pass


@transaction.atomic
def save_week(actor, monday: date, selections: dict, open_days=()) -> int:
    """Remplace les présences de la semaine par `selections`.

    `selections` vaut {(jour, moment): Declared} (ou un simple lieu). Les jours de
    `open_days` deviennent des permanences ouvertes au public (décision 23).
    """
    days = set(week_days(monday))
    open_days = set(open_days) & days
    declared = {key: _as_declared(value) for key, value in selections.items()}
    for (day, _period), d in declared.items():
        if d.start and d.end and d.end <= d.start:
            raise PresenceError(
                f"Le {day:%d/%m}, l'heure de fin doit venir après l'heure de début."
            )
    Presence.objects.filter(actor=actor, day__in=days).delete()
    created = [
        Presence(
            actor=actor,
            day=day,
            period=period,
            place=d.place.strip()[:80],
            start_time=d.start,
            end_time=d.end,
            is_open=day in open_days,
        )
        for (day, period), d in declared.items()
        if day in days and period in Presence.Period.values
    ]
    Presence.objects.bulk_create(created)
    return len(created)


@dataclass
class Cell:
    day: date
    period: str
    label: str
    people: list = field(default_factory=list)  # objets Presence, acteur compris


def board(monday: date) -> list[list[Cell]]:
    """Tableau « Qui est là ? » : une ligne par moment, une colonne par jour."""
    presences = (
        Presence.objects.filter(day__gte=monday, day__lte=monday + timedelta(days=6))
        .select_related("actor")
        .order_by("actor__display_name")
    )
    by_key = {}
    for p in presences:
        by_key.setdefault((p.day, p.period), []).append(p)
    return [
        [
            Cell(day, period.value, period.label, by_key.get((day, period.value), []))
            for day in week_days(monday)
        ]
        for period in PERIODS
    ]


@dataclass
class Day:
    day: date
    label: str  # « Aujourd'hui », « Demain » ou « Mercredi 28 octobre »
    entries: list  # paires (moment, Presence), dans l'ordre de la journée
    is_today: bool = False


def days_list(monday: date) -> list[Day]:
    """La semaine en liste, pour un téléphone : à partir d'aujourd'hui si c'est la semaine
    en cours (les jours passés n'aident plus à se coordonner)."""
    today = timezone.localdate()
    rows = board(monday)
    result = []
    for index, day in enumerate(week_days(monday)):
        if day < today and monday <= today:
            continue
        entries = [(row[index].label, p) for row in rows for p in row[index].people]
        if day == today:
            label = "Aujourd'hui"
        elif day == today + timedelta(days=1):
            label = "Demain"
        else:
            label = format_fr(day, "l j F").capitalize()
        result.append(Day(day, label, entries, is_today=day == today))
    return result


@dataclass
class PublicDay:
    day: date
    slots: list  # paires (moment, [« 14:00 – 17:00, Local »…])


def _public_text(start, end, place) -> str:
    return ", ".join(part for part in (hours_label(start, end), place) if part)


def public_permanences(days: int = 14) -> list[PublicDay]:
    """Les permanences des `days` prochains jours, regroupées par jour et par moment, avec
    leurs heures et leurs lieux seulement : aucun nom, aucun nombre de personnes (PUB-1,
    décision 23)."""
    until = timezone.localdate() + timedelta(days=days - 1)
    rows = (
        Presence.objects.public()
        .filter(day__lte=until)
        .values_list("day", "period", "start_time", "end_time", "place")
        .distinct()
    )
    by_day: dict[date, dict[str, set]] = {}
    for day, period, start, end, place in rows:
        texts = by_day.setdefault(day, {}).setdefault(period, set())
        text = _public_text(start, end, place)
        if text:
            texts.add(text)
    return [
        PublicDay(
            day,
            [
                (period.label, sorted(by_day[day][period.value]))
                for period in PERIODS
                if period.value in by_day[day]
            ],
        )
        for day in sorted(by_day)
    ]


def count_people(monday: date) -> int:
    return (
        Presence.objects.filter(day__gte=monday, day__lte=monday + timedelta(days=6))
        .values("actor")
        .distinct()
        .count()
    )


def known_places() -> list[str]:
    """Suggestions de lieux : salles, bâtiments et lieux déjà saisis."""
    places = set()
    for room in Room.objects.filter(is_active=True):
        places.add(room.name)
        if room.building:
            places.add(room.building)
    places.update(
        Presence.objects.exclude(place="").values_list("place", flat=True).distinct()[:50]
    )
    return sorted(places)


def purge(days: int = RETENTION_DAYS) -> int:
    limit = timezone.localdate() - timedelta(days=days)
    deleted, _ = Presence.objects.filter(day__lt=limit).delete()
    return deleted
