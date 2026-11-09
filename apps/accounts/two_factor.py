"""Double authentification des comptes de gestion (CLAUDE.md ACC-3).

TOTP (application d'authentification) avec 10 codes de secours à usage unique. Tant
qu'un compte n'a pas confirmé son appareil, puis tant que la session n'est pas vérifiée,
toute page de `/gestion/` redirige vers la configuration ou la vérification.
"""

import secrets

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

BACKUP_CODE_COUNT = 10


def confirmed_totp(user):
    return TOTPDevice.objects.filter(user=user, confirmed=True).first()


def pending_totp(user) -> TOTPDevice:
    """L'appareil en cours de configuration (créé au besoin, non confirmé)."""
    device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
    if device is None:
        device = TOTPDevice.objects.create(user=user, name="Application", confirmed=False)
    return device


def regenerate_backup_codes(user) -> list[str]:
    device, _ = StaticDevice.objects.get_or_create(user=user, name="Codes de secours")
    device.token_set.all().delete()
    codes = [f"{secrets.randbelow(10**8):08d}" for _ in range(BACKUP_CODE_COUNT)]
    for code in codes:
        StaticToken.objects.create(device=device, token=code)
    return codes


def verify_token(user, token: str):
    """Renvoie l'appareil qui accepte ce code (application ou code de secours), sinon None."""
    token = "".join(token.split())
    for device in TOTPDevice.objects.filter(user=user, confirmed=True):
        if device.verify_token(token):
            return device
    for device in StaticDevice.objects.filter(user=user, confirmed=True):
        if device.verify_token(token):
            return device
    return None


def safe_next(request, default: str) -> str:
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return default


# Pages de /gestion/ accessibles avant la vérification : connexion, déconnexion, 2FA.
EXEMPT_PREFIXES = ("/gestion/admin/login/", "/gestion/admin/logout/", "/gestion/2fa/")

# « Plus tard » choisi pendant cette session : la configuration sera reproposée à la
# prochaine connexion (une connexion ouvre une nouvelle session).
POSTPONED_KEY = "two_factor_postponed"


def is_optional(user) -> bool:
    """Un gestionnaire peut remettre la configuration à plus tard ; l'administrateur
    principal, non. Une fois l'appareil confirmé, le code est exigé à chaque connexion.

    DÉCISION du porteur du projet (09/11/2026), qui assouplit ACC-3 (CDC §2, §9) pour les
    gestionnaires : proposer la double authentification à chaque connexion sans l'imposer.
    """
    return not user.is_superuser and confirmed_totp(user) is None


class RequireTwoFactorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if settings.ADMIN_2FA_REQUIRED and user.is_authenticated and not user.is_verified():
            if is_optional(user):
                # Gestionnaire sans double authentification : on la propose une fois par
                # connexion, en arrivant dans la gestion ; la session garde ses droits.
                if (
                    request.path.startswith("/gestion/")
                    and not request.path.startswith(EXEMPT_PREFIXES)
                    and not request.session.get(POSTPONED_KEY)
                ):
                    url = reverse("accounts:2fa_setup")
                    return redirect(f"{url}?next={request.get_full_path()}")
            elif not request.path.startswith("/gestion/"):
                # Hors de /gestion/, une session qui doit saisir son code et ne l'a pas fait
                # n'a aucun droit (ACC-3) : elle navigue comme un participant.
                request.user = AnonymousUser()
            elif not request.path.startswith(EXEMPT_PREFIXES):
                name = "accounts:2fa_verify" if confirmed_totp(user) else "accounts:2fa_setup"
                return redirect(f"{reverse(name)}?next={request.get_full_path()}")
        return self.get_response(request)
