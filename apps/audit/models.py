from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Une action d'un administrateur ou d'un gestionnaire (CLAUDE.md LOG-1).

    Le journal accepte seulement des ajouts : ni modification ni suppression, y compris
    depuis l'admin.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audit_entries",
        verbose_name="compte",
    )
    action = models.CharField("action", max_length=60, db_index=True)
    object_type = models.CharField("type d'objet", max_length=60, blank=True)
    object_id = models.CharField("identifiant", max_length=64, blank=True)
    object_repr = models.CharField("objet", max_length=200, blank=True)
    details = models.JSONField("détails", default=dict, blank=True)
    created_at = models.DateTimeField("le", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "entrée du journal"
        verbose_name_plural = "journal d'activité"
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.created_at:%d/%m/%Y %H:%M} · {self.user} · {self.action}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Le journal d'activité ne se modifie pas.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Le journal d'activité ne se supprime pas.")
