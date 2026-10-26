from django.apps import AppConfig


class AgendaConfig(AppConfig):
    name = "apps.agenda"
    label = "agenda"
    verbose_name = "Agenda"

    def ready(self):
        from apps.accounts import pending

        from .models import Event

        pending.register(
            "to_confirm",
            "manage_agenda",
            lambda n: pending.plural(n, "provisoire à confirmer", "provisoires à confirmer"),
            lambda: Event.objects.to_confirm().count(),
            "agenda:programming",
        )
        pending.register(
            "rooms",
            "manage_rooms",
            lambda n: pending.plural(n, "réservation à valider", "réservations à valider"),
            lambda: Event.objects.awaiting_room().count(),
            "agenda:room_requests",
        )
        pending.register(
            "publication",
            ("manage_agenda", "manage_public"),
            lambda n: pending.plural(n, "demande de publication", "demandes de publication"),
            lambda: Event.objects.awaiting_publication().count(),
            "agenda:public_requests",
        )
