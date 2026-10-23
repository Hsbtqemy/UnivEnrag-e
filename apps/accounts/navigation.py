"""La barre de navigation, décrite une seule fois : le gabarit l'affiche en onglets sur
ordinateur et en barre d'onglets en bas de l'écran sur téléphone (les liens `primary`,
les autres sous « Plus »)."""

from dataclasses import dataclass, field

from django.urls import reverse


@dataclass
class NavItem:
    label: str
    url_name: str
    icon: str
    # Vues (« app:nom ») ou apps entières (« app: ») où le lien est l'onglet en cours.
    matches: tuple = ()
    primary: bool = False
    cta: bool = False
    short: str = ""
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
        items.append(NavItem("Gestion", "accounts:gestion_home", "sliders"))
    return items


def _visitor_items(is_manager: bool) -> list[NavItem]:
    items = [
        NavItem("Le collectif", "public:home", "home", primary=True, short="Accueil"),
        NavItem(
            "Agenda",
            "agenda:public_list",
            "calendar",
            matches=("agenda:public_list", "agenda:public_detail"),
            primary=True,
        ),
        NavItem(
            "Idées",
            "ideas:public_list",
            "idea",
            matches=("ideas:public_list", "ideas:public_detail"),
            primary=True,
        ),
        NavItem(
            "Actualités",
            "public:news_list",
            "news",
            matches=("public:news_list", "public:news_detail"),
        ),
        NavItem("Contact", "public:contact", "mail"),
        NavItem(
            "Proposer une idée", "ideas:propose", "plus", primary=True, cta=True, short="Proposer"
        ),
    ]
    if is_manager:
        items.append(NavItem("Gestion", "accounts:gestion_home", "sliders"))
    else:
        items.append(NavItem("Espace membres", "core:access", "key"))
    return items


def build(request, *, has_access: bool, is_manager: bool) -> dict:
    match = getattr(request, "resolver_match", None)
    view_name = match.view_name if match else ""
    items = _member_items(is_manager) if has_access else _visitor_items(is_manager)
    for item in items:
        item.url = reverse(item.url_name)
        item.short = item.short or item.label
        names = item.matches or (item.url_name,)
        item.current = any(
            view_name.startswith(name) if name.endswith(":") else view_name == name
            for name in names
        )
    more = [item for item in items if not item.primary]
    return {
        "items": items,
        "more": more,
        "more_current": any(item.current for item in more),
    }
