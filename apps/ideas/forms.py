import re

from django import forms
from django.utils import timezone

from apps.actors.forms import ActorNameFormMixin
from apps.core.antispam import AntiSpamFormMixin
from apps.core.dates import combine
from apps.rooms.models import Room
from apps.spaces.models import Space

from .models import AUDIENCE_SUGGESTIONS, Idea, Reaction

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


class SlotFieldsMixin:
    """Jusqu'à trois créneaux envisagés : date et heure précises, ou période libre (CDC §4)."""

    reject_past_slots = True

    def add_slot_fields(self):
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

    @staticmethod
    def slot_initial(idea) -> dict:
        initial = {}
        for i, slot in enumerate(idea.slots.all()[:SLOT_COUNT], start=1):
            if slot.is_precise:
                start = timezone.localtime(slot.start)
                initial[f"slot{i}_date"], initial[f"slot{i}_time"] = start.date(), start.time()
            else:
                initial[f"slot{i}_period"] = slot.period_text
        return initial

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

    def clean_slots(self, cleaned) -> list[dict]:
        slots = []
        now = timezone.now()
        for i in range(1, SLOT_COUNT + 1):
            day = cleaned.get(f"slot{i}_date")
            hour = cleaned.get(f"slot{i}_time")
            period = (cleaned.get(f"slot{i}_period") or "").strip()
            if day and hour:
                start = combine(day, hour)
                if self.reject_past_slots and start <= now:
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
        return slots


HIDE_NAME_LABEL = "Ne pas afficher mon nom sur la page publique"


class ProposeForm(IdeaFieldsMixin, SlotFieldsMixin, AntiSpamFormMixin):
    kind = forms.ChoiceField(
        label="Vous proposez",
        choices=[
            (Idea.Kind.EVENT, "Un événement (rencontre, atelier, projection…)"),
            (Idea.Kind.PROJECT, "Un projet"),
            (Idea.Kind.WISH, "Une envie, une idée à creuser"),
        ],
        initial=Idea.Kind.EVENT,
        required=False,  # faute de choix (formulaire ouvert avant l'ajout du type) : événement
        widget=forms.RadioSelect,
    )
    owner_name = forms.CharField(
        label="Votre nom",
        max_length=120,
        help_text="Il sera affiché avec votre proposition si elle est publiée.",
    )
    owner_email = forms.EmailField(
        label="Votre adresse e-mail",
        help_text="Seuls les organisateurs du collectif la verront, pour vous écrire si besoin.",
    )
    owner_hidden = forms.BooleanField(label=HIDE_NAME_LABEL, required=False)
    title = forms.CharField(label="Titre", max_length=120)
    description = forms.CharField(
        label="Description",
        max_length=3000,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text="De quoi il s'agit, pour qui, comment ça se déroulerait.",
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
        "kind",
        "owner_name",
        "owner_email",
        "owner_hidden",
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
        self.add_slot_fields()
        self.order_fields(self.field_order)

    def clean(self):
        cleaned = super().clean()
        cleaned["kind"] = cleaned.get("kind") or Idea.Kind.EVENT
        # Créneaux et salle ne valent que pour un événement (voir `services.submit`).
        is_event = cleaned.get("kind") == Idea.Kind.EVENT
        cleaned["slots"] = self.clean_slots(cleaned) if is_event else []
        return cleaned


class TrackingForm(IdeaFieldsMixin, forms.ModelForm):
    class Meta:
        model = Idea
        fields = [
            "title",
            "description",
            "audience",
            "expected_count",
            "owner_email",
            "owner_hidden",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 6})}
        labels = {"owner_email": "Votre adresse e-mail", "owner_hidden": HIDE_NAME_LABEL}


class RefuseForm(forms.Form):
    reason = forms.CharField(
        label="Motif (visible par la personne sur son lien de suivi)",
        max_length=300,
        required=False,
    )


# --- Idées des membres -------------------------------------------------------------------


class IdeaForm(ActorNameFormMixin, SlotFieldsMixin, forms.ModelForm):
    """Dépôt ou complément d'une idée : seuls le nom, le titre et le type sont obligatoires
    (CLAUDE.md IDE-1) ; le reste se replie dans « Plus de détails »."""

    class Meta:
        model = Idea
        fields = [
            "title",
            "kind",
            "description",
            "space",
            "format",
            "duration_minutes",
            "wanted_room",
            "audience",
            "expected_count",
            "speakers_text",
            "needs",
            "constraints",
        ]
        labels = {
            "title": "Titre",
            "kind": "Type",
            "description": "Description",
            "space": "Espace concerné",
            "format": "Format",
            "duration_minutes": "Durée souhaitée",
            "wanted_room": "Salle souhaitée",
            "audience": "Public visé",
            "expected_count": "Nombre de participants attendu",
            "speakers_text": "Organisateurs et intervenants pressentis",
            "needs": "Besoins",
            "constraints": "Contraintes",
        }
        help_texts = {
            "description": "De quoi il s'agit, objectifs, déroulé envisagé, liens utiles.",
            "speakers_text": "Des noms libres, séparés par des virgules.",
            "needs": "Matériel, capacité, budget éventuel…",
            "constraints": "Jours impossibles, date limite…",
        }
        widgets = {
            "kind": forms.RadioSelect,
            "description": forms.Textarea(attrs={"rows": 5}),
            "audience": forms.TextInput(attrs={"list": "publics-suggeres"}),
        }

    ESSENTIAL = ["title", "kind"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reject_past_slots = self.instance.pk is None
        space = self.instance.space if self.instance.pk else None
        spaces = Space.objects.filter(is_archived=False)
        if space is not None:
            # Une idée déjà rattachée à un espace archivé reste modifiable.
            spaces = spaces | Space.objects.filter(pk=space.pk)
        self.fields["space"].queryset = spaces
        self.fields["space"].empty_label = "Aucun"
        self.fields["wanted_room"].queryset = Room.objects.filter(is_active=True)
        self.fields["wanted_room"].empty_label = "Pas de préférence"
        self.fields["format"].choices = [("", "Non précisé"), *Idea.Format.choices]
        self.fields["kind"].choices = Idea.Kind.choices
        self.add_slot_fields()
        if self.instance.pk is None:
            # Choisi au dépôt par la personne elle-même : les autres participants qui
            # complètent l'idée ne le changent pas.
            self.fields["owner_hidden"] = forms.BooleanField(
                label="Si l'idée est publiée sur la page publique, ne pas y afficher mon nom",
                required=False,
            )
        if self.instance.pk and not self.is_bound:
            self.initial.update(self.slot_initial(self.instance))

    audience_suggestions = AUDIENCE_SUGGESTIONS

    def detail_fields(self):
        return [self[name] for name in self.Meta.fields if name not in self.ESSENTIAL]

    def clean(self):
        cleaned = super().clean()
        cleaned["slots"] = self.clean_slots(cleaned)
        return cleaned

    def service_kwargs(self) -> dict:
        data = self.cleaned_data
        kwargs = {name: data[name] for name in self.Meta.fields} | {"slots": data["slots"]}
        if "owner_hidden" in data:
            kwargs["owner_hidden"] = data["owner_hidden"]
        return kwargs


class IdeaFilterForm(forms.Form):
    """Filtres du tableau des idées (CDC §4) ; la sélection passe dans l'adresse."""

    STATUS_CURRENT = "en-cours"
    STATUS_ALL = "toutes"

    kind = forms.ChoiceField(label="Type", required=False)
    space = forms.ModelChoiceField(
        label="Espace", queryset=Space.objects.all(), required=False, empty_label="Tous"
    )
    audience = forms.ChoiceField(label="Public visé", required=False)
    status = forms.ChoiceField(label="Statut", required=False)

    def __init__(self, *args, audiences=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kind"].choices = [("", "Tous"), *Idea.Kind.choices]
        self.fields["audience"].choices = [("", "Tous"), *((a, a) for a in audiences)]
        visible = [(s, Idea.Status(s).label) for s in Idea.VISIBLE_STATUSES]
        self.fields["status"].choices = [
            (self.STATUS_CURRENT, "En cours"),
            *visible,
            (self.STATUS_ALL, "Toutes"),
        ]

    def filter(self, ideas):
        if not self.is_valid():
            return ideas.filter(status__in=CURRENT_STATUSES)
        data = self.cleaned_data
        if data["kind"]:
            ideas = ideas.filter(kind=data["kind"])
        if data["space"]:
            ideas = ideas.filter(space=data["space"])
        if data["audience"]:
            ideas = ideas.filter(audience=data["audience"])
        status = data["status"] or self.STATUS_CURRENT
        if status == self.STATUS_CURRENT:
            ideas = ideas.filter(status__in=CURRENT_STATUSES)
        elif status != self.STATUS_ALL:
            ideas = ideas.filter(status=status)
        return ideas


CURRENT_STATUSES = [Idea.Status.NEW, Idea.Status.PREPARING, Idea.Status.PLANNED]


class ReactionForm(ActorNameFormMixin, forms.Form):
    kind = forms.ChoiceField(choices=Reaction.Kind.choices)


class PublicReactionForm(ActorNameFormMixin, forms.Form):
    """Réagir depuis la page publique : le nom est demandé, il n'est pas affiché."""

    kind = forms.ChoiceField(choices=Reaction.Kind.choices)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[
            "author_name"
        ].help_text = (
            "Les organisateurs le voient ; la page publique n'affiche que le nombre de réactions."
        )


class PublishForm(forms.Form):
    is_public = forms.BooleanField(label="Afficher cette idée sur la page publique", required=False)
    owner_hidden = forms.BooleanField(
        label="Masquer le nom de la personne qui l'a proposée", required=False
    )


class StatusForm(ActorNameFormMixin, forms.Form):
    status = forms.ChoiceField(
        label="Statut",
        choices=[(s, Idea.Status(s).label) for s in Idea.MANUAL_STATUSES],
    )
