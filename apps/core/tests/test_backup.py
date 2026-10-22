"""Sauvegarde et restauration (CLAUDE.md : « test de restauration d'une sauvegarde en CI »)."""

import io
import json
import os
import tarfile
import time

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from django.urls import reverse

from apps.core import backup
from apps.rooms.models import Room
from conftest import login_verified

# La restauration écrit dans la base hors de toute transaction de test.
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def backup_dir(tmp_path, settings):
    settings.BACKUP_DIR = tmp_path / "sauvegardes"
    return settings.BACKUP_DIR


def test_backup_then_restore_brings_data_back(backup_dir):
    Room.objects.create(name="Salle du collectif")
    archive = backup.create()
    assert backup.check(archive)["sha256"]

    Room.objects.all().delete()
    Room.objects.create(name="Salle arrivée après la sauvegarde")
    manifest, safety = backup.restore(archive)

    assert list(Room.objects.values_list("name", flat=True)) == ["Salle du collectif"]
    assert "core.0001_initial" in manifest["migrations"]
    # L'état remplacé n'est pas perdu : il a été sauvegardé juste avant.
    assert safety.exists() and "avant-restauration" in safety.name


def test_restore_command_needs_confirmation(backup_dir):
    Room.objects.create(name="Salle du collectif")
    archive = backup.create()
    Room.objects.all().delete()
    call_command("restore", str(archive), stdout=io.StringIO())
    assert not Room.objects.exists()
    call_command("restore", str(archive), "--confirmer", stdout=io.StringIO())
    assert Room.objects.filter(name="Salle du collectif").exists()


def _manifest(archive) -> dict:
    with tarfile.open(archive) as tar:
        return json.loads(tar.extractfile(backup.MANIFEST_NAME).read())


def _rewrite(archive, path, *, manifest=None, extra=None):
    """Recompose une archive à partir de `archive`, avec un manifeste modifié."""
    with tarfile.open(archive, "r:gz") as tar:
        db = tar.extractfile(backup.DB_NAME).read()
        original = json.loads(tar.extractfile(backup.MANIFEST_NAME).read())
    with tarfile.open(path, "w:gz") as tar:
        for name, data in [
            (backup.DB_NAME, db),
            (backup.MANIFEST_NAME, json.dumps(manifest or original).encode()),
            *(extra or []),
        ]:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def test_tampered_archive_is_refused(backup_dir, tmp_path):
    archive = backup.create()
    manifest = _manifest(archive)
    bad = _rewrite(archive, tmp_path / "abimee.tar.gz", manifest=manifest | {"sha256": "0" * 64})
    with pytest.raises(backup.BackupError, match="empreinte"):
        backup.restore(bad)
    with pytest.raises(CommandError):
        call_command("restore", str(bad), "--confirmer", stdout=io.StringIO())


def test_archive_with_unexpected_files_is_refused(backup_dir, tmp_path):
    archive = backup.create()
    odd = _rewrite(archive, tmp_path / "autre.tar.gz", extra=[("../evil", b"x")])
    with pytest.raises(backup.BackupError, match="pas une sauvegarde"):
        backup.check(odd)


def test_backup_from_a_newer_version_is_refused(backup_dir, tmp_path):
    archive = backup.create()
    manifest = _manifest(archive)
    manifest["migrations"].append("agenda.9999_futur")
    newer = _rewrite(archive, tmp_path / "future.tar.gz", manifest=manifest)
    # L'empreinte porte sur la base, pas sur le manifeste : seule la version bloque.
    with pytest.raises(backup.BackupError, match="plus récente"):
        backup.restore(newer)


def test_rotation_keeps_thirty_days(backup_dir):
    recent = backup.create()
    old = backup.create(label="ancienne")
    month_ago = time.time() - 31 * 86400
    os.utime(old, (month_ago, month_ago))
    assert backup.rotate() == 1
    assert recent.exists() and not old.exists()


def test_backup_command(backup_dir):
    out = io.StringIO()
    call_command("backup", stdout=out)
    assert len(list(backup_dir.glob("sauvegarde-*.tar.gz"))) == 1


def test_full_backup_download_is_for_the_superuser_only(backup_dir, admin_user, make_manager):
    manager = login_verified(Client(), make_manager("manage_agenda", "export_data"))
    assert manager.post(reverse("accounts:backup")).status_code == 403
    admin = login_verified(Client(), admin_user)
    response = admin.post(reverse("accounts:backup"))
    assert response.status_code == 200
    assert response["Content-Disposition"].startswith('attachment; filename="sauvegarde-')
