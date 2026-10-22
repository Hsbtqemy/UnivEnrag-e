from django import forms

from apps.actors.forms import ActorNameFormMixin
from apps.core.dates import combine
from apps.rooms.models import Room
from apps.spaces.models import Space

from .models import PollAnswer
from .services import MAX_SLOTS, MIN_SLOTS

SLOT_ROWS = 6


class PollForm(ActorNameFormMixin, forms.Form):
    title = forms.CharField(
        label="Objet", max_length=120, help_text="Par exemple : réunion du groupe de travail"
    )
    description = forms.CharField(
        label="Précisions", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    space = forms.ModelChoiceField(
        label="Espace", queryset=Space.objects.open(), required=False, empty_label="Aucun"
    )
    room = forms.ModelChoiceField(
        label="Salle envisagée",
        required=False,
        empty_label="Aucune",
        queryset=Room.objects.filter(is_active=True),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for i in range(1, SLOT_ROWS + 1):
            self.fields[f"slot{i}_day"] = forms.DateField(
                label="Jour",
                required=False,
                widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            )
            for part, label in (("start", "Début"), ("end", "Fin")):
                self.fields[f"slot{i}_{part}"] = forms.TimeField(
                    label=label,
                    required=False,
                    widget=forms.TimeInput(format="%H:%M", attrs={"type": "time", "step": 300}),
                )

    def slot_rows(self):
        return [
            {"number": i, "fields": [self[f"slot{i}_{p}"] for p in ("day", "start", "end")]}
            for i in range(1, SLOT_ROWS + 1)
        ]

    def clean(self):
        cleaned = super().clean()
        slots = []
        for i in range(1, SLOT_ROWS + 1):
            day, start, end = (cleaned.get(f"slot{i}_{p}") for p in ("day", "start", "end"))
            if not any((day, start, end)):
                continue
            if not all((day, start, end)):
                self.add_error(f"slot{i}_day", "Indiquez le jour, le début et la fin.")
                continue
            if end <= start:
                self.add_error(f"slot{i}_end", "La fin doit être après le début.")
                continue
            slots.append((combine(day, start), combine(day, end)))
        if len(slots) < MIN_SLOTS and not self.errors:
            raise forms.ValidationError(f"Proposez au moins {MIN_SLOTS} créneaux.")
        cleaned["slots"] = slots[:MAX_SLOTS]
        return cleaned


ANSWER_CHOICES = [
    (PollAnswer.Answer.YES, "Oui"),
    (PollAnswer.Answer.MAYBE, "Si besoin"),
    ("", "Non"),
]


class AnswerForm(ActorNameFormMixin, forms.Form):
    def __init__(self, *args, slots=(), current=None, **kwargs):
        super().__init__(*args, **kwargs)
        current = current or {}
        self.slots = list(slots)
        for slot in self.slots:
            self.fields[f"slot-{slot.pk}"] = forms.ChoiceField(
                choices=ANSWER_CHOICES,
                required=False,
                widget=forms.RadioSelect,
                initial=current.get(slot.pk, ""),
            )

    def slot_fields(self):
        return [(slot, self[f"slot-{slot.pk}"]) for slot in self.slots]

    def answers(self) -> dict:
        return {slot.pk: self.cleaned_data.get(f"slot-{slot.pk}", "") for slot in self.slots}
