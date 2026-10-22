import re

from django import forms
from django.utils import timezone

from apps.core.antispam import AntiSpamFormMixin
from apps.core.dates import combine
from apps.rooms.models import Room

from .models import Idea

SLOT_COUNT = 3
MAX_LINKS = 3


def _count_links(text: str) -> int:
    return len(re.findall(r"https?://|www\.", text, flags=re.IGNORECASE))


class IdeaFieldsMixin:
    def clean_description(self):
        description = self.cleaned_data["description"]
        if _count_links(description) > MAX_LINKS:
            raise forms.ValidationError(f"{MAX_LINKS} liens au plus dans la description.")
        return description


class ProposeForm(IdeaFieldsMixin, AntiSpamFormMixin):
    owner_name = forms.CharField(
        label="Votre nom",
        max_length=120,
        help_text="Il sera affiché avec l'événement.",
    )
    owner_email = forms.EmailField(
        label="Votre adresse e-mail",
        help_text="Seuls les organisateurs du collectif la verront, pour vous écrire si besoin.",
    )
    title = forms.CharField(label="Titre de l'événement", max_length=120)
    description = forms.CharField(
        label="Description",
        max_length=3000,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text="De quoi il s'agit, pour qui, comment ça se déroule.",
    )
    duration_minutes = forms.TypedChoiceField(
        label="Durée souhaitée",
        choices=Idea.Duration.choices,
        coerce=int,
        initial=Idea.Duration.TWO_HOURS,
    )
    wanted_room = forms.ModelChoiceField(
        label="Salle souhaitée",
        queryset=Room.objects.filter(is_active=True),
        required=False,
        empty_label="Pas de préférence",
    )
    audience = forms.CharField(
        label="Public visé",
        max_length=120,
        required=False,
        help_text="Par exemple : tout public, étudiants, personnels…",
    )
    expected_count = forms.IntegerField(
        label="Nombre de personnes attendues", min_value=1, max_value=10000, required=False
    )

    field_order = [
        "owner_name",
        "owner_email",
        "title",
        "description",
        "duration_minutes",
        *[
            f"slot{i}_{part}"
            for i in range(1, SLOT_COUNT + 1)
            for part in ("date", "time", "period")
        ],
        "wanted_room",
        "audience",
        "expected_count",
        "website",
        "rendered_at",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for i in range(1, SLOT_COUNT + 1):
            self.fields[f"slot{i}_date"] = forms.DateField(
                label="Date",
                required=False,
                widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            )
            self.fields[f"slot{i}_time"] = forms.TimeField(
                label="Heure de début",
                required=False,
                widget=forms.TimeInput(format="%H:%M", attrs={"type": "time", "step": 900}),
            )
            self.fields[f"slot{i}_period"] = forms.CharField(
                label="Ou une période plus large",
                max_length=200,
                required=False,
                widget=forms.TextInput(
                    attrs={"placeholder": "Une après-midi la semaine du 10 novembre"}
                ),
            )
        self.order_fields(self.field_order)

    def slot_groups(self):
        """Champs regroupés par créneau, pour le template."""
        return [
            {
                "number": i,
                "date": self[f"slot{i}_date"],
                "time": self[f"slot{i}_time"],
                "period": self[f"slot{i}_period"],
            }
            for i in range(1, SLOT_COUNT + 1)
        ]

    def clean(self):
        cleaned = super().clean()
        slots = []
        now = timezone.now()
        for i in range(1, SLOT_COUNT + 1):
            day = cleaned.get(f"slot{i}_date")
            hour = cleaned.get(f"slot{i}_time")
            period = (cleaned.get(f"slot{i}_period") or "").strip()
            if day and hour:
                start = combine(day, hour)
                if start <= now:
                    self.add_error(f"slot{i}_date", "Ce créneau est déjà passé.")
                    continue
                slots.append({"start": start})
            elif day or hour:
                # Une date sans heure (ou l'inverse) reste utile : on la garde comme période.
                if hour and not day:
                    self.add_error(f"slot{i}_date", "Indiquez aussi la date.")
                    continue
                text = f"Le {day:%d/%m/%Y}, horaire libre"
                slots.append({"period_text": f"{text} — {period}" if period else text})
            elif period:
                slots.append({"period_text": period})
        cleaned["slots"] = slots
        return cleaned


class TrackingForm(IdeaFieldsMixin, forms.ModelForm):
    class Meta:
        model = Idea
        fields = ["title", "description", "audience", "expected_count", "owner_email"]
        widgets = {"description": forms.Textarea(attrs={"rows": 6})}
        labels = {"owner_email": "Votre adresse e-mail"}


class RefuseForm(forms.Form):
    reason = forms.CharField(
        label="Motif (visible par la personne sur son lien de suivi)",
        max_length=300,
        required=False,
    )
