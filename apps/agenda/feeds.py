"""Abonnements iCal à l'agenda des membres (CDC §3, « Abonnement et partage »).

Une application d'agenda n'envoie pas de cookie : ces flux ne passent donc pas par le
code d'accès, mais par un jeton dans l'adresse (`SiteSettings.feeds_token`), révocable par
l'administrateur principal sans toucher au code d'accès.
"""

import secrets

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_safe

from apps.core.access import public_view
from apps.core.models import SiteSettings
from apps.rooms.models import Room
from apps.spaces.models import Space

from . import ical


def _check_token(token: str) -> SiteSettings:
    site = SiteSettings.get()
    if not secrets.compare_digest(token, site.feeds_token):
        raise Http404
    return site


def _ics(request, events, name: str) -> HttpResponse:
    body = ical.build_calendar(
        events,
        base_url=request.build_absolute_uri("/"),
        name=name,
        detail_path=lambda e: reverse("agenda:detail", args=[e.pk]),
    )
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="agenda.ics"'
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@require_safe
@public_view
def feed_all(request, token):
    site = _check_token(token)
    return _ics(request, ical.member_events(), site.collective_name)


@require_safe
@public_view
def feed_space(request, token, slug):
    site = _check_token(token)
    space = get_object_or_404(Space, slug=slug)
    return _ics(
        request, ical.member_events().filter(space=space), f"{site.collective_name} — {space}"
    )


@require_safe
@public_view
def feed_room(request, token, pk):
    site = _check_token(token)
    room = get_object_or_404(Room, pk=pk)
    return _ics(
        request,
        ical.member_events().filter(room=room),
        f"{site.collective_name} — {room.name}",
    )


@require_safe
def subscriptions(request):
    """Page « S'abonner » des membres : les adresses à coller dans son agenda."""
    token = SiteSettings.get().feeds_token

    def link(name, *args):
        url = request.build_absolute_uri(reverse(name, args=[token, *args]))
        return {"https": url, "webcal": "webcal://" + url.split("://", 1)[1]}

    feeds = [{"label": "Tout l'agenda", **link("agenda:feed_all")}]
    feeds += [
        {"label": f"Espace « {space} »", **link("agenda:feed_space", space.slug)}
        for space in Space.objects.open()
    ]
    feeds += [
        {"label": f"Salle « {room.name} »", **link("agenda:feed_room", room.pk)}
        for room in Room.objects.filter(is_active=True)
    ]
    return render(
        request,
        "agenda/subscriptions.html",
        {"feeds": feeds, "public_feed": request.build_absolute_uri(reverse("agenda:public_ics"))},
    )
