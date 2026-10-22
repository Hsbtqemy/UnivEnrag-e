from django.core.management.base import BaseCommand

from apps.ideas import services


class Command(BaseCommand):
    help = "Passe à « Réalisée » les idées dont l'événement est passé (à planifier chaque nuit)."

    def handle(self, *args, **options):
        count = services.mark_done()
        self.stdout.write(f"{count} idée(s) passée(s) à « Réalisée ».")
