import json
from datetime import timedelta
from itertools import groupby

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

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


@require_GET
@public_view
def public_agenda(request):
    """Agenda public : la semaine en calendrier, puis la liste des prochains événements."""
    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    events = list(ical.public_events().filter(end__gte=today))
    days = [
        (day, list(items))
        for day, items in groupby(events, key=lambda e: timezone.localtime(e.start).date())
    ]
    config = {"eventsUrl": reverse("agenda:public_events_json")}
    return render(request, "public/agenda.html", {"days": days, "calendar_config": config})


@require_GET
@public_view
def public_week(request):
    """Ancienne adresse de la vue semaine, peut-être déjà partagée : tout est sur une page."""
    return redirect("agenda:public_list", permanent=True)


@require_GET
@public_view
def public_detail(request, pk):
    event = get_object_or_404(ical.public_events(), pk=pk)
    return render(request, "public/event_detail.html", {"event": event})


@require_GET
@public_view
def public_events_json(request):
    events = ical.public_events()
    start, end = from_wall_clock(request.GET.get("start")), from_wall_clock(request.GET.get("end"))
    if start and end:
        events = events.overlapping(start, end)
    return JsonResponse([serializers.public_event(e) for e in events], safe=False)


@require_GET
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


@require_GET
def home(request):
    """Accueil des membres : prochains événements, provisoires compris (marqués comme tels)."""
    now = timezone.now()
    events = (
        Event.objects.active()
        .filter(end__gte=now, start__lte=now + timedelta(days=60))
        .select_related("owner", "room")
        .order_by("start")[:20]
    )
    monday = presences_services.week_start(timezone.localdate())
    return render(
        request,
        "agenda/home.html",
        {
            "events": events,
            "open_polls": Poll.objects.filter(is_closed=False).select_related("owner")[:5],
            "presence_count": presences_services.count_people(monday),
            "idea_count": Idea.objects.filter(
                status__in=[Idea.Status.NEW, Idea.Status.PREPARING, Idea.Status.PLANNED]
            ).count(),
            "to_place": Idea.objects.to_place().count(),
        },
    )


# --- Programmation (CDC §3) --------------------------------------------------------------
# Ouverte à tous les participants : chacun place et déplace, sous son nom. Confirmer et
# publier restent réservés (CLAUDE.md AGE-3, décision 11).


@require_GET
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
        "canEdit": bool(request.actor_name) or can_confirm,
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


@require_GET
def programming_events(request):
    start, end = from_wall_clock(request.GET.get("start")), from_wall_clock(request.GET.get("end"))
    base = Event.objects.active().select_related("owner", "room", "space", "idea")
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
    can_edit = bool(request.actor_name) or manager

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
