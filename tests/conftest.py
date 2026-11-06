import pytest

from lotse import config as lotse_config


def pytest_configure(config):
    config.addinivalue_line("markers", "daten: benötigt die SV-Box-Quelldaten im Repo bzw. unter LOTSE_DATA_DIR")
    config.addinivalue_line("markers", "befunde: benötigt den Ordner Befunde/ (nicht im Repo, nur lokal aus der SV-Box)")


def pytest_collection_modifyitems(config, items):
    fehlt = {
        "daten": not lotse_config.daten_vorhanden(),
        "befunde": not lotse_config.datei("Befunde").is_dir(),
    }
    gruende = {
        "daten": "SV-Box-Quelldaten nicht vorhanden (LOTSE_DATA_DIR setzen)",
        "befunde": "Befunde/ nicht vorhanden (bewusst nicht im Repo)",
    }
    for item in items:
        for marker, ja in fehlt.items():
            if ja and marker in item.keywords:
                item.add_marker(pytest.mark.skip(reason=gruende[marker]))
