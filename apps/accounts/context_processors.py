from . import navigation
from .capabilities import can_edit_agenda, capabilities_of, is_manager


def management(request):
    """Droits du compte connecté, pour n'afficher que les liens de gestion utiles, et la
    barre de navigation qui en dépend."""
    user = getattr(request, "user", None)
    manager = is_manager(user)
    nav = navigation.build(
        request, has_access=getattr(request, "has_access", False), is_manager=manager
    )
    # Les membres modifient-ils l'agenda ? (décision 22) Utile à toutes les pages qui
    # proposent « Nouvel événement », « Réserver » ou « Fixer ce créneau ».
    editing = can_edit_agenda(user)
    if not manager:
        return {"capabilities": set(), "is_manager": False, "nav": nav, "can_edit_agenda": editing}
    return {
        "capabilities": capabilities_of(user),
        "is_manager": True,
        "nav": nav,
        "can_edit_agenda": editing,
    }
