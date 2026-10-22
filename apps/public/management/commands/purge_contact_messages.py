from django.core.management.base import BaseCommand

from apps.public import services


class Command(BaseCommand):
    help = "Efface les messages de contact de plus d'un an (à planifier chaque nuit)."

    def handle(self, *args, **options):
        deleted = services.purge_contact_messages()
        self.stdout.write(f"{deleted} message(s) effacé(s).")
