from django.core.management.base import BaseCommand

from apps.core import ratelimit


class Command(BaseCommand):
    help = "Efface les empreintes d'adresses IP de plus de 30 jours (à planifier chaque nuit)."

    def handle(self, *args, **options):
        deleted = ratelimit.purge()
        self.stdout.write(f"{deleted} empreinte(s) effacée(s).")
