"""Sauvegarde et restauration de la base (CLAUDE.md « Sécurité et RGPD »).

Une sauvegarde est une archive `sauvegarde-AAAAMMJJ-HHMMSS.tar.gz` qui contient :
  db.sqlite3      copie cohérente faite par l'API de sauvegarde de SQLite (jamais un `cp`
                  sur une base en WAL, qui peut donner une copie corrompue) ;
  manifest.json   date, empreinte SHA-256 de la base, migrations appliquées.

La restauration vérifie l'empreinte et l'intégrité, refuse une base plus récente que le
code, fait d'abord une sauvegarde de l'état courant, puis remplace la base en place.
"""

import hashlib
import json
import sqlite3
import tarfile
import tempfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

PREFIX = "sauvegarde-"
SUFFIX = ".tar.gz"
DB_NAME = "db.sqlite3"
MANIFEST_NAME = "manifest.json"


class BackupError(Exception):
    """Sauvegarde inutilisable ; le message s'affiche tel quel."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_integrity(path: Path) -> None:
    with sqlite3.connect(path) as db:
        result = db.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise BackupError(f"Base endommagée : {result}")


def _live_connection() -> sqlite3.Connection:
    connection.ensure_connection()
    return connection.connection


def _applied_migrations() -> list[str]:
    applied = MigrationRecorder(connection).applied_migrations()
    return sorted(f"{app}.{name}" for app, name in applied)


def create(directory: Path | None = None, *, label: str = "") -> Path:
    """Écrit une archive dans `directory` (par défaut `settings.BACKUP_DIR`)."""
    directory = Path(directory or settings.BACKUP_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    now = timezone.now()
    name = f"{PREFIX}{timezone.localtime(now):%Y%m%d-%H%M%S}{f'-{label}' if label else ''}"
    target = directory / f"{name}{SUFFIX}"
    with tempfile.TemporaryDirectory() as tmp:
        db_copy = Path(tmp) / DB_NAME
        with sqlite3.connect(db_copy) as destination:
            _live_connection().backup(destination)
        destination.close()
        _check_integrity(db_copy)
        manifest = {
            "created_at": now.isoformat(),
            "sha256": _sha256(db_copy),
            "migrations": _applied_migrations(),
        }
        (Path(tmp) / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2))
        # Écrite à côté puis renommée : une archive à moitié écrite ne passe jamais
        # pour une sauvegarde.
        partial = target.with_name(target.name + ".part")
        with tarfile.open(partial, "w:gz") as archive:
            archive.add(db_copy, arcname=DB_NAME)
            archive.add(Path(tmp) / MANIFEST_NAME, arcname=MANIFEST_NAME)
        partial.rename(target)
    return target


def rotate(directory: Path | None = None, *, keep_days: int | None = None) -> int:
    """Efface les archives de plus de `keep_days` jours ; renvoie le nombre effacé."""
    directory = Path(directory or settings.BACKUP_DIR)
    keep_days = settings.BACKUP_KEEP_DAYS if keep_days is None else keep_days
    limit = (timezone.now() - timedelta(days=keep_days)).timestamp()
    removed = 0
    for archive in directory.glob(f"{PREFIX}*{SUFFIX}"):
        if archive.stat().st_mtime < limit:
            archive.unlink()
            removed += 1
    return removed


def _extract(archive: Path, into: Path) -> dict:
    try:
        with tarfile.open(archive, "r:gz") as tar:
            names = set(tar.getnames())
            if names != {DB_NAME, MANIFEST_NAME}:
                raise BackupError("Cette archive n'est pas une sauvegarde du site.")
            tar.extractall(into, filter="data")
    except (tarfile.TarError, OSError) as error:
        raise BackupError(f"Archive illisible : {error}") from error
    manifest = json.loads((into / MANIFEST_NAME).read_text())
    if _sha256(into / DB_NAME) != manifest.get("sha256"):
        raise BackupError("L'empreinte ne correspond pas : la base a été modifiée ou abîmée.")
    _check_integrity(into / DB_NAME)
    return manifest


def check(archive: Path) -> dict:
    """Vérifie une archive sans rien toucher ; renvoie son manifeste."""
    with tempfile.TemporaryDirectory() as tmp:
        return _extract(Path(archive), Path(tmp))


def restore(archive: Path) -> tuple[dict, Path]:
    """Remplace la base par celle de l'archive. Renvoie le manifeste et la sauvegarde de
    sécurité faite juste avant. Lancer ensuite `migrate` si l'archive est plus ancienne."""
    with tempfile.TemporaryDirectory() as tmp:
        manifest = _extract(Path(archive), Path(tmp))
        known = MigrationLoader(None, ignore_no_migrations=True).disk_migrations
        unknown = [m for m in manifest["migrations"] if tuple(m.split(".", 1)) not in known]
        if unknown:
            raise BackupError(
                "Cette sauvegarde vient d'une version plus récente du site "
                f"({', '.join(unknown[:3])}…) : déployez d'abord cette version."
            )
        safety = create(label="avant-restauration")
        with sqlite3.connect(Path(tmp) / DB_NAME) as source:
            source.backup(_live_connection())
        source.close()
    return manifest, safety
