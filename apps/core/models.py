from django.db import models


class RateLimitHit(models.Model):
    """Une tentative comptée pour la limitation de débit.

    L'adresse IP n'est jamais stockée en clair : seule son empreinte HMAC l'est
    (CLAUDE.md, « Sécurité et RGPD »). Le compteur vit en base, et non dans le cache
    local d'un processus, pour rester juste avec plusieurs workers.
    """

    bucket = models.CharField(max_length=40)
    key_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["bucket", "key_hash", "created_at"])]

    def __str__(self) -> str:
        return f"{self.bucket} · {self.created_at:%Y-%m-%d %H:%M}"
