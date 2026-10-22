"""Limitation de débit par adresse IP, sans jamais stocker l'IP en clair."""

import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import RateLimitHit


def client_ip(request) -> str:
    # Derrière un proxy, REMOTE_ADDR est celle du proxy : toutes les tentatives
    # s'imputeraient à une seule origine et la limite fermerait le formulaire à tous.
    if settings.TRUST_X_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def ip_hash(request) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(), client_ip(request).encode(), hashlib.sha256
    ).hexdigest()


def exceeded(request, bucket: str, limit: int, window_seconds: int) -> bool:
    """Vrai si la limite est déjà atteinte sur la fenêtre, sans rien compter."""
    since = timezone.now() - timedelta(seconds=window_seconds)
    recent = RateLimitHit.objects.filter(
        bucket=bucket, key_hash=ip_hash(request), created_at__gte=since
    )
    return recent.count() >= limit


def record(request, bucket: str) -> None:
    """Compte une tentative (par exemple un échec de saisie du code)."""
    RateLimitHit.objects.create(bucket=bucket, key_hash=ip_hash(request))


def hit(request, bucket: str, limit: int, window_seconds: int) -> bool:
    """Compte une tentative et indique si elle reste sous la limite.

    Les tentatives au-delà de la limite ne sont pas enregistrées : un robot qui insiste
    ne remplit pas la table.
    """
    if exceeded(request, bucket, limit, window_seconds):
        return False
    record(request, bucket)
    return True


def purge(older_than_days: int = 30) -> int:
    """Efface les empreintes de plus de 30 jours (CDC §9, durée de conservation des IP)."""
    limit = timezone.now() - timedelta(days=older_than_days)
    deleted, _ = RateLimitHit.objects.filter(created_at__lt=limit).delete()
    return deleted
