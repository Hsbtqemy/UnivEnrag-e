from django import template

from apps.core.dates import format_fr

register = template.Library()


@register.filter(expects_localtime=True, is_safe=False)
def date_fr(value, fmt):
    """`{{ jour|date_fr:"l j F" }}` : « dimanche 1er novembre »."""
    return format_fr(value, fmt)
