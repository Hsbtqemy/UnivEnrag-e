"""Écritures de la page publique : messages de contact, présentation."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.actors.services import get_or_create_for_name
from apps.audit import audit
from apps.core.models import SiteSettings

from .models import ContactMessage


@transaction.atomic
def submit_contact(*, name: str, email: str, message: str) -> ContactMessage:
    return ContactMessage.objects.create(
        sender=get_or_create_for_name(name), email=email.strip(), message=message.strip()
    )


@transaction.atomic
def mark_handled(message: ContactMessage, *, user) -> ContactMessage:
    if message.handled_at is None:
        message.handled_at, message.handled_by = timezone.now(), user
        message.save(update_fields=["handled_at", "handled_by"])
        audit.log(user, "public.contact_handled", message)
    return message


def purge_contact_messages(now=None) -> int:
    """Messages de plus d'un an effacés (CONTACT_KEEP_DAYS, décision à confirmer)."""
    limit = (now or timezone.now()) - timedelta(days=settings.CONTACT_KEEP_DAYS)
    deleted, _ = ContactMessage.objects.filter(created_at__lt=limit).delete()
    return deleted


@transaction.atomic
def set_presentation(text: str, *, user) -> SiteSettings:
    site = SiteSettings.get()
    site.presentation = text.strip()
    site.save(update_fields=["presentation", "updated_at"])
    audit.log(user, "public.presentation_changed", site)
    return site
