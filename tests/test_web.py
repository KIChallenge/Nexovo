"""Smoke-Tests der Web-API über den FastAPI-TestClient."""

import pytest
from fastapi.testclient import TestClient

from lotse import config
from lotse.web.app import app

PFLEGE = "Meine Mutter ist chronisch krank und kommt allein nicht mehr zurecht"
BRIEF = config.REPO_ROOT / "examples" / "entlassungsbrief_synthetisch.txt"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AZURE_API_KEY", "")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")
    return TestClient(app)


def _sitzung(client, **daten) -> str:
    r = client.post("/api/sitzung", json=daten or {"sprache": "de", "stil": "einfach"})
    assert r.status_code == 200
    return r.json()["sitzung_id"]


def test_startseite_statische_dateien_und_texte(client):
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "/static/app.js" in r.text
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200
    texte = client.get("/api/texte").json()
    assert texte["de"]["senden"] == "Senden" and texte["en"]["senden"] == "Send"
    assert set(texte["en"]["beispiele_saetze"]) == {"pflege", "gesundheit", "entlassung", "kind"}


@pytest.mark.daten
def test_ablauf_sitzung_nachricht_upload_formular(client):
    sid = _sitzung(client)
    a = client.post(f"/api/sitzung/{sid}/nachricht", json={"text": PFLEGE}).json()
    assert len(a["buendel"]) >= 3 and a["rueckfrage"] is not None and a["modus"] == "regelbasiert"

    a = client.post(f"/api/sitzung/{sid}/dokument",
                    files={"datei": (BRIEF.name, BRIEF.read_bytes(), "text/plain")}).json()
    reha = next(b for b in a["buendel"] if b["leistung_id"] == "rehabilitation")
    assert reha["dokument"] and "In Ihrem Dokument steht" in a["text"]

    pal = next(b for b in a["buendel"] if b["formular"] and b["formular"]["id"] == "PAL080")
    r = client.get(pal["formular"]["url"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")

    a = client.post(f"/api/sitzung/{sid}/schritt/pflegegeld.antrag_unterschreiben", json={"status": "erledigt"}).json()
    eintrag = next(e for e in a["fallakte"]["eintraege"] if e["leistung_id"] == "pflegegeld")
    assert eintrag["naechster_schritt"] not in ("pflegegeld.antrag_ausfuellen", "pflegegeld.antrag_unterschreiben")

    a = client.post(f"/api/sitzung/{sid}/einstellungen", json={"sprache": "en", "stil": "ausfuehrlich"}).json()
    assert a["sprache"] == "en" and a["stil"] == "ausfuehrlich"
    assert client.get(f"/api/sitzung/{sid}").json()["sprache"] == "en"


def test_demo_dokumente(client):
    namen = [d["name"] for d in client.get("/api/demo/dokumente").json()]
    assert "entlassungsbrief_synthetisch.txt" in namen
    assert ("Entlassungsbefund.pdf" in namen) == config.datei("Befunde/Entlassungsbefund.pdf").is_file()
    sid = _sitzung(client)
    a = client.post(f"/api/sitzung/{sid}/demo/entlassungsbrief_synthetisch.txt").json()
    assert any(b["dokument"] for b in a["buendel"])
    assert client.post(f"/api/sitzung/{sid}/demo/passwort.txt").status_code == 404


def test_fehlerfaelle(client):
    assert client.post("/api/sitzung/unbekannt/nachricht", json={"text": "Hallo"}).status_code == 404
    assert client.post("/api/sitzung", json={"sprache": "fr"}).status_code == 400
    sid = _sitzung(client)
    assert client.post(f"/api/sitzung/{sid}/einstellungen", json={"stil": "bunt"}).status_code == 400
    assert client.get(f"/api/sitzung/{sid}/formular/GIBTESNICHT").status_code == 404
    assert client.post(f"/api/sitzung/{sid}/schritt/x.y", json={"status": "erledigt"}).status_code == 404
    leer = client.post(f"/api/sitzung/{sid}/nachricht", json={"text": "   "}).json()
    assert leer["text"] and leer["buendel"] == []
