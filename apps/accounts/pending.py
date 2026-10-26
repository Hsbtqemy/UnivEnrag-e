"""Ce qui attend un gestionnaire, compté pour la page `/gestion/`.

`accounts` est en amont des apps qui détiennent les données (CLAUDE.md, sens des
dépendances) : chacune déclare ses compteurs au démarrage (`AppConfig.ready`), et la page
de gestion n'affiche que ceux des droits du compte.
"""

from collections.abc import Callable
from dataclasses import dataclass

from django.urls import reverse

from .capabilities import has_capability


@dataclass(frozen=True)
class Counter:
    key: str  # repère utilisé par le gabarit
    capabilities: tuple  # un seul de ces droits suffit
    label: Callable[[int], str]  # « 2 propositions à modérer »
    count: Callable[[], int]
    url_name: str  # la page où on la traite


_counters: dict[str, Counter] = {}


def register(key: str, capabilities, label, count, url_name: str) -> None:
    caps = (capabilities,) if isinstance(capabilities, str) else tuple(capabilities)
    _counters[key] = Counter(key, caps, label, count, url_name)


@dataclass(frozen=True)
class Waiting:
    label: str
    url: str

    def __str__(self) -> str:
        return self.label


def for_user(user) -> dict[str, Waiting]:
    """{repère: (libellé, lien)} des files non vides que ce compte peut traiter."""
    result = {}
    for counter in _counters.values():
        if not any(has_capability(user, cap) for cap in counter.capabilities):
            continue
        n = counter.count()
        if n:
            result[counter.key] = Waiting(counter.label(n), reverse(counter.url_name))
    return result


def plural(n: int, singular: str, plural_form: str) -> str:
    return f"{n} {singular if n == 1 else plural_form}"
