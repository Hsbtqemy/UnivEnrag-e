"""Anti-spam local pour les formulaires publics, sans captcha externe.

Deux pièges complémentaires : un champ invisible que seuls les robots remplissent, et
un horodatage signé qui révèle un formulaire envoyé trop vite pour avoir été lu.
"""

from django import forms
from django.conf import settings
from django.core import signing

SALT = "antispam.form-rendered-at"
MAX_AGE_SECONDS = 24 * 3600


class AntiSpamFormMixin(forms.Form):
    # Le nom « website » attire les robots ; le champ est masqué aux humains par CSS
    # et retiré de l'arbre d'accessibilité dans le template.
    website = forms.CharField(required=False, label="Site web (laisser vide)")
    rendered_at = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial["rendered_at"] = signing.TimestampSigner(salt=SALT).sign("form")

    def clean_rendered_at(self):
        # Un formulaire resté ouvert plus d'un jour n'est pas un spam : on le dit à la
        # personne plutôt que d'ignorer sa proposition en silence.
        token = self.cleaned_data.get("rendered_at", "")
        try:
            signing.TimestampSigner(salt=SALT).unsign(token, max_age=MAX_AGE_SECONDS)
        except signing.SignatureExpired:
            raise forms.ValidationError(
                "Le formulaire a expiré. Rechargez la page, puis renvoyez-le."
            ) from None
        except signing.BadSignature:
            pass  # signature fabriquée : traitée comme spam par is_spam()
        return token

    def is_spam(self) -> bool:
        """À appeler après `is_valid()`. Vrai si le formulaire doit être ignoré en silence."""
        if self.cleaned_data.get("website"):
            return True
        signer = signing.TimestampSigner(salt=SALT)
        try:
            signer.unsign(
                self.cleaned_data.get("rendered_at", ""),
                max_age=settings.PROPOSAL_MIN_FILL_SECONDS,
            )
        except signing.SignatureExpired:
            return False  # assez de temps passé : un humain a pu lire et remplir
        except signing.BadSignature:
            return True
        return True  # signature encore « fraîche » : envoyé trop vite
