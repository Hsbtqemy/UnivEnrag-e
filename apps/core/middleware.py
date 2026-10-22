"""En-têtes de sécurité communs à toutes les réponses."""

# Aucune ressource externe (CLAUDE.md, « Contraintes dures ») : tout vient du site.
# `style-src 'unsafe-inline'` est nécessaire : @event-calendar positionne ses
# événements par attributs `style`. Les scripts, eux, restent strictement locaux.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
    ]
)

# Pages publiques qu'un moteur de recherche n'a pas à indexer pour autant.
NOINDEX_PUBLIC_PREFIXES = ("/p/suivi/", "/acces/")


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        # La partie interne n'est jamais indexée (CDC §2).
        is_public = getattr(request, "is_public_view", False)
        if not is_public or request.path.startswith(NOINDEX_PUBLIC_PREFIXES):
            response.setdefault("X-Robots-Tag", "noindex, nofollow")
        return response
