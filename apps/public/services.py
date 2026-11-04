"""Écritures de la page publique : messages de contact, présentation, actualités."""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.actors.services import get_or_create_for_name
from apps.audit import audit
from apps.core.models import SiteSettings

from .models import ContactMessage, NewsPost


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


# --- Actualités : rédigées par un habilité « page publique » (CDC §7) -------------------

NEWS_FIELDS = ("title", "summary", "body", "published_at", "is_published")


def _unique_slug(title: str) -> str:
    base = slugify(title)[:150] or "actualite"
    slug, n = base, 2
    while NewsPost.objects.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


@transaction.atomic
def create_news(*, user, title, summary="", body, published_at=None, is_published=False):
    """L'adresse découle du titre et ne change plus : un lien partagé reste valable."""
    post = NewsPost.objects.create(
        title=title,
        slug=_unique_slug(title),
        summary=summary,
        body=body,
        published_at=published_at or timezone.now(),
        is_published=is_published,
        author=user,
    )
    audit.log(user, "public.news_created", post, published=is_published)
    return post


@transaction.atomic
def update_news(post: NewsPost, *, user, **fields) -> NewsPost:
    unknown = set(fields) - set(NEWS_FIELDS)
    if unknown:
        raise TypeError(f"Champs inconnus : {', '.join(sorted(unknown))}")
    for name, value in fields.items():
        setattr(post, name, value)
    if not post.published_at:
        post.published_at = timezone.now()
    post.save()
    audit.log(user, "public.news_updated", post, published=post.is_published)
    return post


@transaction.atomic
def set_news_published(post: NewsPost, *, user, published: bool) -> NewsPost:
    """Publier ou dépublier ; une actualité ne se supprime jamais (CLAUDE.md MOD-1)."""
    post.is_published = published
    post.save(update_fields=["is_published", "updated_at"])
    audit.log(user, "public.news_published" if published else "public.news_unpublished", post)
    return post
