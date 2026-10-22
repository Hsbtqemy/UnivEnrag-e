import uuid

from django.conf import settings
from django.db import models


class Actor(models.Model):
    """Une personne qui agit sous son nom, sans compte (CDC §2).

    Un acteur correspond à un nom, pas à un navigateur : « Marie » saisi depuis deux
    appareils donne le même acteur. Toute contribution référence `Actor` par clé
    étrangère, pour qu'une identification individuelle puisse être ajoutée plus tard
    (champ `user`) sans changer aucune autre table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_name = models.CharField("nom affiché", max_length=120)
    name_key = models.CharField("nom normalisé", max_length=120, unique=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actor",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    anonymized_at = models.DateTimeField("anonymisée le", null=True, blank=True)

    class Meta:
        verbose_name = "personne"
        verbose_name_plural = "personnes"
        ordering = ["display_name"]

    def __str__(self) -> str:
        return self.display_name
