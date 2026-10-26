import io
from base64 import b32encode

import segno
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.http import FileResponse, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django_otp import login as otp_login

from apps.audit import audit
from apps.core import backup, ratelimit

from . import pending, two_factor
from .capabilities import CAPABILITY_LABELS, capabilities_of, is_manager, require_superuser

HOME = "/gestion/"


class TokenForm(forms.Form):
    token = forms.CharField(
        label="Code à 6 chiffres (ou code de secours)",
        max_length=12,
        widget=forms.TextInput(
            attrs={"autocomplete": "one-time-code", "inputmode": "numeric", "autofocus": True}
        ),
    )


@login_required
def setup(request):
    """Première configuration : QR code à scanner, puis un code pour confirmer."""
    if two_factor.confirmed_totp(request.user):
        return redirect("accounts:2fa_verify")
    device = two_factor.pending_totp(request.user)
    form = TokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if device.verify_token("".join(form.cleaned_data["token"].split())):
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            otp_login(request, device)
            codes = two_factor.regenerate_backup_codes(request.user)
            audit.log(request.user, "accounts.two_factor_enabled", request.user)
            return render(
                request,
                "accounts/backup_codes.html",
                {"codes": codes, "next": two_factor.safe_next(request, HOME)},
            )
        form.add_error("token", "Code incorrect. Vérifiez l'heure du téléphone et réessayez.")
    return render(
        request,
        "accounts/two_factor_setup.html",
        {
            "form": form,
            "secret": b32encode(device.bin_key).decode(),
            "next": request.GET.get("next", ""),
        },
    )


@login_required
@never_cache
def setup_qr(request):
    """QR code de l'appareil en cours de configuration, produit ici en SVG (aucun service tiers)."""
    if two_factor.confirmed_totp(request.user):
        return HttpResponse(status=404)
    device = two_factor.pending_totp(request.user)
    buffer = io.BytesIO()
    segno.make(device.config_url, error="m").save(
        buffer, kind="svg", scale=5, dark="#111", light="#fff", xmldecl=False
    )
    return HttpResponse(buffer.getvalue(), content_type="image/svg+xml")


@login_required
def verify(request):
    """Vérification à chaque nouvelle session."""
    if not two_factor.confirmed_totp(request.user):
        return redirect("accounts:2fa_setup")
    form = TokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        # Seuls les échecs comptent : 5 par quart d'heure (CLAUDE.md, « Sécurité et RGPD »).
        if ratelimit.exceeded(request, "2fa", limit=5, window_seconds=15 * 60):
            return render(request, "429.html", status=429)
        device = two_factor.verify_token(request.user, form.cleaned_data["token"])
        if device is not None:
            otp_login(request, device)
            return redirect(two_factor.safe_next(request, HOME))
        ratelimit.record(request, "2fa")
        form.add_error("token", "Code incorrect.")
    return render(
        request,
        "accounts/two_factor_verify.html",
        {"form": form, "next": request.GET.get("next", "")},
    )


def gestion_home(request):
    """Point d'entrée de la gestion : seuls les outils permis au compte sont proposés."""
    if not is_manager(request.user):
        return redirect_to_login(request.get_full_path())
    labels = [
        label for code, label in CAPABILITY_LABELS.items() if code in capabilities_of(request.user)
    ]
    return render(
        request,
        "accounts/gestion_home.html",
        {"capability_labels": labels, "pending": pending.for_user(request.user)},
    )


@require_superuser
@never_cache
def backup_download(request):
    """« Sauvegarde complète » : réservée au superuser, car elle contient les empreintes
    des mots de passe (CLAUDE.md ACC-4, décision 16)."""
    if request.method == "POST":
        archive = backup.create()
        audit.log(request.user, "core.backup_downloaded", name=archive.name)
        return FileResponse(archive.open("rb"), as_attachment=True, filename=archive.name)
    archives = settings.BACKUP_DIR.glob(f"{backup.PREFIX}*{backup.SUFFIX}")
    recent = sorted(archives, reverse=True)[:10]
    return render(request, "accounts/backup.html", {"archives": recent})


@never_cache
def gestion_help(request):
    """Aide des gestionnaires et de l'administrateur principal."""
    if not is_manager(request.user):
        return redirect_to_login(request.get_full_path())
    return render(request, "accounts/help.html")
