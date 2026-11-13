"""Statistiques de visite anonymes (décision 28) : on compte, on ne suit personne.

Chaque page servie avec succès ajoute 1 à un compteur « page × jour ». Rien n'est gardé de
la personne : ni IP, ni cookie, ni identifiant, ni navigateur, ni heure. La conséquence
est assumée : pas de « visiteurs uniques », seulement des pages vues.

Ne comptent pas : les robots (repérés à leur navigateur, lu puis oublié), les comptes de
gestion, la gestion elle-même, les erreurs et redirections, les préchargements, les
rafraîchissements du grand écran (`?fragment=1`), les fichiers statiques.
"""

import re
from urllib.parse import urlsplit

from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import PageCount

Kind = PageCount.Kind

ROBOTS = re.compile(
    r"bot|crawl|spider|slurp|preview|monitor|uptime|curl|wget|python|httpx|http-client|"
    r"go-http|java/|okhttp|headless|lighthouse|facebookexternalhit|scan|fetch|feedparser",
    re.IGNORECASE,
)
FEED_TYPES = ("text/calendar", "application/rss+xml", "application/atom+xml")
# Fiches publiques : on garde l'objet (son numéro ou son adresse), pour afficher son titre.
DETAIL_ROUTES = {
    "agenda:public_detail": "pk",
    "public:news_detail": "slug",
    "ideas:public_detail": "pk",
}
BOARD_VIEW = "agenda:public_board"
NOT_COUNTED_PREFIXES = ("/gestion/", "/static/", "/sante/")


def entries_for(request, response) -> list[tuple[str, str]]:
    """Les compteurs que cette réponse incrémente : (catégorie, clé), ou rien."""
    match = request.resolver_match
    if request.method != "GET" or response.status_code != 200 or match is None:
        return []
    if request.path.startswith(NOT_COUNTED_PREFIXES) or request.GET.get("fragment"):
        return []
    agent = request.headers.get("User-Agent", "")
    if not agent or ROBOTS.search(agent):
        return []
    purpose = request.headers.get("Sec-Purpose", "") + request.headers.get("Purpose", "")
    if "prefetch" in purpose:
        return []
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return []  # les comptes de gestion ne gonflent pas les chiffres

    view = match.view_name
    content_type = response.get("Content-Type", "")
    if content_type.startswith(FEED_TYPES):
        return [(Kind.FEED, view)]
    if not content_type.startswith("text/html"):
        return []
    if view == BOARD_VIEW:
        return [(Kind.BOARD, view)]
    if not request.path.startswith("/p/"):
        return [(Kind.MEMBERS, view)]

    key = view
    if view in DETAIL_ROUTES:
        key = f"{view}:{match.kwargs.get(DETAIL_ROUTES[view], '')}"
    found = [(Kind.PUBLIC, key[:120])]
    source = _source(request)
    if source:
        found.append((Kind.SOURCE, source))
    return found


def _source(request) -> str:
    """Le domaine du site d'où vient la visite, s'il est extérieur ; jamais l'adresse."""
    host = urlsplit(request.headers.get("Referer", "")).hostname or ""
    host = host.lower().removeprefix("www.")
    own = request.get_host().split(":")[0].lower().removeprefix("www.")
    return host[:120] if host and host != own else ""


def record(entries) -> None:
    """Ajoute 1 à chaque compteur du jour. Une erreur de base ne casse jamais la page."""
    day = timezone.localdate()
    for kind, key in entries:
        try:
            _increment(day, kind, key)
        except DatabaseError:
            return


def _increment(day, kind, key) -> None:
    counters = PageCount.objects.filter(day=day, kind=kind, key=key)
    if counters.update(count=F("count") + 1):
        return
    try:
        with transaction.atomic():
            PageCount.objects.create(day=day, kind=kind, key=key, count=1)
    except IntegrityError:
        counters.update(count=F("count") + 1)  # une autre requête l'a créé entre-temps


class VisitCounterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        entries = entries_for(request, response)
        if entries:
            record(entries)
        return response
