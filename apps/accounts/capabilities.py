"""Vérification des droits des gestionnaires, en un seul endroit (CLAUDE.md ACC-5)."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import CAPABILITIES

CAPABILITY_LABELS = dict(CAPABILITIES)


def is_manager(user) -> bool:
    """Administrateur principal ou gestionnaire actif."""
    return bool(user and user.is_authenticated and user.is_active and user.is_staff)


def has_capability(user, codename: str) -> bool:
    if codename not in CAPABILITY_LABELS:
        raise ValueError(f"Droit inconnu : {codename}")
    if not is_manager(user):
        return False
    return user.is_superuser or user.has_perm(f"accounts.{codename}")


def can_edit_agenda(user) -> bool:
    """Écrire dans l'agenda (créer, modifier, déplacer, annuler, placer une idée).

    Un habilité « agenda » le peut toujours ; un participant seulement si le réglage du site
    l'ouvre (CLAUDE.md AGE-3, décision 22). Le nom retenu reste exigé à part.
    """
    from apps.core.models import SiteSettings

    return has_capability(user, "manage_agenda") or SiteSettings.get().members_edit_agenda


def capabilities_of(user) -> set[str]:
    return {code for code in CAPABILITY_LABELS if has_capability(user, code)}


def require_capability(codename: str):
    """Réserve une vue aux habilités du domaine ; les autres reçoivent un 403."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not is_manager(request.user):
                return redirect_to_login(request.get_full_path())
            if not has_capability(request.user, codename):
                raise PermissionDenied(f"Droit « {CAPABILITY_LABELS[codename]} » nécessaire.")
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


def require_superuser(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_manager(request.user):
            return redirect_to_login(request.get_full_path())
        if not request.user.is_superuser:
            raise PermissionDenied("Réservé à l'administrateur principal.")
        return view(request, *args, **kwargs)

    return wrapped


class CapabilityAdminMixin:
    """Ouvre un écran de l'admin Django aux gestionnaires qui ont le droit du domaine."""

    capability: str = ""

    def _allowed(self, request) -> bool:
        return has_capability(request.user, self.capability)

    def has_module_permission(self, request):
        return self._allowed(request)

    def has_view_permission(self, request, obj=None):
        return self._allowed(request)

    def has_add_permission(self, request, *args):
        return self._allowed(request)

    def has_change_permission(self, request, obj=None):
        return self._allowed(request)


class SuperuserAdminMixin:
    """Écran de l'admin réservé à l'administrateur principal."""

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request, *args):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser
