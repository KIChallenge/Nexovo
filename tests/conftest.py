import pytest

from lotse import config as lotse_config


def pytest_configure(config):
    config.addinivalue_line("markers", "daten: benötigt die lokalen SV-Box-Quelldaten (LOTSE_DATA_DIR)")


def pytest_collection_modifyitems(config, items):
    if lotse_config.daten_vorhanden():
        return
    skip = pytest.mark.skip(reason="SV-Box-Quelldaten nicht vorhanden (LOTSE_DATA_DIR setzen)")
    for item in items:
        if "daten" in item.keywords:
            item.add_marker(skip)
