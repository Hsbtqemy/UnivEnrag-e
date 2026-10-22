from django import forms

from .services import normalize_name

AUTHOR_FIELD = "author_name"


class ActorNameFormMixin:
    """Ajoute le champ « Votre nom ou pseudo », pré-rempli depuis le navigateur.

    La vue passe `actor_name=request.actor_name` ; après une action réussie, elle appelle
    `remember_name(response, form.cleaned_data["author_name"])`.
    """

    def __init__(self, *args, actor_name: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[AUTHOR_FIELD] = forms.CharField(
            label="Votre nom ou pseudo",
            max_length=120,
            help_text="Il sera affiché avec votre contribution et retenu par ce navigateur.",
        )
        if actor_name and not self.is_bound:
            self.initial[AUTHOR_FIELD] = actor_name

    def clean_author_name(self):
        name = self.cleaned_data[AUTHOR_FIELD]
        if not normalize_name(name):
            raise forms.ValidationError("Indiquez un nom ou un pseudo.")
        return name


class NameForm(ActorNameFormMixin, forms.Form):
    pass
