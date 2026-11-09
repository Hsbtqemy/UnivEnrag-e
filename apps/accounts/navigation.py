"""La barre de navigation, décrite une seule fois : le gabarit l'affiche en onglets sur
ordinateur et en barre d'onglets en bas de l'écran sur téléphone (les liens `primary`,
les autres sous « Plus »).

Sous `/p/`, tout le monde a la navigation publique, membres compris : ils voient le site
comme le public, et « Espace membres » les ramène à l'interne."""

from dataclasses import dataclass, field

from django.urls import reverse

PUBLIC_PREFIX = "/p/"


@dataclass
class NavItem:
    label: str
    url_name: str
    icon: str
    # Vues (« app:nom ») ou apps entières (« app: ») où le lien est l'onglet en cours.
    matches: tuple = ()
    primary: bool = False
    cta: bool = False
    # Aussi dans l'en-tête sur téléphone, où la barre du bas n'a pas de place pour lui.
    header: bool = False
    short: str = ""
    badge: int = 0  # nombre à traiter, en pastille (onglet « Gestion »)
    url: str = field(init=False, default="")
    current: bool = field(init=False, default=False)


def _member_items(is_manager: bool) -> list[NavItem]:
    items = [
        NavItem("Accueil", "agenda:home", "home", primary=True),
        NavItem(
            "Agenda",
            "agenda:calendar",
            "calendar",
            matches=(
                "agenda:calendar",
                "agenda:detail",
                "agenda:new",
                "agenda:edit",
                "agenda:subscriptions",
                "agenda:programming",
                "agenda:export",
            ),
            primary=True,
        ),
        NavItem(
            "Idées",
            "ideas:list",
            "idea",
            matches=("ideas:list", "ideas:new", "ideas:detail", "ideas:edit"),
            primary=True,
        ),
        NavItem("Salles", "agenda:rooms", "door"),
        NavItem("Qui est là ?", "presences:board", "people", matches=("presences:",), primary=True),
        NavItem("Sondages", "polls:list", "poll", matches=("polls:",)),
        NavItem("Site public", "public:home", "globe"),
    ]
    if is_manager:
        items.append(NavItem("Gestion", GESTION, "sliders"))
    return items


def _public_items(*, has_access: bool, is_manager: bool) -> list[NavItem]:
    # Sur téléphone, la barre du bas sert ce qu'on vient consulter : l'agenda, puis les
    # nouvelles. « Le collectif » reste la page d'arrivée (le nom du site y ramène) et
    # passe sous « Plus » ; sur ordinateur, tout est en onglets, dans cet ordre.
    items = [
        NavItem("Le collectif", "public:home", "home"),
        NavItem(
            "Agenda",
            "agenda:public_list",
            "calendar",
            matches=("agenda:public_list", "agenda:public_detail"),
            primary=True,
        ),
        NavItem(
            "Actualités",
            "public:news_list",
            "news",
            matches=("public:news_list", "public:news_detail"),
            primary=True,
        ),
        NavItem(
            "Idées",
            "ideas:public_list",
            "idea",
            matches=("ideas:public_list", "ideas:public_detail"),
            primary=True,
        ),
        # « Nous écrire » est un onglet de la même page que « Proposer une idée » : un seul
        # lien pour les deux, les données restent séparées (idée modérée, message privé).
        NavItem(
            "Proposer ou écrire",
            "ideas:propose",
            "plus",
            matches=("ideas:propose", "ideas:sent", "public:contact"),
            primary=True,
            cta=True,
            short="Proposer",
        ),
    ]
    # Un membre passe par son accueil ; un visiteur, par la saisie du code d'accès.
    members_home = "agenda:home" if has_access else "core:access"
    if has_access or not is_manager:
        items.append(NavItem("Espace membres", members_home, "key", header=True, short="Membres"))
    if is_manager:
        items.append(NavItem("Gestion", GESTION, "sliders"))
    return items


GESTION = "accounts:gestion_home"


def build(request, *, has_access: bool, is_manager: bool, pending: int = 0) -> dict:
    match = getattr(request, "resolver_match", None)
    view_name = match.view_name if match else ""
    public = request.path.startswith(PUBLIC_PREFIX) or not has_access
    if public:
        items = _public_items(has_access=has_access, is_manager=is_manager)
    else:
        items = _member_items(is_manager)
    for item in items:
        item.url = reverse(item.url_name)
        item.short = item.short or item.label
        if item.url_name == GESTION:
            item.badge = pending
        names = item.matches or (item.url_name,)
        item.current = any(
            view_name.startswith(name) if name.endswith(":") else view_name == name
            for name in names
        )
    more = [item for item in items if not item.primary]
    return {
        "items": items,
        "more": more,
        "header": [item for item in items if item.header],
        "more_current": any(item.current for item in more),
        # Sur téléphone, « Gestion » est sous « Plus » : la pastille y remonte.
        "more_badge": sum(item.badge for item in more),
        "public": public,
    }
