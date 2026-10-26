from django.apps import AppConfig


class IdeasConfig(AppConfig):
    name = "apps.ideas"
    label = "ideas"
    verbose_name = "Propositions d'événements"

    def ready(self):
        from apps.accounts import pending

        from .models import Idea

        pending.register(
            "moderation",
            "moderate",
            lambda n: pending.plural(n, "proposition à modérer", "propositions à modérer"),
            lambda: Idea.objects.filter(status=Idea.Status.PENDING).count(),
            "ideas:moderation",
        )
        pending.register(
            "to_place",
            "manage_agenda",
            lambda n: pending.plural(n, "idée à placer", "idées à placer"),
            lambda: Idea.objects.to_place().count(),
            "agenda:programming",
        )
