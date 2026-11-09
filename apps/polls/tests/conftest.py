import pytest


@pytest.fixture(autouse=True)
def polls_enabled(settings):
    """Les sondages sont fermés par défaut ; leurs propres tests les rouvrent."""
    settings.POLLS_ENABLED = True
