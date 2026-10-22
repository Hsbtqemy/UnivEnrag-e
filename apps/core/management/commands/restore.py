from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.core import backup


class Command(BaseCommand):
    help = (
        "Restaure une sauvegarde. Arrêtez d'abord le site (docker compose stop app cron). "
        "L'état courant est sauvegardé avant d'être remplacé."
    )

    def add_arguments(self, parser):
        parser.add_argument("archive", help="Chemin de l'archive sauvegarde-….tar.gz")
        parser.add_argument(
            "--confirmer", action="store_true", help="Remplacer réellement la base actuelle."
        )

    def handle(self, *args, archive, confirmer=False, **options):
        try:
            if not confirmer:
                manifest = backup.check(archive)
                self.stdout.write(
                    f"Archive valide, du {manifest['created_at']}. "
                    "Relancez avec --confirmer pour remplacer la base actuelle."
                )
                return
            manifest, safety = backup.restore(archive)
        except backup.BackupError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f"État précédent sauvegardé : {safety}")
        self.stdout.write(f"Base restaurée, du {manifest['created_at']}.")
        call_command("migrate", interactive=False, verbosity=0)
        self.stdout.write("Migrations appliquées.")
