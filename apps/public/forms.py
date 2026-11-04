from django import forms
from django.utils import timezone

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


class NewsForm(forms.Form):
    """Rédiger une actualité : le titre et le texte suffisent."""

    title = forms.CharField(label="Titre", max_length=150)
    summary = forms.CharField(
        label="Chapô",
        max_length=300,
        required=False,
        help_text="Une ou deux phrases, montrées dans la liste et dans le flux RSS.",
    )
    body = forms.CharField(
        label="Texte",
        widget=forms.Textarea(attrs={"rows": 14}),
        help_text=PresentationForm.base_fields["presentation"].help_text,
    )
    published_at = forms.DateTimeField(
        label="Date de publication",
        required=False,
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
        help_text="Vide : maintenant. Une date future attend son jour pour paraître.",
    )
    is_published = forms.BooleanField(label="Publier sur la page publique", required=False)

    @classmethod
    def initial_from(cls, post) -> dict:
        return {
            "title": post.title,
            "summary": post.summary,
            "body": post.body,
            "published_at": timezone.localtime(post.published_at),
            "is_published": post.is_published,
        }
