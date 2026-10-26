from datetime import date, time, timedelta

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.actors.forms import NameForm
from apps.actors.resolvers import remember_name
from apps.actors.services import get_or_create_for_name

from . import services
from .models import Presence


def _week_nav(monday: date) -> dict:
    return {
        "monday": monday,
        "sunday": monday + timedelta(days=6),
        "previous": (monday - timedelta(days=7)).isoformat(),
        "next": (monday + timedelta(days=7)).isoformat(),
        "is_current": monday == services.week_start(timezone.localdate()),
    }


def board(request):
    """Qui est là cette semaine, et où."""
    monday = services.parse_week(request.GET.get("semaine"))
    return render(
        request,
        "presences/board.html",
        {
            "rows": services.board(monday),
            "days": services.week_days(monday),
            "people_count": services.count_people(monday),
            **_week_nav(monday),
        },
    )


def _time(value: str | None):
    try:
        return time.fromisoformat(value) if value else None
    except ValueError:
        return None


def _selections_from_post(post, monday: date) -> dict:
    selections = {}
    for day in services.week_days(monday):
        key = day.isoformat()
        place = post.get(f"lieu-{key}", "")
        for period in Presence.Period.values:
            if post.get(f"p-{key}-{period}"):
                selections[(day, period)] = services.Declared(
                    place,
                    _time(post.get(f"de-{key}-{period}")),
                    _time(post.get(f"a-{key}-{period}")),
                )
    return selections


def _open_days_from_post(post, monday: date) -> set[date]:
    return {day for day in services.week_days(monday) if post.get(f"ouvert-{day.isoformat()}")}


def my_week(request):
    """Je coche les demi-journées où je serai là, avec un lieu par jour, et je dis si c'est
    une permanence ouverte au public (décision 23)."""
    monday = services.parse_week(request.GET.get("semaine") or request.POST.get("semaine"))
    name_form = NameForm(request.POST or None, actor_name=request.actor_name)
    if request.method == "POST":
        selections = _selections_from_post(request.POST, monday)
        open_days = _open_days_from_post(request.POST, monday)
        if name_form.is_valid():
            actor = get_or_create_for_name(name_form.cleaned_data["author_name"])
            try:
                count = services.save_week(actor, monday, selections, open_days)
            except services.PresenceError as error:
                messages.error(request, str(error))
                return _render_week(request, monday, selections, open_days, name_form)
            messages.success(
                request,
                f"Votre semaine est enregistrée ({count} demi-journée{'s' if count > 1 else ''}).",
            )
            response = redirect(f"{reverse('presences:board')}?semaine={monday.isoformat()}")
            remember_name(response, name_form.cleaned_data["author_name"])
            return response
    else:
        if request.GET.get("reprendre"):
            selections = services.previous_week_selections(request.actor, monday)
            open_days = services.previous_open_days(request.actor, monday)
            if not selections:
                messages.info(request, "Rien de déclaré la semaine précédente.")
        else:
            selections = services.selections_for(request.actor, monday)
            open_days = services.open_days_for(request.actor, monday)
    return _render_week(request, monday, selections, open_days, name_form)


def _render_week(request, monday, selections, open_days, name_form):
    days = []
    for day in services.week_days(monday):
        mine = {period: d for (on, period), d in selections.items() if on == day}
        place = next((d.place for d in mine.values() if d.place), "")
        days.append(
            {
                "date": day,
                "key": day.isoformat(),
                "periods": [
                    {
                        "value": period.value,
                        "label": period.label,
                        "checked": period.value in mine,
                        "start": mine[period.value].start if period.value in mine else None,
                        "end": mine[period.value].end if period.value in mine else None,
                    }
                    for period in Presence.Period
                ],
                "place": place,
                "is_open": day in open_days,
            }
        )
    return render(
        request,
        "presences/my_week.html",
        {
            "days": days,
            "name_form": name_form,
            "places": services.known_places(),
            **_week_nav(monday),
        },
    )
