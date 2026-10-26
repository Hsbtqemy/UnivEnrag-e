from dataclasses import dataclass, field
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from apps.rooms.models import Room

from .models import Presence

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


def selections_for(actor, monday: date) -> dict:
    """{(jour, moment): lieu} des présences déclarées par `actor` cette semaine-là."""
    if actor is None:
        return {}
    return {(p.day, p.period): p.place for p in _week_of(actor, monday)}


def open_days_for(actor, monday: date) -> set[date]:
    """Les jours où `actor` tient une permanence ouverte au public."""
    if actor is None:
        return set()
    return set(_week_of(actor, monday).filter(is_open=True).values_list("day", flat=True))


def previous_week_selections(actor, monday: date) -> dict:
    """La semaine précédente, décalée d'une semaine : pour « reprendre ma semaine »."""
    previous = selections_for(actor, monday - timedelta(days=7))
    return {(day + timedelta(days=7), period): place for (day, period), place in previous.items()}


def previous_open_days(actor, monday: date) -> set[date]:
    return {day + timedelta(days=7) for day in open_days_for(actor, monday - timedelta(days=7))}


class PresenceError(ValueError):
    pass


@transaction.atomic
def save_week(actor, monday: date, selections: dict, open_days=()) -> int:
    """Remplace les présences de la semaine par `selections` ({(jour, moment): lieu}).

    Les jours de `open_days` deviennent des permanences ouvertes au public : elles
    exigent un lieu, puisque c'est tout ce que la page publique en montrera.
    """
    days = set(week_days(monday))
    open_days = set(open_days) & days
    for (day, _period), place in selections.items():
        if day in open_days and not place.strip():
            raise PresenceError(
                f"Indiquez un lieu pour la permanence du {day:%d/%m} : "
                "c'est ce que verra le public."
            )
    Presence.objects.filter(actor=actor, day__in=days).delete()
    created = [
        Presence(
            actor=actor,
            day=day,
            period=period,
            place=place.strip()[:80],
            is_open=day in open_days,
        )
        for (day, period), place in selections.items()
        if day in days and period in Presence.Period.values
    ]
    Presence.objects.bulk_create(created)
    return len(created)


@dataclass
class Cell:
    day: date
    period: str
    label: str
    people: list = field(default_factory=list)  # triplets (nom, lieu, permanence)


def board(monday: date) -> list[list[Cell]]:
    """Tableau « Qui est là ? » : une ligne par moment, une colonne par jour."""
    presences = (
        Presence.objects.filter(day__gte=monday, day__lte=monday + timedelta(days=6))
        .select_related("actor")
        .order_by("actor__display_name")
    )
    by_key = {}
    for p in presences:
        by_key.setdefault((p.day, p.period), []).append((p.actor.display_name, p.place, p.is_open))
    return [
        [
            Cell(day, period.value, period.label, by_key.get((day, period.value), []))
            for day in week_days(monday)
        ]
        for period in PERIODS
    ]


@dataclass
class PublicDay:
    day: date
    slots: list  # paires (moment, [lieux])


def public_permanences(days: int = 14) -> list[PublicDay]:
    """Les permanences des `days` prochains jours, regroupées par jour et par moment, avec
    leurs lieux seulement : aucun nom, aucun nombre de personnes (PUB-1, décision 23)."""
    until = timezone.localdate() + timedelta(days=days - 1)
    rows = (
        Presence.objects.public()
        .filter(day__lte=until)
        .values_list("day", "period", "place")
        .distinct()
    )
    by_day: dict[date, dict[str, set]] = {}
    for day, period, place in rows:
        by_day.setdefault(day, {}).setdefault(period, set()).add(place)
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
