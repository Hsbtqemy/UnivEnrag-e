"""Point d'entrée unique pour tracer une action d'un habilité : `audit.log(...)`."""

from .models import AuditLog


def log(user, action: str, obj=None, **details) -> AuditLog | None:
    """Trace l'action si son auteur est un compte de gestion ; ignore sinon.

    Les participants n'ont pas de compte : leurs actions vont dans l'historique des
    objets, pas dans ce journal.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    entry = AuditLog(user=user, action=action, details=_jsonable(details))
    if obj is not None:
        entry.object_type = obj._meta.label_lower
        entry.object_id = str(obj.pk)
        entry.object_repr = str(obj)[:200]
    entry.save()
    return entry


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)
