"""Stockage des fichiers statiques en production."""

from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


def _without_source_maps(patterns):
    def keep(pattern) -> bool:
        regex = pattern if isinstance(pattern, str) else pattern[0]
        return "sourceMappingURL" not in regex

    return tuple((ext, tuple(p for p in rules if keep(p))) for ext, rules in patterns)


class StaticStorage(ManifestStaticFilesStorage):
    """Noms versionnés (app.3f2a9c.css), pour un cache long sans mélange de versions.

    Les bibliothèques de `static/vendor/` citent leur fichier `.map`, qu'on ne livre pas et
    qu'on ne retouche pas (leur sha256 est noté dans VERSIONS.md) : sans ce réglage,
    `collectstatic` échouerait au démarrage du conteneur.
    """

    patterns = _without_source_maps(ManifestStaticFilesStorage.patterns)
