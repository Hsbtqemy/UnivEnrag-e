"""Texte mis en forme (présentation, actualités) : Markdown, puis HTML assaini.

C'est le SEUL endroit où du HTML est marqué sûr (CLAUDE.md : `|safe` est interdit, sauf
sur la sortie de `render()`). Balises permises : p, br, strong, em, ul, ol, li, a ; les
liens reçoivent `rel="nofollow noopener"`. Tout le reste (script, style, image, iframe,
attributs d'événement…) est retiré par nh3.
"""

import markdown as markdown_lib
import nh3
from django.utils.safestring import SafeString, mark_safe

ALLOWED_TAGS = {"p", "br", "strong", "em", "ul", "ol", "li", "a"}
ALLOWED_ATTRIBUTES = {"a": {"href", "title"}}
URL_SCHEMES = {"http", "https", "mailto"}


def render(text: str) -> SafeString:
    html = markdown_lib.markdown(text or "", extensions=["nl2br", "sane_lists"])
    clean = nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=URL_SCHEMES,
        link_rel="nofollow noopener",
    )
    return mark_safe(clean)  # noqa: S308 — assaini par nh3 juste au-dessus
