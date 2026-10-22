from django.db import models
from django.utils.text import slugify

from apps.core.validators import hex_color


class SpaceQuerySet(models.QuerySet):
    def open(self):
        return self.filter(is_archived=False)


class Space(models.Model):
    """Un groupe de travail (CDC §5). En phase 1 : nom, description, couleur.

    Les fils de discussion, documents et comptes rendus viendront en phase 3.
    """

    name = models.CharField("nom", max_length=80, unique=True)
    slug = models.SlugField("adresse", max_length=80, unique=True, blank=True)
    description = models.CharField("description courte", max_length=200, blank=True)
    color = models.CharField("couleur", max_length=7, default="#6b5b95", validators=[hex_color])
    # Un espace archivé reste lisible ; on ne peut plus y rattacher de nouvel événement.
    is_archived = models.BooleanField("archivé", default=False)

    objects = SpaceQuerySet.as_manager()

    class Meta:
        verbose_name = "espace"
        verbose_name_plural = "espaces"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:80]
        super().save(*args, **kwargs)
