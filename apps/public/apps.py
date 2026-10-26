from django.apps import AppConfig


class PublicConfig(AppConfig):
    name = "apps.public"
    label = "public"
    verbose_name = "Page publique"

    def ready(self):
        from apps.accounts import pending

        from .models import ContactMessage

        pending.register(
            "contact",
            "manage_public",
            lambda n: pending.plural(n, "message à traiter", "messages à traiter"),
            lambda: ContactMessage.objects.filter(handled_at=None).count(),
            "admin:public_contactmessage_changelist",
        )
