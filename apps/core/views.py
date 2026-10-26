import hashlib

from django import forms
from django.conf import settings
from django.db import DatabaseError, connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from . import access, ratelimit
from .models import SiteSettings

INTERNAL_HOME = "/accueil/"
PUBLIC_HOME = "/p/"

# Échecs du code d'accès : 10 par tranche de 10 minutes et par IP. La limite est large
# car tout un bâtiment universitaire peut partager la même adresse.
ACCESS_FAILURES = (10, 10 * 60)


class AccessCodeForm(forms.Form):
    code = forms.CharField(
        label="Code d'accès du collectif",
        max_length=128,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "autofocus": True}),
    )


def _next_url(request) -> str:
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return INTERNAL_HOME


@access.public_view
def root(request):
    return redirect(INTERNAL_HOME if access.has_valid_cookie(request) else PUBLIC_HOME)


@access.public_view
def access_code(request):
    site = SiteSettings.get()
    form = AccessCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        limit, window = ACCESS_FAILURES
        if ratelimit.exceeded(request, "access_code", limit, window):
            return render(request, "429.html", status=429)
        if site.check_access_code(form.cleaned_data["code"]):
            response = redirect(_next_url(request))
            access.grant(response)
            return response
        ratelimit.record(request, "access_code")
        form.add_error(
            "code", "Ce code n'est pas le bon. Il a peut-être changé : demandez-le au collectif."
        )
    return render(
        request,
        "core/access.html",
        {"form": form, "next": request.GET.get("next", ""), "site": site},
    )


@require_safe
@access.public_view
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /$",
        "Allow: /p/",
        "Disallow: /p/suivi/",
        "Disallow: /",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


@require_safe
@never_cache
@access.public_view
def health(request):
    """Sonde du conteneur et du script de déploiement : la base répond-elle ?"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return HttpResponse("base indisponible\n", status=503, content_type="text/plain")
    return HttpResponse("ok\n", content_type="text/plain")


@require_safe
@access.public_view
def privacy(request):
    """Finalité, responsables, durées et droits (CLAUDE.md « Sécurité et RGPD »)."""
    return render(request, "public/privacy.html", {"site": SiteSettings.get()})


@require_safe
def help_page(request):
    """Aide des membres : derrière le code d'accès, comme le reste de l'espace interne."""
    return render(request, "core/help.html")


# --- Application installable (CLAUDE.md : « installable (manifest + service worker) ») ----

THEME_COLOR = "#2f5d8c"
BACKGROUND_COLOR = "#f7f7f5"
SW_LOGIC_VERSION = "1"  # à changer quand templates/core/sw.js change de comportement


@require_safe
@access.public_view
def manifest(request):
    name = SiteSettings.get().collective_name
    icon = static("icons/icone-512.png")
    response = JsonResponse(
        {
            "name": name,
            "short_name": name[:24],
            "lang": "fr",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": BACKGROUND_COLOR,
            "theme_color": THEME_COLOR,
            "icons": [
                {"src": static("icons/icone-192.png"), "sizes": "192x192", "type": "image/png"},
                {"src": icon, "sizes": "512x512", "type": "image/png"},
                {
                    "src": static("icons/icone-maskable-512.png"),
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                },
            ],
        }
    )
    response["Content-Type"] = "application/manifest+json"
    return response


@require_safe
@never_cache
@access.public_view
def service_worker(request):
    precache = [
        reverse("core:offline"),
        static("css/app.css"),
        static("icons/icone-192.png"),
        static("icons/favicon-32.png"),
    ]
    # Les noms versionnés changent à chaque mise à jour des fichiers : le cache aussi.
    version = hashlib.sha256("|".join([SW_LOGIC_VERSION, *precache]).encode()).hexdigest()[:12]
    return render(
        request,
        "core/sw.js",
        {
            "version": version,
            "offline_url": reverse("core:offline"),
            "static_prefix": settings.STATIC_URL
            if settings.STATIC_URL.startswith("/")
            else f"/{settings.STATIC_URL}",
            "precache": precache,
        },
        content_type="application/javascript; charset=utf-8",
    )


@require_safe
@access.public_view
def offline(request):
    return render(request, "core/offline.html", {"site": SiteSettings.get()})
