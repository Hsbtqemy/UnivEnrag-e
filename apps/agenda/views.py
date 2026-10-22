import json
from datetime import timedelta
from itertools import groupby

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.capabilities import require_capability
from apps.core.access import public_view
from apps.core.dates import from_wall_clock, to_wall_clock
from apps.ideas import services as ideas_services
from apps.ideas.models import Idea
from apps.rooms.models import Room

from . import ical, serializers, services
from .models import Event

# --- Public ------------------------------------------------------------------------------


@require_GET
@public_view
def public_list(request):
    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    events = list(ical.public_events().filter(end__gte=today))
    days = [
        (day, list(items))
        for day, items in groupby(events, key=lambda e: timezone.localtime(e.start).date())
    ]
    return render(request, "public/agenda_list.html", {"days": days})


@require_GET
@public_view
def public_week(request):
    config = {
        "eventsUrl": reverse("agenda:public_events_json"),
        "listUrl": reverse("agenda:public_list"),
    }
    return render(request, "public/agenda_week.html", {"calendar_config": config})


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
        name="Agenda du collectif",
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
    return render(request, "agenda/home.html", {"events": events})


# --- Gestion -----------------------------------------------------------------------------


def _unplaced_ideas():
    return (
        Idea.objects.filter(status=Idea.Status.ACCEPTED, event__isnull=True)
        .select_related("owner", "wanted_room")
        .prefetch_related("slots")
        .order_by("created_at")
    )


@require_capability("manage_agenda")
@require_GET
def programming(request):
    rooms = list(Room.objects.filter(is_active=True))
    resources = [{"id": str(r.pk), "title": r.name} for r in rooms]
    resources.append({"id": serializers.FREE_PLACE_RESOURCE, "title": "Lieu libre"})
    config = {
        "eventsUrl": reverse("agenda:gestion_events"),
        "moveUrl": reverse("agenda:gestion_move", args=[0]),
        "confirmUrl": reverse("agenda:gestion_confirm"),
        "publicUrl": reverse("agenda:gestion_public", args=[0]),
        "placeUrl": reverse("agenda:gestion_place", args=[0]),
        "resources": resources,
        "freePlaceResource": serializers.FREE_PLACE_RESOURCE,
    }
    return render(
        request,
        "gestion/programming.html",
        {"calendar_config": config, "unplaced": _unplaced_ideas(), "rooms": rooms},
    )


@require_capability("manage_agenda")
@require_GET
def gestion_events(request):
    start, end = from_wall_clock(request.GET.get("start")), from_wall_clock(request.GET.get("end"))
    events = Event.objects.active().select_related("owner", "room", "idea")
    if start and end:
        events = events.overlapping(start, end)
    events = list(events.prefetch_related("idea__slots"))

    payload = []
    for event in events:
        payload.append(serializers.gestion_event(event, services.warnings_for(event)))
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


def _room_from(value):
    """`lieu-libre` ou vide → pas de salle ; sinon l'identifiant d'une salle existante."""
    if value in (None, "", serializers.FREE_PLACE_RESOURCE):
        return None
    try:
        return Room.objects.get(pk=int(value))
    except (Room.DoesNotExist, TypeError, ValueError):
        raise Http404("Salle inconnue.") from None


def _error(message: str, status: int = 400, **extra) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message, **extra}, status=status)


@require_capability("manage_agenda")
@require_POST
def gestion_move(request, pk):
    event = get_object_or_404(Event, pk=pk)
    data = _json_body(request)
    start, end = from_wall_clock(data.get("start", "")), from_wall_clock(data.get("end", ""))
    if not start or not end:
        return _error("Début et fin sont obligatoires.")
    room = _room_from(data["room"]) if "room" in data else event.room
    try:
        revision = int(data.get("revision"))
    except (TypeError, ValueError):
        return _error("Version de l'événement manquante.")
    try:
        event = services.move(
            event, start=start, end=end, room=room, revision=revision, user=request.user
        )
    except services.StaleRevisionError as error:
        return _error(str(error), status=409)
    except services.RoomConflictError as error:
        return _error(str(error), status=409)
    except services.EventError as error:
        return _error(str(error))
    return JsonResponse({"ok": True, "warnings": services.warnings_for(event)})


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


@require_capability("manage_agenda")
@require_POST
def gestion_public(request, pk):
    event = get_object_or_404(Event, pk=pk)
    is_public = bool(_json_body(request).get("isPublic"))
    services.set_public(event, is_public=is_public, user=request.user)
    return JsonResponse({"ok": True, "isPublic": is_public})


@require_capability("manage_agenda")
@require_POST
def gestion_place(request, pk):
    idea = get_object_or_404(Idea, pk=pk)
    data = _json_body(request)
    start = from_wall_clock(data.get("start", ""))
    if not start:
        return _error("Choisissez un créneau.")
    end = from_wall_clock(data.get("end", "")) or start + timedelta(minutes=idea.duration_minutes)
    room = _room_from(data.get("room"))
    try:
        event = ideas_services.place(idea, start=start, end=end, room=room, user=request.user)
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
