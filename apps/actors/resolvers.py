"""Qui agit ? Un seul point de résolution : `request.actor` (CLAUDE.md, modèle « acteur »).

Aujourd'hui, le participant est désigné par le nom mémorisé dans son navigateur (cookie
`pseudo`), et un compte de gestion par l'acteur qui lui est rattaché. Une identification
individuelle future n'aura qu'à fournir un autre résolveur (`settings.ACTOR_RESOLVER`),
sans toucher aux clés étrangères ni aux vues.
"""

from urllib.parse import quote, unquote

from django.conf import settings
from django.utils.functional import SimpleLazyObject
from django.utils.module_loading import import_string

from .models import Actor
from .services import clean_display_name, normalize_name

NAME_COOKIE = "pseudo"
NAME_COOKIE_MAX_AGE = 400 * 24 * 3600


def read_name(request) -> str:
    raw = request.COOKIES.get(NAME_COOKIE, "")
    return clean_display_name(unquote(raw))[:120] if raw else ""


def remember_name(response, name: str) -> None:
    """Mémorise le nom saisi : il sera pré-rempli à la prochaine action (CLAUDE.md ACC-2)."""
    response.set_cookie(
        NAME_COOKIE,
        quote(clean_display_name(name)),
        max_age=NAME_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="Lax",
    )


def forget_name(response) -> None:
    response.delete_cookie(NAME_COOKIE, samesite="Lax")


class NameCookieResolver:
    def resolve(self, request) -> Actor | None:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            actor = getattr(user, "actor", None)
            if actor is not None:
                return actor
        name = read_name(request)
        if not name:
            return None
        # Lecture seule : l'acteur n'est créé qu'à la première écriture, par les services.
        return Actor.objects.filter(name_key=normalize_name(name)).first()


def get_resolver():
    return import_string(
        getattr(settings, "ACTOR_RESOLVER", "apps.actors.resolvers.NameCookieResolver")
    )()


class ActorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.resolver = get_resolver()

    def __call__(self, request):
        request.actor_name = read_name(request)
        request.actor = SimpleLazyObject(lambda: self.resolver.resolve(request))
        return self.get_response(request)
