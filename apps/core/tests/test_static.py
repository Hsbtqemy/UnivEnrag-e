"""Les fichiers statiques de production se construisent (sinon le conteneur ne démarre pas)."""

import io

from django.core.management import call_command
from django.test import override_settings


def test_collectstatic_with_versioned_names(tmp_path):
    storages = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "apps.core.storage.StaticStorage"},
    }
    with override_settings(STATIC_ROOT=tmp_path, STORAGES=storages):
        call_command("collectstatic", interactive=False, verbosity=0, stdout=io.StringIO())
    assert (tmp_path / "staticfiles.json").exists()
    assert list((tmp_path / "css").glob("app.*.css"))
    assert list((tmp_path / "vendor" / "event-calendar-5.3.0").glob("event-calendar.min.*.js"))
