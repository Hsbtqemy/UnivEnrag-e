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


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        if request.path.startswith("/gestion/") or request.path.startswith("/suivi/"):
            response.setdefault("X-Robots-Tag", "noindex, nofollow")
        return response
