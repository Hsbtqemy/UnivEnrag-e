from .capabilities import capabilities_of, is_manager


def management(request):
    """Droits du compte connecté, pour n'afficher que les liens de gestion utiles."""
    user = getattr(request, "user", None)
    if not is_manager(user):
        return {"capabilities": set(), "is_manager": False}
    return {"capabilities": capabilities_of(user), "is_manager": True}
