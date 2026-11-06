"""Gemeinsame Fixtures der Browser-Tests (Marker `ui`).

Startet den Lotsen regelbasiert (ohne Schlüssel, eigener Cache) auf einem freien Port und
Chromium über Playwright (`LOTSE_UI_BROWSER`). Ohne playwright, axe-playwright-python oder
Browser überspringt tests/conftest.py alle `ui`-Tests.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from messung import REPO, VIEWPORTS

# Vorlesen ohne Lautsprecher: Äußerungen mitschreiben, statt sie auszugeben
SPRACHAUSGABE_MITSCHRIFT = """
(() => {
  window.__gesprochen = [];
  window.__abgebrochen = 0;
  if (!("speechSynthesis" in window)) return;
  const s = window.speechSynthesis;
  s.speak = (u) => { window.__gesprochen.push({ text: u.text, lang: u.lang, rate: u.rate }); };
  s.cancel = () => { window.__abgebrochen += 1; };
})();
"""


def _freier_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def lotse_url(tmp_path_factory):
    """Basis-URL eines regelbasiert laufenden Lotsen (eigener Prozess, eigener Cache)."""
    if not os.environ.get("LOTSE_UI_BROWSER"):
        pytest.skip("LOTSE_UI_BROWSER nicht gesetzt")
    cache = tmp_path_factory.mktemp("lotse_cache")
    port = _freier_port()
    env = dict(os.environ, AZURE_API_KEY="", AZURE_OPENAI_ENDPOINT="",
               LOTSE_CACHE_DIR=str(cache), LOTSE_PORT=str(port))
    log = (cache / "server.log").open("wb")
    proc = subprocess.Popen([sys.executable, "-m", "lotse"], cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/"
    frist = time.time() + 180
    while True:
        if proc.poll() is not None:
            log.close()
            raise RuntimeError(f"Lotse-Server beendet: {(cache / 'server.log').read_text(errors='replace')[-2000:]}")
        try:
            with urllib.request.urlopen(url + "api/texte", timeout=5) as r:
                if r.status == 200:
                    break
        except OSError:
            pass
        if time.time() > frist:
            proc.kill()
            raise RuntimeError("Lotse-Server nicht rechtzeitig bereit")
        time.sleep(0.3)
    yield url
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    b = pw.chromium.launch(executable_path=os.environ["LOTSE_UI_BROWSER"])
    yield b
    b.close()
    pw.stop()


@pytest.fixture
def neue_seite(browser):
    """Fabrik für Seiten in frischen Kontexten: neue_seite("mobil_390", color_scheme="dark", ...)."""
    kontexte = []

    def erzeugen(viewport: str = "desktop", **optionen):
        ctx = browser.new_context(viewport=VIEWPORTS[viewport], locale="de-AT", **optionen)
        kontexte.append(ctx)
        ctx.add_init_script(SPRACHAUSGABE_MITSCHRIFT)
        page = ctx.new_page()
        page.set_default_timeout(15000)
        return page

    yield erzeugen
    for ctx in kontexte:
        ctx.close()
