from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.actors.forms import ActorNameFormMixin
from apps.core.dates import combine
from apps.rooms.models import Room
from apps.spaces.models import Space


class RoomChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, room):
        return f"{room.name} (sur validation)" if room.needs_approval else room.name


class EventForm(ActorNameFormMixin, forms.Form):
    """Création ou modification d'un événement par un participant (CDC §3).

    Seuls le titre, le jour et les heures sont obligatoires ; le reste se replie dans
    « Plus de détails » pour tenir la promesse des 30 secondes.
    """

    title = forms.CharField(label="Titre", max_length=120)
    day = forms.DateField(
        label="Jour", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    )
    start_time = forms.TimeField(
        label="Début", widget=forms.TimeInput(format="%H:%M", attrs={"type": "time", "step": 300})
    )
    end_time = forms.TimeField(
        label="Fin", widget=forms.TimeInput(format="%H:%M", attrs={"type": "time", "step": 300})
    )
    space = forms.ModelChoiceField(
        label="Espace",
        queryset=Space.objects.open(),
        required=False,
        empty_label="Aucun",
    )
    room = RoomChoiceField(
        label="Salle du collectif",
        queryset=Room.objects.filter(is_active=True),
        required=False,
        empty_label="Aucune (lieu ci-dessous, ou à préciser)",
    )
    place_text = forms.CharField(
        label="Autre lieu",
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Amphi B, réservé via la scolarité"}),
    )
    description = forms.CharField(
        label="Description", required=False, widget=forms.Textarea(attrs={"rows": 4})
    )
    visio_link = forms.URLField(label="Lien visio", required=False, assume_scheme="https")
    wants_public = forms.BooleanField(required=False)
    override = forms.BooleanField(
        label="Déroger : réserver même si la salle est occupée ou fermée",
        required=False,
        help_text="Réservé aux gestionnaires des salles ; la dérogation est journalisée.",
    )
    revision = forms.IntegerField(widget=forms.HiddenInput, required=False)

    ESSENTIAL = ["title", "day", "start_time", "end_time"]
    DETAILS = ["space", "room", "place_text", "description", "visio_link", "wants_public"]

    def __init__(self, *args, can_publish=False, can_override=False, current_space=None, **kwargs):
        super().__init__(*args, **kwargs)
        if current_space is not None:
            # Un événement déjà rattaché à un espace archivé reste modifiable.
            self.fields["space"].queryset = Space.objects.filter(
                Q(is_archived=False) | Q(pk=current_space.pk)
            )
        if not can_override:
            del self.fields["override"]
        self.fields["wants_public"].label = (
            "Visible sur l'agenda public"
            if can_publish
            else "Demander la publication sur l'agenda public"
        )
        if not can_publish:
            self.fields["wants_public"].help_text = "Un gestionnaire validera la demande."

    def essential_fields(self):
        return [self[name] for name in self.ESSENTIAL]

    def detail_fields(self):
        return [self[name] for name in self.DETAILS]

    def clean(self):
        cleaned = super().clean()
        day, start, end = cleaned.get("day"), cleaned.get("start_time"), cleaned.get("end_time")
        if day and start and end:
            if end <= start:
                self.add_error("end_time", "La fin doit être après le début.")
            else:
                cleaned["start"], cleaned["end"] = combine(day, start), combine(day, end)
        return cleaned

    def service_kwargs(self) -> dict:
        data = self.cleaned_data
        return {
            "title": data["title"],
            "start": data["start"],
            "end": data["end"],
            "room": data["room"],
            "space": data["space"],
            "override": data.get("override", False),
            "place_text": data["place_text"],
            "description": data["description"],
            "visio_link": data["visio_link"],
            "wants_public": data["wants_public"],
        }

    @classmethod
    def initial_from_event(cls, event) -> dict:
        start, end = timezone.localtime(event.start), timezone.localtime(event.end)
        return {
            "title": event.title,
            "day": start.date(),
            "start_time": start.time().replace(second=0, microsecond=0),
            "end_time": end.time().replace(second=0, microsecond=0),
            "room": event.room,
            "space": event.space,
            "place_text": event.place_text,
            "description": event.description,
            "visio_link": event.visio_link,
            "wants_public": event.is_public or event.public_requested,
            "revision": event.revision,
        }


class ActionForm(ActorNameFormMixin, forms.Form):
    """Action simple sur un événement (annuler…) : le nom et la version vue."""

    revision = forms.IntegerField(widget=forms.HiddenInput)
