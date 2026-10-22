"""Code d'accès commun (CDC §2, CLAUDE.md ACC-1).

Fermé par défaut : une vue n'est accessible sans code que si elle porte `@public_view`.
Les pages de `/gestion/` relèvent, elles, de la connexion des comptes de gestion.
"""

from functools import wraps

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode

from .models import SiteSettings

COOKIE_NAME = "acces"
COOKIE_SALT = "core.access"
COOKIE_MAX_AGE = 400 * 24 * 3600


def public_view(view):
    """Marque une vue comme accessible sans code d'accès."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        return view(*args, **kwargs)

    wrapped.public_view = True
    return wrapped


def has_valid_cookie(request) -> bool:
    stamp = request.get_signed_cookie(COOKIE_NAME, default=None, salt=COOKIE_SALT)
    if not stamp:
        return False
    site = SiteSettings.get()
    return site.has_access_code and stamp == site.access_code_stamp


def grant(response) -> None:
    response.set_signed_cookie(
        COOKIE_NAME,
        SiteSettings.get().access_code_stamp,
        salt=COOKIE_SALT,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="Lax",
    )


def _is_manager(user) -> bool:
    return bool(user.is_authenticated and user.is_active and user.is_staff)


class AccessCodeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        request.is_public_view = getattr(view_func, "public_view", False)
        request.has_access = _is_manager(request.user) or has_valid_cookie(request)
        if request.is_public_view or request.path.startswith("/gestion/"):
            return None
        if request.has_access:
            return None
        return redirect(f"{reverse('core:access')}?{urlencode({'next': request.get_full_path()})}")
