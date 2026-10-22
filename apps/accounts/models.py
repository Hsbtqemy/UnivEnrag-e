from django.contrib.auth.models import AbstractUser

# Les droits qu'un administrateur peut confier à un gestionnaire (CDC §2 et §8).
# L'administrateur principal (`is_superuser`) les a tous, et seul lui gère les comptes,
# le code d'accès et le journal d'activité (CLAUDE.md ACC-4).
CAPABILITIES = [
    ("manage_votes", "Votes"),
    ("manage_agenda", "Agenda"),
    ("manage_rooms", "Salles"),
    ("manage_spaces", "Espaces"),
    ("moderate", "Modération"),
    ("manage_public", "Page publique"),
    ("export_data", "Exports"),
]


class User(AbstractUser):
    """Compte de l'administrateur principal ou d'un gestionnaire.

    Les participants n'ont pas de compte : ils agissent sous leur nom (`actors.Actor`).
    """

    class Meta:
        verbose_name = "compte de gestion"
        verbose_name_plural = "comptes de gestion"
        permissions = CAPABILITIES

    def __str__(self) -> str:
        return self.get_full_name() or self.username
