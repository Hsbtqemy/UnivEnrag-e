from django import template

from apps.core.markdown import render

register = template.Library()


@register.filter(name="markdown")
def markdown_filter(text):
    """`{{ texte|markdown }}` : Markdown assaini (apps/core/markdown.py)."""
    return render(text)
