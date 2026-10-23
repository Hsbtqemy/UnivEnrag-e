from . import navigation
from .capabilities import capabilities_of, is_manager


def management(request):
    """Droits du compte connecté, pour n'afficher que les liens de gestion utiles, et la
    barre de navigation qui en dépend."""
    user = getattr(request, "user", None)
    manager = is_manager(user)
    nav = navigation.build(
        request, has_access=getattr(request, "has_access", False), is_manager=manager
    )
    if not manager:
        return {"capabilities": set(), "is_manager": False, "nav": nav}
    return {"capabilities": capabilities_of(user), "is_manager": True, "nav": nav}
