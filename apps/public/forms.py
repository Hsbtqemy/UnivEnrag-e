from django import forms

from apps.actors.services import normalize_name
from apps.core.antispam import AntiSpamFormMixin


class ContactForm(AntiSpamFormMixin):
    name = forms.CharField(label="Votre nom", max_length=120)
    email = forms.EmailField(
        label="Votre adresse e-mail (facultatif)",
        required=False,
        help_text="Pour qu'on puisse vous répondre. Seuls les organisateurs la verront.",
    )
    message = forms.CharField(
        label="Votre message", max_length=4000, widget=forms.Textarea(attrs={"rows": 6})
    )

    def clean_name(self):
        name = self.cleaned_data["name"]
        if not normalize_name(name):
            raise forms.ValidationError("Indiquez votre nom.")
        return name


class PresentationForm(forms.Form):
    presentation = forms.CharField(
        label="Texte de présentation",
        required=False,
        widget=forms.Textarea(attrs={"rows": 14}),
        help_text=(
            "Mise en forme simple : **gras**, *italique*, listes (- …), liens "
            "[texte](https://…). Une ligne vide sépare les paragraphes."
        ),
    )
