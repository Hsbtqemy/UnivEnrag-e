"""Lecture des compteurs de pages vues pour la gestion (décision 28).

Les compteurs vivent dans `core` ; c'est ici, au sommet des dépendances, qu'on leur donne
un nom lisible (titre d'un événement, d'une actualité, d'une idée).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Sum

from apps.agenda.models import Event
from apps.core.dates import format_fr
from apps.core.models import PageCount
from apps.ideas.models import Idea

from .models import NewsPost

Kind = PageCount.Kind

PERIODS = {
    "7": (7, "7 derniers jours"),
    "30": (30, "30 derniers jours"),
    "365": (365, "12 derniers mois"),
}
DEFAULT_PERIOD = "30"
TOP = 15

PAGE_LABELS = {
    # Site public
    "public:home": "Page d'accueil",
    "agenda:public_list": "Agenda",
    "agenda:public_week": "Agenda, semaine",
    "agenda:public_print": "Agenda à imprimer",
    "public:news_list": "Actualités",
    "public:contact": "Nous écrire",
    "ideas:public_list": "Idées",
    "ideas:propose": "Proposer une idée",
    "ideas:sent": "Idée envoyée (confirmation)",
    "ideas:track": "Suivi d'une proposition",
    "core:privacy": "Données personnelles",
    # Flux
    "agenda:public_ics": "Agenda public (iCal)",
    "agenda:public_download": "Agenda public téléchargé (iCal)",
    "public:news_feed": "Actualités (RSS)",
    "agenda:feed_all": "Agenda des membres (iCal)",
    "agenda:feed_space": "Agenda d'un espace (iCal)",
    "agenda:feed_room": "Agenda d'une salle (iCal)",
    # Espace des membres
    "core:access": "Saisie du code d'accès",
    "core:help": "Aide",
    "core:offline": "Page hors ligne",
    "agenda:home": "Accueil des membres",
    "agenda:calendar": "Agenda",
    "agenda:detail": "Fiche d'un événement",
    "agenda:new": "Nouvel événement",
    "agenda:edit": "Modifier un événement",
    "agenda:programming": "Programmation",
    "agenda:rooms": "Salles",
    "agenda:subscriptions": "S'abonner",
    "agenda:export": "Exporter ou imprimer",
    "ideas:list": "Idées",
    "ideas:new": "Déposer une idée",
    "ideas:detail": "Fiche d'une idée",
    "ideas:edit": "Modifier une idée",
    "presences:board": "Qui est là ?",
    "presences:my_week": "Ma semaine",
    "actors:name": "Indiquer son nom",
}


@dataclass
class Bar:
    label: str
    count: str  # déjà écrit à la française (« 9 952 »)
    percent: float  # largeur de la barre, par rapport à la plus grande


def number(value: int) -> str:
    """9952 → « 9 952 », avec une espace fine insécable."""
    return f"{value:,}".replace(",", "\u202f")


def _bars(rows: list[tuple[str, int]]) -> list[Bar]:
    biggest = max((count for _, count in rows), default=0) or 1
    return [Bar(label, number(count), round(100 * count / biggest, 1)) for label, count in rows]


def _start(days: int, today: date) -> date:
    """Premier jour compté. Sur un an : douze mois entiers, le mois en cours compris, pour
    que chaque barre soit un mois complet (sauf le mois en cours)."""
    if days <= 31:
        return today - timedelta(days=days - 1)
    month = today.month - 11
    return date(today.year + (month - 1) // 12, (month - 1) % 12 + 1, 1)


def summary(period: str, today: date) -> dict:
    days, period_label = PERIODS.get(period, PERIODS[DEFAULT_PERIOD])
    start = _start(days, today)
    counts = PageCount.objects.filter(day__gte=start, day__lte=today)
    totals = {row["kind"]: row["n"] for row in counts.values("kind").annotate(n=Sum("count"))}
    return {
        "period_label": period_label,
        "tiles": [
            (Kind.PUBLIC.label, number(totals.get(Kind.PUBLIC, 0))),
            (Kind.MEMBERS.label, number(totals.get(Kind.MEMBERS, 0))),
            (Kind.FEED.label, number(totals.get(Kind.FEED, 0))),
            (Kind.BOARD.label, number(totals.get(Kind.BOARD, 0))),
        ],
        "timeline": _timeline(counts, start, today, by_month=days > 31),
        "by_month": days > 31,
        "public_pages": _top(counts, Kind.PUBLIC),
        "member_pages": _top(counts, Kind.MEMBERS),
        "feeds": _top(counts, Kind.FEED),
        "sources": _bars(
            list(
                counts.filter(kind=Kind.SOURCE)
                .values_list("key")
                .annotate(n=Sum("count"))
                .order_by("-n", "key")[:TOP]
            )
        ),
    }


def _timeline(counts, start, today, *, by_month) -> list[Bar]:
    """Pages publiques vues, jour par jour (ou mois par mois sur un an), jours vides compris."""
    per_day = dict(counts.filter(kind=Kind.PUBLIC).values_list("day").annotate(n=Sum("count")))
    if not by_month:
        span = (today - start).days + 1
        days = [start + timedelta(days=i) for i in range(span)]
        return _bars([(format_fr(d, "D j F"), per_day.get(d, 0)) for d in days])
    months: dict[tuple[int, int], int] = {}
    cursor = date(start.year, start.month, 1)
    while cursor <= today:
        months[(cursor.year, cursor.month)] = 0
        cursor = date(cursor.year + cursor.month // 12, cursor.month % 12 + 1, 1)
    for day, n in per_day.items():
        months[(day.year, day.month)] += n
    return _bars(
        [(format_fr(date(y, m, 1), "F Y").capitalize(), n) for (y, m), n in months.items()]
    )


def _top(counts, kind) -> list[Bar]:
    rows = list(
        counts.filter(kind=kind).values_list("key").annotate(n=Sum("count")).order_by("-n", "key")
    )[:TOP]
    labels = _labels([key for key, _ in rows])
    return _bars([(labels[key], n) for key, n in rows])


def _labels(keys: list[str]) -> dict[str, str]:
    """Nom lisible de chaque page ; pour une fiche publique, le titre de l'objet."""
    wanted = {
        "agenda:public_detail": set(),
        "public:news_detail": set(),
        "ideas:public_detail": set(),
    }
    for key in keys:
        view, _, ref = key.rpartition(":")
        if view in wanted:
            wanted[view].add(ref)
    events = dict(
        Event.all_objects.filter(pk__in=_ints(wanted["agenda:public_detail"])).values_list(
            "pk", "title"
        )
    )
    news = dict(
        NewsPost.objects.filter(slug__in=wanted["public:news_detail"]).values_list("slug", "title")
    )
    ideas = dict(
        Idea.objects.filter(pk__in=_ints(wanted["ideas:public_detail"])).values_list("pk", "title")
    )
    labels = {}
    for key in keys:
        view, _, ref = key.rpartition(":")
        if view == "agenda:public_detail":
            title = events.get(int(ref)) if ref.isdigit() else None
            labels[key] = f"Événement « {title} »" if title else "Événement supprimé"
        elif view == "public:news_detail":
            title = news.get(ref)
            labels[key] = f"Actualité « {title} »" if title else "Actualité supprimée"
        elif view == "ideas:public_detail":
            title = ideas.get(int(ref)) if ref.isdigit() else None
            labels[key] = f"Idée « {title} »" if title else "Idée"
        else:
            labels[key] = PAGE_LABELS.get(key, key)
    return labels


def _ints(values) -> list[int]:
    return [int(v) for v in values if v.isdigit()]
