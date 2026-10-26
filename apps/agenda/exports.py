"""Exporter ou imprimer l'agenda (CDC §7, « Exports » : agenda, espace, salle en iCal et CSV).

Les membres choisissent une période et des filtres ; le public n'exporte que les
événements publics (PUB-1). L'e-mail du porteur ne figure dans AUCUN export (PUB-2).
"""

import csv
from datetime import datetime, time, timedelta
from itertools import groupby

from django import forms
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_safe

from apps.core.access import public_view
from apps.core.models import SiteSettings
from apps.rooms.models import Room
from apps.spaces.models import Space

from . import ical
from .models import Event

MAX_DAYS = 366
FORMATS = {"imprimer", "csv", "ics"}


class ExportForm(forms.Form):
    du = forms.DateField(
        label="Du", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    )
    au = forms.DateField(
        label="Au", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    )
    salle = forms.ModelChoiceField(
        label="Salle",
        queryset=Room.objects.filter(is_active=True),
        required=False,
        empty_label="Toutes",
    )
    espace = forms.ModelChoiceField(
        label="Espace", queryset=Space.objects.all(), required=False, empty_label="Tous"
    )
    provisoires = forms.BooleanField(label="Inclure les événements provisoires", required=False)
    annules = forms.BooleanField(label="Inclure les événements annulés", required=False)

    @staticmethod
    def defaults() -> dict:
        today = timezone.localdate()
        return {"du": today, "au": today + timedelta(days=30), "provisoires": True}

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("du"), cleaned.get("au")
        if start and end:
            if end < start:
                self.add_error("au", "La fin de la période doit suivre son début.")
            elif (end - start).days > MAX_DAYS:
                self.add_error("au", "Un an au plus.")
        return cleaned

    def events(self):
        data = self.cleaned_data
        start = timezone.make_aware(datetime.combine(data["du"], time.min))
        end = timezone.make_aware(datetime.combine(data["au"] + timedelta(days=1), time.min))
        events = Event.objects.overlapping(start, end).select_related("owner", "room", "space")
        if data["salle"]:
            events = events.filter(room=data["salle"])
        if data["espace"]:
            events = events.filter(space=data["espace"])
        if not data["provisoires"]:
            events = events.exclude(status=Event.Status.PROVISIONAL)
        if not data["annules"]:
            events = events.exclude(status=Event.Status.CANCELLED)
        return events.order_by("start")

    def summary(self) -> str:
        data = self.cleaned_data
        parts = [f"du {data['du']:%d/%m/%Y} au {data['au']:%d/%m/%Y}"]
        if data["salle"]:
            parts.append(f"salle « {data['salle'].name} »")
        if data["espace"]:
            parts.append(f"espace « {data['espace'].name} »")
        return ", ".join(parts)


def _by_day(events):
    return [
        (day, list(items))
        for day, items in groupby(events, key=lambda e: timezone.localtime(e.start).date())
    ]


def _csv(events, filename: str) -> HttpResponse:
    """UTF-8 avec BOM et « ; » : s'ouvre tel quel dans un tableur français (CLAUDE.md)."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(
        [
            "Date",
            "Début",
            "Fin",
            "Titre",
            "Statut",
            "Lieu",
            "Espace",
            "Porté par",
            "Intervenants",
            "Public",
            "Description",
        ]
    )
    for event in events:
        start, end = timezone.localtime(event.start), timezone.localtime(event.end)
        writer.writerow(
            [
                f"{start:%d/%m/%Y}",
                f"{start:%H:%M}",
                f"{end:%H:%M}",
                event.title,
                event.get_status_display(),
                event.place_label,
                event.space.name if event.space_id else "",
                event.owner.display_name,
                event.speakers,
                "oui" if event.is_public else "non",
                event.description,
            ]
        )
    return response


def _ics_download(request, events, *, filename: str, name: str, public: bool) -> HttpResponse:
    if public:
        body = ical.public_calendar(events, base_url=request.build_absolute_uri("/"), name=name)
    else:
        body = ical.build_calendar(
            events,
            base_url=request.build_absolute_uri("/"),
            name=name,
            detail_path=lambda e: reverse("agenda:detail", args=[e.pk]),
        )
    response = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@require_safe
def export(request):
    """Agenda des membres : choisir une période, puis imprimer ou télécharger."""
    form = ExportForm(request.GET or None, initial=ExportForm.defaults())
    fmt = request.GET.get("format")
    if fmt in FORMATS and form.is_valid():
        events = form.events()
        data = form.cleaned_data
        stem = f"agenda-{data['du']:%Y%m%d}-{data['au']:%Y%m%d}"
        site = SiteSettings.get()
        if fmt == "csv":
            return _csv(events, f"{stem}.csv")
        if fmt == "ics":
            return _ics_download(
                request, events, filename=f"{stem}.ics", name=site.collective_name, public=False
            )
        return render(
            request,
            "agenda/print.html",
            {"days": _by_day(events), "summary": form.summary(), "internal": True},
        )
    return render(request, "agenda/export.html", {"form": form})


@require_safe
@public_view
def public_print(request):
    """Agenda public imprimable : les événements publics à venir."""
    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    events = ical.public_events().filter(end__gte=today)
    return render(
        request,
        "agenda/print.html",
        {"days": _by_day(events), "summary": "événements à venir", "internal": False},
    )


@require_safe
@public_view
def public_download(request):
    """Les événements publics à venir, en fichier .ics à importer (et non en abonnement)."""
    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    events = ical.public_events().filter(end__gte=today)
    site = SiteSettings.get()
    return _ics_download(
        request,
        events,
        filename=f"agenda-{timezone.localdate():%Y%m%d}.ics",
        name=site.collective_name,
        public=True,
    )
