import importlib.util
import os

import pytest

from lotse import config as lotse_config


def pytest_configure(config):
    config.addinivalue_line("markers", "daten: benötigt die SV-Box-Quelldaten im Repo bzw. unter LOTSE_DATA_DIR")
    config.addinivalue_line("markers", "befunde: benötigt den Ordner Befunde/ (nicht im Repo, nur lokal aus der SV-Box)")
    config.addinivalue_line("markers", "ui: Browser-Tests mit Playwright und axe-core (LOTSE_UI_BROWSER = Pfad zu Chromium)")


def _ui_verfuegbar() -> bool:
    browser = os.environ.get("LOTSE_UI_BROWSER", "")
    return (
        importlib.util.find_spec("playwright") is not None
        and importlib.util.find_spec("axe_playwright_python") is not None
        and bool(browser)
        and os.path.isfile(browser)
    )


def pytest_collection_modifyitems(config, items):
    fehlt = {
        "daten": not lotse_config.daten_vorhanden(),
        "befunde": not lotse_config.datei("Befunde").is_dir(),
        "ui": not _ui_verfuegbar(),
    }
    gruende = {
        "daten": "SV-Box-Quelldaten nicht vorhanden (LOTSE_DATA_DIR setzen)",
        "befunde": "Befunde/ nicht vorhanden (bewusst nicht im Repo)",
        "ui": "Browser-Tests: playwright/axe-playwright-python installieren und LOTSE_UI_BROWSER setzen (siehe requirements-dev.txt)",
    }
    for item in items:
        for marker, ja in fehlt.items():
            if ja and marker in item.keywords:
                item.add_marker(pytest.mark.skip(reason=gruende[marker]))
