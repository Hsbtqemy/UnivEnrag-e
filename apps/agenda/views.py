import io
import json
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import groupby

import segno
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from apps.accounts.capabilities import is_manager, require_capability
from apps.actors.services import get_or_create_for_name
from apps.core.access import public_view
from apps.core.dates import from_wall_clock, to_wall_clock
from apps.core.models import SiteSettings
from apps.ideas import services as ideas_services
from apps.ideas.models import Idea, IdeaSlot
from apps.polls.models import Poll
from apps.presences import services as presences_services
from apps.rooms.models import Room
from apps.spaces.models import Space

from . import ical, serializers, services
from .models import Event

# --- Public ------------------------------------------------------------------------------


@require_safe
@public_view
def public_agenda(request):
    """Agenda public : le calendrier, puis la liste des prochains événements.

    À l'ouverture, la semaine en cours si elle a des rendez-vous publics, sinon le mois ;
    on change ensuite librement de vue.
    """
    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    events = list(ical.public_events().filter(end__gte=today))
    days = [
        (day, list(items))
        for day, items in groupby(events, key=lambda e: timezone.localtime(e.start).date())
    ]
    monday = today - timedelta(days=today.weekday())
    busy_week = ical.public_events().overlapping(monday, monday + timedelta(days=7)).exists()
    config = {
        "eventsUrl": reverse("agenda:public_events_json"),
        "initialView": "week" if busy_week else "month",
    }
    return render(request, "public/agenda.html", {"days": days, "calendar_config": config})


@require_safe
@public_view
def public_week(request):
    """Ancienne adresse de la vue semaine, peut-être déjà partagée : tout est sur une page."""
    return redirect("agenda:public_list", permanent=True)


@require_safe
@public_view
def public_detail(request, pk):
    event = get_object_or_404(ical.public_events(), pk=pk)
    return render(request, "public/event_detail.html", {"event": event})


@require_safe
@public_view
def public_events_json(request):
    events = ical.public_events()
    start, end = from_wall_clock(request.GET.get("start")), from_wall_clock(request.GET.get("end"))
    if start and end:
        events = events.overlapping(start, end)
    return JsonResponse([serializers.public_event(e) for e in events], safe=False)


BOARD_UPCOMING = 8
BOARD_THEMES = {"clair": "light", "sombre": "dark", "enrage": "enrage"}
# Les vues du grand écran, dans l'ordre de passage, et leur nom dans l'adresse (`?vues=`).
BOARD_VIEWS = {"jour": "Aujourd'hui", "semaine": "7 jours", "mois": "Le mois"}
# Durée d'affichage de chaque vue, en secondes (`?duree=`) : le temps de lire une journée
# chargée en passant ; un cycle complet dure une minute.
BOARD_DURATION = 20
BOARD_DURATION_RANGE = (8, 120)
BOARD_WEEK_PER_DAY = 6  # au-delà : « + 2 autres » ; le script resserre selon l'écran
BOARD_MONTH_PER_DAY = 4
BOARD_MONTH_WEEKS = 5


@dataclass
class BoardDay:
    day: date
    events: list
    more: int
    is_today: bool
    is_past: bool


def _board_days(events, first: date, count: int, cap: int, today: date) -> list[BoardDay]:
    """`count` jours à partir de `first`, chacun avec ses `cap` premiers événements."""
    by_day: dict[date, list] = {}
    for event in events:
        by_day.setdefault(timezone.localtime(event.start).date(), []).append(event)
    days = []
    for offset in range(count):
        day = first + timedelta(days=offset)
        items = by_day.get(day, [])
        days.append(BoardDay(day, items[:cap], max(0, len(items) - cap), day == today, day < today))
    return days


def _board_context() -> dict:
    """Ce que montre le grand écran, calculé à chaque appel : le jour change tout seul.

    Trois vues : aujourd'hui (rendez-vous en cours et à venir, permanences du jour, puis
    les prochains rendez-vous), les 7 prochains jours, et cinq semaines à partir du lundi.
    Rien d'autre que ce que montre déjà l'agenda public (PUB-1).
    """
    now = timezone.localtime()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    events = ical.public_events()
    today_events = list(events.overlapping(today, tomorrow))
    current = [event for event in today_events if event.end > now]
    upcoming = list(events.filter(start__gte=tomorrow)[:BOARD_UPCOMING])
    permanences = presences_services.public_permanences(days=1)

    week_events = events.filter(start__gte=today, start__lt=today + timedelta(days=7))
    week_days = _board_days(week_events, now.date(), 7, BOARD_WEEK_PER_DAY, now.date())

    monday = today - timedelta(days=today.weekday())
    month_count = BOARD_MONTH_WEEKS * 7
    month_events = events.filter(start__gte=monday, start__lt=monday + timedelta(days=month_count))
    month_days = _board_days(
        month_events, monday.date(), month_count, BOARD_MONTH_PER_DAY, now.date()
    )
    return {
        "now": now,
        "today_events": current,
        "finished_count": len(today_events) - len(current),
        "permanences": permanences[0].slots if permanences else [],
        "upcoming_days": [
            (day, list(items))
            for day, items in groupby(upcoming, key=lambda e: timezone.localtime(e.start).date())
        ],
        "week_days": week_days,
        "week_empty": not any(day.events for day in week_days),
        "month_weeks": [month_days[i : i + 7] for i in range(0, month_count, 7)],
        "month_empty": not any(day.events for day in month_days),
        "weekday_names": ["Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."],
    }


def _board_settings(request) -> tuple[list[str], int]:
    """Vues et durée demandées dans l'adresse, sinon les valeurs par défaut."""
    views = [v for v in request.GET.get("vues", "").split(",") if v in BOARD_VIEWS]
    raw = request.GET.get("duree", "")
    low, high = BOARD_DURATION_RANGE
    duration = min(max(int(raw), low), high) if raw.isdigit() else BOARD_DURATION
    return list(dict.fromkeys(views)) or list(BOARD_VIEWS), duration


@require_safe
@never_cache
@public_view
def public_board(request):
    """Agenda pour un grand écran (panneau d'affichage) : sans navigation, lisible de loin,
    sans compte ni code (il ne montre que le public).

    Le script fait tourner les vues (aujourd'hui, 7 jours, le mois) et redemande le contenu
    chaque minute (`?fragment=1`) : un événement ajouté apparaît, et le jour change à
    minuit sans intervention.
    """
    context = _board_context()
    if request.GET.get("fragment"):
        return render(request, "public/_board.html", context)
    views, duration = _board_settings(request)
    context["forced_theme"] = BOARD_THEMES.get(request.GET.get("theme", ""), "")
    context["config"] = {
        "fragmentUrl": f"{reverse('agenda:public_board')}?fragment=1",
        "timeZone": settings.TIME_ZONE,
        "views": views,
        "labels": BOARD_VIEWS,
        "duration": duration,
    }
    return render(request, "public/board.html", context)


@require_safe
@public_view
def public_board_qr(request):
    """QR code vers l'agenda public, produit ici en SVG (aucun service tiers)."""
    buffer = io.BytesIO()
    url = request.build_absolute_uri(reverse("agenda:public_list"))
    segno.make(url, error="m").save(
        buffer, kind="svg", scale=4, border=2, dark="#111", light="#fff", xmldecl=False
    )
    response = HttpResponse(buffer.getvalue(), content_type="image/svg+xml")
    response["Cache-Control"] = "public, max-age=86400"
    return response


@require_safe
@public_view
def public_ics(request):
    body = ical.public_calendar(
        ical.public_events(),
        base_url=request.build_absolute_uri("/"),
        name=SiteSettings.get().collective_name,
    )
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="agenda.ics"'
    return response


# --- Interne ------------------------------------------------------------------------------


@require_safe
def home(request):
    """Accueil des membres : prochains événements, provisoires compris (marqués comme tels)."""
    now = timezone.now()
    events = (
        Event.objects.active()
        .filter(end__gte=now, start__lte=now + timedelta(days=60))
        .select_related("owner", "room", "space")
        .order_by("start")[:20]
    )
    monday = presences_services.week_start(timezone.localdate())
    return render(
        request,
        "agenda/home.html",
        {
            "events": events,
            "open_polls": (
                Poll.objects.filter(is_closed=False).select_related("owner")[:5]
                if settings.POLLS_ENABLED
                else []
            ),
            "presence_count": presences_services.count_people(monday),
            "idea_count": Idea.objects.filter(
                status__in=[Idea.Status.NEW, Idea.Status.PREPARING, Idea.Status.PLANNED]
            ).count(),
            "to_place": Idea.objects.to_place().count(),
        },
    )


# --- Programmation (CDC §3) --------------------------------------------------------------
# Consultable par tous les participants. Placer et déplacer, sous son nom, seulement si le
# réglage du site l'ouvre (décision 22). Confirmer et publier restent réservés
# (CLAUDE.md AGE-3, décision 11).


@require_safe
def programming(request):
    rooms = list(Room.objects.filter(is_active=True))
    resources = [{"id": str(r.pk), "title": r.name} for r in rooms]
    resources.append({"id": serializers.FREE_PLACE_RESOURCE, "title": "Lieu libre"})
    can_confirm = services.can_manage(request.user)
    can_publish = services.can_publish(request.user)
    config = {
        "eventsUrl": reverse("agenda:programming_events"),
        "moveUrl": reverse("agenda:move", args=[0]),
        "placeUrl": reverse("agenda:place_idea", args=[0]),
        "confirmUrl": reverse("agenda:gestion_confirm") if can_confirm else "",
        "publicUrl": reverse("agenda:gestion_public", args=[0]) if can_publish else "",
        "canEdit": services.can_edit(request.user) and (bool(request.actor_name) or can_confirm),
        "resources": resources,
        "freePlaceResource": serializers.FREE_PLACE_RESOURCE,
    }
    ideas = Idea.objects.visible()
    return render(
        request,
        "agenda/programming.html",
        {
            "calendar_config": config,
            "unplaced": Idea.objects.to_place()
            .select_related("owner", "wanted_room")
            .prefetch_related("slots")
            .order_by("created_at"),
            "rooms": rooms,
            "spaces": Space.objects.open(),
            "kinds": Idea.Kind.choices,
            "audiences": sorted(set(ideas.exclude(audience="").values_list("audience", flat=True))),
            "can_confirm": can_confirm,
            "can_publish": can_publish,
        },
    )


@require_safe
def programming_events(request):
    start, end = from_wall_clock(request.GET.get("start")), from_wall_clock(request.GET.get("end"))
    # Les « à reprogrammer » y restent : c'est ici qu'on leur trouve une autre date.
    base = Event.objects.exclude(status=Event.Status.CANCELLED).select_related(
        "owner", "room", "space", "idea"
    )
    events = base.overlapping(start, end) if start and end else base
    events = list(events.prefetch_related("idea__slots"))
    # Un provisoire placé hors de la période peut y avoir un autre créneau envisagé :
    # on n'envoie alors que ce créneau en pointillé (IDE-2).
    elsewhere = []
    if start and end:
        slots_here = IdeaSlot.objects.filter(start__lt=end, end__gt=start).values("idea")
        elsewhere = list(
            base.filter(status=Event.Status.PROVISIONAL, idea__in=slots_here)
            .exclude(pk__in=[e.pk for e in events])
            .prefetch_related("idea__slots")
        )
    manager = services.can_manage(request.user)
    can_edit = services.can_edit(request.user) and (bool(request.actor_name) or manager)

    payload = [
        serializers.programming_event(
            event,
            services.warnings_for(event),
            editable=can_edit and (manager or not event.is_locked),
            show_email=is_manager(request.user),
        )
        for event in events
    ]
    for event in events + elsewhere:
        if event.status == Event.Status.PROVISIONAL and event.idea_id:
            for slot in event.idea.slots.all():
                is_current = slot.start == event.start and slot.end == event.end
                if slot.is_precise and not is_current:
                    payload.append(serializers.alternative_slot(event, slot))
    return JsonResponse(payload, safe=False)


def _json_body(request) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}


def _error(message: str, status: int = 400, **extra) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message, **extra}, status=status)


@require_POST
def place_idea(request, pk):
    """Une idée de « À placer » posée sur un créneau, en provisoire, sous le nom retenu."""
    idea = get_object_or_404(Idea.objects.visible(), pk=pk)
    if not services.can_edit(request.user):
        return _error("Les gestionnaires de l'agenda placent les idées.", status=403)
    if not request.actor_name and not services.can_manage(request.user):
        return _error("Indiquez d'abord votre nom pour placer une idée.")
    data = _json_body(request)
    start = from_wall_clock(data.get("start", ""))
    if not start:
        return _error("Choisissez un créneau.")
    end = from_wall_clock(data.get("end", "")) or start + timedelta(minutes=idea.duration_minutes)
    room = serializers.room_from_resource(data.get("room"))
    actor = get_or_create_for_name(request.actor_name) if request.actor_name else None
    try:
        event = ideas_services.place(
            idea, start=start, end=end, room=room, actor=actor, user=request.user
        )
    except (ideas_services.TransitionError, services.EventError) as error:
        return _error(str(error))
    return JsonResponse(
        {
            "ok": True,
            "eventId": event.pk,
            "start": to_wall_clock(event.start),
            "warnings": services.warnings_for(event),
        }
    )


@require_capability("manage_agenda")
@require_POST
def gestion_confirm(request):
    ids = _json_body(request).get("ids") or []
    events = list(Event.objects.filter(pk__in=[i for i in ids if str(i).isdigit()]))
    if not events:
        return _error("Aucun événement sélectionné.")
    report = services.confirm_many(events, user=request.user)
    return JsonResponse(
        {
            "ok": not report.refused,
            "confirmed": [e.pk for e in report.confirmed],
            "refused": [{"id": e.pk, "title": e.title, "error": msg} for e, msg in report.refused],
        }
    )


@require_POST
def gestion_public(request, pk):
    if not services.can_publish(request.user):
        return _error("Droit « Agenda » ou « Page publique » nécessaire.", status=403)
    event = get_object_or_404(Event, pk=pk)
    is_public = bool(_json_body(request).get("isPublic"))
    services.set_public(event, is_public=is_public, user=request.user)
    return JsonResponse({"ok": True, "isPublic": is_public})
