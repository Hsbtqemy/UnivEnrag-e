from django.core.management.base import BaseCommand

from apps.presences import services


class Command(BaseCommand):
    help = "Efface les présences de plus de deux mois (à planifier chaque nuit)."

    def handle(self, *args, **options):
        deleted = services.purge()
        self.stdout.write(f"{deleted} présence(s) effacée(s).")
