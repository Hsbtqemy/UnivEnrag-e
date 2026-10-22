from django.conf import settings

from .models import SiteSettings


def site(request):
    return {
        "site": SiteSettings.get(),
        "has_access": getattr(request, "has_access", False),
        # En développement, les fichiers statiques gardent des noms fixes : le service
        # worker les figerait en cache. Il n'est donc enregistré qu'en production.
        "pwa_enabled": not settings.DEBUG,
    }
