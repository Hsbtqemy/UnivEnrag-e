"""Agenda des membres (CDC §3) : derrière le code d'accès, sous le nom de chacun."""

import json
from datetime import datetime, time, timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.capabilities import require_capability
from apps.actors.resolvers import remember_name
from apps.actors.services import get_or_create_for_name
from apps.core.dates import from_wall_clock
from apps.rooms.models import Room

from . import history, serializers, services
from .forms import ActionForm, EventForm
from .models import Event, EventChange


def _actor_for(name: str):
    return get_or_create_for_name(name)


def _done(response, form):
    """Retient le nom saisi pour la prochaine action (CLAUDE.md ACC-2)."""
    remember_name(response, form.cleaned_data["author_name"])
    return response


def _calendar_url(event_or_date) -> str:
    day = (
        timezone.localtime(event_or_date.start).date()
        if isinstance(event_or_date, Event)
        else event_or_date
    )
    return f"{reverse('agenda:calendar')}?date={day.isoformat()}"


# --- Agenda ------------------------------------------------------------------------------


@require_GET
def calendar(request):
    rooms = list(Room.objects.filter(is_active=True))
    config = {
        "eventsUrl": reverse("agenda:events_json"),
        "moveUrl": reverse("agenda:move", args=[0]),
        "newUrl": reverse("agenda:new"),
        "canEdit": bool(request.actor_name),
        "date": request.GET.get("date", ""),
    }
    return render(request, "agenda/calendar.html", {"calendar_config": config, "rooms": rooms})


@require_GET
def events_json(request):
    start, end = from_wall_clock(request.GET.get("start")), from_wall_clock(request.GET.get("end"))
    events = Event.objects.select_related("owner", "room")
    if start and end:
        events = events.overlapping(start, end)
    manager = services.can_manage(request.user)
    can_edit = bool(request.actor_name) or manager
    return JsonResponse(
        [
            serializers.member_event(e, editable=can_edit and (manager or not e.is_locked))
            for e in events
        ],
        safe=False,
    )


@require_GET
def check_slot(request):
    """Vérification en direct, avant l'enregistrement (CLAUDE.md AGE-7)."""
    start, end = from_wall_clock(request.GET.get("start")), from_wall_clock(request.GET.get("end"))
    room = Room.objects.filter(pk=request.GET.get("room") or None).first()
    exclude = request.GET.get("exclude") or None
    if not (start and end and room) or end <= start:
        return JsonResponse({"conflicts": [], "warnings": []})
    conflicts = services.room_conflicts(room, start, end, exclude_id=exclude)
    return JsonResponse(
        {
            "conflicts": [f"« {e.title} » ({services.describe_slot(e)})" for e in conflicts],
            "warnings": services.slot_warnings(room, start, end, exclude_id=exclude),
        }
    )


# --- Création, modification, annulation --------------------------------------------------


def _initial_for_new(request) -> dict:
    source = request.GET.get("depuis")
    if source:
        # Duplication : le formulaire arrive pré-rempli, il ne reste qu'à ajuster la date.
        event = get_object_or_404(Event, pk=source)
        initial = EventForm.initial_from_event(event)
        initial.pop("revision", None)
        initial["title"] = event.title
        return initial
    start = from_wall_clock(request.GET.get("debut", ""))
    if start is None:
        now = timezone.localtime() + timedelta(hours=1)
        start = timezone.make_aware(datetime.combine(now.date(), time(now.hour)))
    else:
        start = timezone.localtime(start)
        if start.hour == 0 and start.minute == 0 and not request.GET.get("fin"):
            start = start.replace(hour=10)  # clic sur un jour entier (vue mois)
    end = from_wall_clock(request.GET.get("fin", "")) or start + timedelta(hours=1)
    end = timezone.localtime(end)
    initial = {"day": start.date(), "start_time": start.time(), "end_time": end.time()}
    room = Room.objects.filter(pk=request.GET.get("salle") or None, is_active=True).first()
    if room:
        initial["room"] = room
    return initial


def new(request):
    can_publish = services.can_publish(request.user)
    form = EventForm(
        request.POST or None,
        initial=_initial_for_new(request) if request.method == "GET" else None,
        actor_name=request.actor_name,
        can_publish=can_publish,
    )
    if request.method == "POST" and form.is_valid():
        try:
            event = services.create(
                actor=_actor_for(form.cleaned_data["author_name"]),
                user=request.user,
                **form.service_kwargs(),
            )
        except services.EventError as error:
            form.add_error(None, str(error))
        else:
            if event.public_requested:
                messages.success(
                    request, f"« {event.title} » est créé. La publication est demandée."
                )
            else:
                messages.success(request, f"« {event.title} » est créé.")
            return _done(redirect(_calendar_url(event)), form)
    return render(
        request,
        "agenda/event_form.html",
        {"form": form, "event": None, "check_url": reverse("agenda:check")},
    )


def detail(request, pk):
    event = get_object_or_404(Event.objects.select_related("owner", "room"), pk=pk)
    changes = list(event.changes.select_related("actor", "user"))
    for change in changes:
        change.lines = history.describe(change)
    return render(
        request,
        "agenda/event_detail.html",
        {
            "event": event,
            "changes": changes,
            "cancel_form": ActionForm(
                initial={"revision": event.revision}, actor_name=request.actor_name
            ),
            "can_manage": services.can_manage(request.user),
            "can_publish": services.can_publish(request.user),
            "can_edit": event.status != Event.Status.CANCELLED
            and (not event.is_locked or services.can_manage(request.user)),
        },
    )


def edit(request, pk):
    event = get_object_or_404(Event.objects.select_related("room"), pk=pk)
    if event.status == Event.Status.CANCELLED:
        messages.error(request, "Un événement annulé ne se modifie plus.")
        return redirect("agenda:detail", pk=pk)
    if event.is_locked and not services.can_manage(request.user):
        messages.error(request, str(services.LockedError()))
        return redirect("agenda:detail", pk=pk)
    form = EventForm(
        request.POST or None,
        initial=EventForm.initial_from_event(event),
        actor_name=request.actor_name,
        can_publish=services.can_publish(request.user),
    )
    if request.method == "POST" and form.is_valid():
        try:
            services.update(
                event,
                actor=_actor_for(form.cleaned_data["author_name"]),
                user=request.user,
                revision=form.cleaned_data["revision"] or 0,
                **form.service_kwargs(),
            )
        except services.EventError as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, "Modifications enregistrées.")
            return _done(redirect("agenda:detail", pk=pk), form)
    return render(
        request,
        "agenda/event_form.html",
        {"form": form, "event": event, "check_url": reverse("agenda:check")},
    )


@require_POST
def cancel(request, pk):
    event = get_object_or_404(Event, pk=pk)
    form = ActionForm(request.POST, actor_name=request.actor_name)
    if not form.is_valid():
        messages.error(request, "Indiquez votre nom pour annuler l'événement.")
        return redirect("agenda:detail", pk=pk)
    try:
        services.cancel(
            event,
            actor=_actor_for(form.cleaned_data["author_name"]),
            user=request.user,
            revision=form.cleaned_data["revision"],
        )
    except services.EventError as error:
        messages.error(request, str(error))
        return redirect("agenda:detail", pk=pk)
    messages.success(request, "L'événement est annulé. Il reste visible, barré.")
    return _done(redirect("agenda:detail", pk=pk), form)


@require_POST
def move(request, pk):
    """Glisser-déposer dans l'agenda des membres."""
    event = get_object_or_404(Event, pk=pk)
    if not request.actor_name and not services.can_manage(request.user):
        return JsonResponse(
            {"ok": False, "error": "Indiquez d'abord votre nom pour modifier l'agenda."},
            status=400,
        )
    try:
        data = json.loads(request.body or b"{}")
        revision = int(data.get("revision"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Requête incomplète."}, status=400)
    start, end = from_wall_clock(data.get("start", "")), from_wall_clock(data.get("end", ""))
    actor = _actor_for(request.actor_name) if request.actor_name else None
    try:
        event = services.move(
            event,
            start=start,
            end=end,
            room=event.room,
            revision=revision,
            actor=actor,
            user=request.user,
        )
    except (services.StaleRevisionError, services.RoomConflictError, services.LockedError) as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=409)
    except services.EventError as error:
        return JsonResponse({"ok": False, "error": str(error)}, status=400)
    return JsonResponse({"ok": True, "warnings": services.warnings_for(event)})


# --- Actions réservées -------------------------------------------------------------------


@require_POST
@require_capability("manage_agenda")
def toggle_lock(request, pk):
    event = get_object_or_404(Event, pk=pk)
    event = services.set_locked(event, locked=not event.is_locked, user=request.user)
    messages.success(request, "Événement verrouillé." if event.is_locked else "Verrou retiré.")
    return redirect("agenda:detail", pk=pk)


@require_POST
@require_capability("manage_agenda")
def restore(request, pk, change_id):
    event = get_object_or_404(Event, pk=pk)
    change = get_object_or_404(EventChange, pk=change_id, event=event)
    try:
        services.restore(event, change, user=request.user)
    except services.EventError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Version restaurée. La restauration figure dans l'historique.")
    return redirect("agenda:detail", pk=pk)


@require_POST
@require_capability("manage_agenda")
def confirm(request, pk):
    event = get_object_or_404(Event, pk=pk)
    try:
        services.confirm(event, user=request.user)
    except services.EventError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Événement confirmé.")
    return redirect("agenda:detail", pk=pk)


@require_POST
def publish(request, pk):
    if not services.can_publish(request.user):
        raise PermissionDenied("Droit « Agenda » ou « Page publique » nécessaire.")
    event = get_object_or_404(Event, pk=pk)
    is_public = request.POST.get("public") == "1"
    services.set_public(event, is_public=is_public, user=request.user)
    if is_public and event.status != Event.Status.CONFIRMED:
        messages.info(request, "Publié : il apparaîtra sur l'agenda public une fois confirmé.")
    else:
        messages.success(
            request, "Publié sur l'agenda public." if is_public else "Retiré de l'agenda public."
        )
    target = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        target = reverse("agenda:detail", args=[pk])
    return redirect(target)


def public_requests(request):
    """File des demandes de publication (CLAUDE.md, décision 11)."""
    if not services.can_publish(request.user):
        raise PermissionDenied("Droit « Agenda » ou « Page publique » nécessaire.")
    events = (
        Event.objects.filter(public_requested=True, is_public=False)
        .exclude(status=Event.Status.CANCELLED)
        .select_related("owner", "room")
        .order_by("start")
    )
    return render(request, "gestion/public_requests.html", {"events": events})
