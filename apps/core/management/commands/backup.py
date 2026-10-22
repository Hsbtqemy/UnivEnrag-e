from django.core.management.base import BaseCommand

from apps.core import backup


class Command(BaseCommand):
    help = "Sauvegarde la base (archive datée) et efface celles de plus de 30 jours."

    def add_arguments(self, parser):
        parser.add_argument("--dossier", help="Dossier des archives (défaut : DJANGO_BACKUP_DIR).")

    def handle(self, *args, dossier=None, **options):
        archive = backup.create(dossier)
        removed = backup.rotate(dossier)
        self.stdout.write(f"Sauvegarde : {archive}")
        if removed:
            self.stdout.write(f"{removed} ancienne(s) sauvegarde(s) effacée(s).")
