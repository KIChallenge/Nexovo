"""Smoke-Tests der Web-API über den FastAPI-TestClient."""

import json
import re

import pytest
from fastapi.testclient import TestClient

from lotse import config, speicher
from lotse.web import app as web
from lotse.web.app import STATIC, app

PFLEGE = "Meine Mutter ist chronisch krank und kommt allein nicht mehr zurecht"
BRIEF = config.REPO_ROOT / "examples" / "entlassungsbrief_synthetisch.txt"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("AZURE_API_KEY", "")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")
    monkeypatch.setattr(speicher, "ORDNER", tmp_path / "sitzungen")
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
    de = client.get("/api/texte").json()
    assert de["texte"]["senden"] == "Senden" and de["ki"] is False
    assert client.get("/api/texte?sprache=en").json()["texte"]["senden"] == "Send"
    assert {"pflege", "gesundheit", "entlassung", "kind", "unterstuetzung", "termin"} == set(
        de["texte"]["beispiele_saetze"])
    sprachen = {x["code"]: x for x in de["sprachen"]}
    assert set(sprachen) == {"de", "en", "tr", "bs", "uk", "ar"}
    assert sprachen["de"]["verfuegbar"] and not sprachen["tr"]["verfuegbar"] and sprachen["ar"]["richtung"] == "rtl"


def test_jeder_ui_schluessel_der_oberflaeche_existiert_in_de_und_en(client):
    """Alle Schlüssel, die die Oberfläche per t("…")/tf("…") oder data-t/data-label nutzt, liegen in texte.UI."""
    genutzt: dict[str, set[str]] = {}
    praefixe: set[str] = set()
    for datei in [*sorted(STATIC.glob("*.js")), STATIC / "index.html"]:
        quelle = datei.read_text(encoding="utf-8")
        for m in re.finditer(r"""\b(?:t|tf)\(\s*["'`]([A-Za-z0-9_]+)["'`]""", quelle):
            genutzt.setdefault(m.group(1), set()).add(datei.name)
        for m in re.finditer(r"""data-(?:t|label)=["']([A-Za-z0-9_]+)["']""", quelle):
            genutzt.setdefault(m.group(1), set()).add(datei.name)
        praefixe |= set(re.findall(r"""\b(?:t|tf)\(\s*`([a-z_]+)\$\{""", quelle))  # t(`box_${…}`)
    assert len(genutzt) > 50
    for sp in ("de", "en"):
        werte = client.get(f"/api/texte?sprache={sp}").json()["texte"]
        fehlt = {k: sorted(d) for k, d in genutzt.items() if not (isinstance(werte.get(k), str) and werte[k].strip())}
        assert not fehlt, (sp, fehlt)
        assert all(any(k.startswith(p) for k in werte) for p in praefixe), (sp, praefixe)


def test_weitere_sprachen_ohne_ki_werden_abgelehnt(client):
    assert client.get("/api/texte?sprache=tr").status_code == 400
    assert client.get("/api/texte?sprache=fr").status_code == 400
    assert client.post("/api/sitzung", json={"sprache": "ar"}).status_code == 400
    sid = _sitzung(client)
    assert client.post(f"/api/sitzung/{sid}/einstellungen", json={"sprache": "uk"}).status_code == 400


@pytest.mark.daten
def test_ablauf_sitzung_nachricht_upload_formular(client):
    sid = _sitzung(client)
    a = client.post(f"/api/sitzung/{sid}/nachricht", json={"text": PFLEGE}).json()
    assert len(a["buendel"]) >= 3 and a["rueckfrage"] is not None and a["modus"] == "regelbasiert"
    assert a["weitere_anzahl"] == max(0, len(a["buendel"]) - 3) and a["status_uebersicht"]["offen"] > 0

    a = client.post(f"/api/sitzung/{sid}/dokument",
                    files={"datei": (BRIEF.name, BRIEF.read_bytes(), "text/plain")}).json()
    reha = next(b for b in a["buendel"] if b["leistung_id"] == "rehabilitation")
    assert reha["dokument"] and "ausdrücklich dokumentierte Empfehlungen" in a["text"]
    assert [(d["name"], d["transkribiert"]) for d in a["dokumente"]] == [(BRIEF.name, False)]

    pal = next(b for b in a["buendel"] if b["formular"] and b["formular"]["id"] == "PAL080")
    r = client.get(pal["formular"]["url"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")

    a = client.post(f"/api/sitzung/{sid}/schritt/pflegegeld.antrag_unterschreiben", json={"status": "erledigt"}).json()
    eintrag = next(e for e in a["fallakte"]["eintraege"] if e["leistung_id"] == "pflegegeld")
    assert eintrag["naechster_schritt"] not in ("pflegegeld.antrag_ausfuellen", "pflegegeld.antrag_unterschreiben")

    a = client.post(f"/api/sitzung/{sid}/einstellungen", json={"sprache": "en", "stil": "ausfuehrlich"}).json()
    assert a["sprache"] == "en" and a["stil"] == "ausfuehrlich" and a["richtung"] == "ltr"
    assert client.get(f"/api/sitzung/{sid}").json()["sprache"] == "en"


def test_demo_dokumente(client):
    demos = client.get("/api/demo/dokumente").json()
    namen = [d["name"] for d in demos]
    assert "entlassungsbrief_synthetisch.txt" in namen
    assert ("Entlassungsbefund.pdf" in namen) == config.datei("Befunde/Entlassungsbefund.pdf").is_file()
    assert all(d["text_key"] and isinstance(d["nur_ki"], bool) for d in demos)
    sid = _sitzung(client)
    a = client.post(f"/api/sitzung/{sid}/demo/entlassungsbrief_synthetisch.txt").json()
    assert any(b["dokument"] for b in a["buendel"])
    assert client.post(f"/api/sitzung/{sid}/demo/passwort.txt").status_code == 404


def test_foto_upload_ohne_ki(client):
    sid = _sitzung(client)
    r = client.post(f"/api/sitzung/{sid}/dokument",
                    files={"datei": ("brief.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 64, "image/jpeg")})
    assert r.status_code == 200 and "KI-Modus" in r.json()["text"] and r.json()["dokumente"] == []


def test_termin_endpunkte_mit_kalenderdatei(client):
    sid = _sitzung(client)
    a = client.post(f"/api/sitzung/{sid}/termin", json={"anlass": "vorsorge"}).json()
    assert a["rueckfrage"]["slot"] == "termin.ort"
    client.post(f"/api/sitzung/{sid}/nachricht", json={"text": "Wien"})
    a = client.post(f"/api/sitzung/{sid}/nachricht", json={"text": "nachmittags"}).json()
    tm = a["termine"][0]
    assert tm["status"] == "vorbereitet" and tm["ics_url"] == "" and tm["anfrage_text"]
    assert client.get(f"/api/sitzung/{sid}/termin/{tm['id']}.ics").status_code == 404  # noch ohne Datum

    r = client.post(f"/api/sitzung/{sid}/termin/{tm['id']}", json={"datum": "2026-11-12", "uhrzeit": "9:30"})
    tm = r.json()["termine"][0]
    assert (tm["status"], tm["datum"], tm["uhrzeit"]) == ("vereinbart", "12.11.2026", "09:30")
    r = client.get(tm["ics_url"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    assert "attachment" in r.headers["content-disposition"]
    assert "DTSTART;TZID=Europe/Vienna:20261112T093000\r\n" in r.text and "LOCATION:Wien\r\n" in r.text

    erledigt = client.post(f"/api/sitzung/{sid}/termin/{tm['id']}", json={"status": "erledigt"}).json()
    assert erledigt["termine"][0]["status"] == "erledigt"

    assert client.post(f"/api/sitzung/{sid}/termin", json={"anlass": "friseur"}).status_code == 400
    assert client.post(f"/api/sitzung/{sid}/termin", json={"leistung": "gibt_es_nicht"}).status_code == 404
    assert client.post(f"/api/sitzung/{sid}/termin/termin_9", json={"datum": "12.11.2026"}).status_code == 404
    assert client.post(f"/api/sitzung/{sid}/termin/{tm['id']}", json={"datum": "31.02.2026"}).status_code == 400
    assert client.get(f"/api/sitzung/{sid}/termin/termin_9.ics").status_code == 404


def test_export_und_import(client):
    sid = _sitzung(client)
    vorher = client.post(f"/api/sitzung/{sid}/nachricht", json={"text": PFLEGE}).json()
    client.post(f"/api/sitzung/{sid}/schritt/pflegegeld.antrag_ausfuellen", json={"status": "erledigt"})
    r = client.get(f"/api/sitzung/{sid}/export")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    assert "attachment" in r.headers["content-disposition"]
    daten = r.json()
    assert daten["format"] == speicher.FORMAT and daten["version"] == speicher.VERSION

    r = client.post("/api/import", files={"datei": ("fall.json", r.content, "application/json")})
    assert r.status_code == 200
    a = r.json()
    assert a["sitzung_id"] != sid and "wiederhergestellt" in a["text"]
    assert [b["leistung_id"] for b in a["buendel"]] == [b["leistung_id"] for b in vorher["buendel"]]
    pg = next(e for e in a["fallakte"]["eintraege"] if e["leistung_id"] == "pflegegeld")
    assert next(x for x in pg["schritte"] if x["schritt_id"] == "antrag_ausfuellen")["status"] == "erledigt"
    assert client.get(f"/api/sitzung/{a['sitzung_id']}").status_code == 200

    falsch = [b"kein json", json.dumps({"format": "x"}).encode(), json.dumps({**daten, "version": 99}).encode(),
              json.dumps({**daten, "sitzung": {**daten["sitzung"], "leistungen": ["gibt_es_nicht"]}}).encode()]
    for inhalt in falsch:
        r = client.post("/api/import", files={"datei": ("fall.json", inhalt, "application/json")})
        assert r.status_code == 400, inhalt[:40]
        assert r.json()["detail"]


def test_sitzung_ueberlebt_neustart(client, monkeypatch):
    sid = _sitzung(client)
    vorher = client.post(f"/api/sitzung/{sid}/nachricht", json={"text": PFLEGE}).json()
    monkeypatch.setattr(web, "_sitzungen", type(web._sitzungen)())  # Neustart: Speicher leer, Platte bleibt
    r = client.get(f"/api/sitzung/{sid}")
    assert r.status_code == 200
    nachher = r.json()
    assert nachher["buendel"] == vorher["buendel"] and nachher["text"] == vorher["text"]
    assert client.post(f"/api/sitzung/{sid}/nachricht", json={"text": "Wien"}).status_code == 200


def test_fehlerfaelle(client):
    assert client.post("/api/sitzung/unbekannt/nachricht", json={"text": "Hallo"}).status_code == 404
    assert client.post("/api/sitzung", json={"sprache": "fr"}).status_code == 400
    sid = _sitzung(client)
    assert client.post(f"/api/sitzung/{sid}/einstellungen", json={"stil": "bunt"}).status_code == 400
    assert client.get(f"/api/sitzung/{sid}/formular/GIBTESNICHT").status_code == 404
    assert client.post(f"/api/sitzung/{sid}/schritt/x.y", json={"status": "erledigt"}).status_code == 404
    leer = client.post(f"/api/sitzung/{sid}/nachricht", json={"text": "   "}).json()
    assert leer["text"] and leer["buendel"] == []
    assert client.get("/api/sitzung/0123456789abcdef0123456789abcdef/export").status_code == 404


def test_leichte_sprache_und_ansage_ueber_die_api(client):
    r = client.post("/api/sitzung", json={"sprache": "de", "stil": "leicht"})
    assert r.status_code == 200 and r.json()["stil"] == "leicht" and r.json()["ansage"]
    sid = r.json()["sitzung_id"]
    a = client.post(f"/api/sitzung/{sid}/nachricht", json={"text": PFLEGE}).json()
    assert a["text"].startswith("Ich habe verstanden.") and "wichtige Hilfen gefunden" in a["ansage"]
    a = client.post(f"/api/sitzung/{sid}/einstellungen", json={"stil": "einfach"}).json()
    assert a["stil"] == "einfach" and a["ansage"] == "Einstellungen gespeichert: Deutsch, Einfach."
    a = client.post(f"/api/sitzung/{sid}/einstellungen", json={"stil": "leicht"}).json()
    assert a["stil"] == "leicht" and a["ansage"] == "Einstellungen gespeichert: Deutsch, Leichte Sprache."
    assert client.get(f"/api/sitzung/{sid}").json()["stil"] == "leicht"


def test_slots_fuer_die_formulare_der_oberflaeche(client):
    de = {x["id"]: x for x in client.get("/api/slots").json()}
    assert de and not any(sid.startswith("termin.") for sid in de)
    gd = de["person.geburtsdatum"]
    assert (gd["label"], gd["typ"], gd["muster_hinweis"], gd["sensibel"], gd["optionen"]) == (
        "Geburtsdatum", "datum", "TT.MM.JJJJ", True, [])
    assert gd["frage"] and de["person.plz"]["muster_hinweis"] == "4 Ziffern"
    assert {"wert": "zuerkennung", "label": "Erstantrag (Zuerkennung)"} in de["pflege.antragsart"]["optionen"]
    en = {x["id"]: x for x in client.get("/api/slots?sprache=en").json()}
    assert en["person.geburtsdatum"]["muster_hinweis"] == "DD.MM.YYYY"
    assert en["person.svnr"]["label"] == "Social security number"
    assert {"wert": "zuerkennung", "label": "first application"} in en["pflege.antragsart"]["optionen"]
    assert client.get("/api/slots?sprache=tr").status_code == 400  # weitere Sprachen nur im KI-Modus
    assert client.get("/api/slots?sprache=fr").status_code == 400


def test_angabe_setzen_pruefen_loeschen_und_speichern(client, monkeypatch):
    sid = _sitzung(client)
    client.post(f"/api/sitzung/{sid}/nachricht", json={"text": PFLEGE})
    url = f"/api/sitzung/{sid}/angabe"
    r = client.post(url, json={"slot": "person.bundesland", "wert": "Steiermark"})
    assert r.status_code == 200
    a = r.json()
    land = next(x for x in a["angaben"] if x["slot"] == "person.bundesland")
    assert (land["wert"], land["wert_roh"], land["herkunft"]) == ("Steiermark", "Steiermark", "von Ihnen geändert")
    assert a["ansage"].startswith("Gespeichert: Bundesland – Steiermark.")
    assert a["rueckfrage"] is None or a["rueckfrage"]["slot"] != "person.bundesland"
    assert all(not b["regionen"] or "Steiermark" in b["regionen"] for b in a["buendel"])

    # ungültig: 400 mit einer Erklärung in der Sprache der Sitzung
    r = client.post(url, json={"slot": "person.geburtsdatum", "wert": "31.02.1950"})
    assert r.status_code == 400 and "TT.MM.JJJJ" in r.json()["detail"]
    assert client.post(url, json={"slot": "termin.datum", "wert": "12.11.2026"}).status_code == 400
    assert client.post(url, json={"slot": "gibt.es.nicht", "wert": "x"}).status_code == 400
    assert client.post("/api/sitzung/unbekannt/angabe", json={"slot": "person.ort", "wert": "Graz"}).status_code == 404
    en = _sitzung(client, sprache="en")
    r = client.post(f"/api/sitzung/{en}/angabe", json={"slot": "person.plz", "wert": "12"})
    assert r.status_code == 400 and r.json()["detail"] == "Please check Postcode. Expected: 4 digits."

    # sensibel: maskiert, nie in Antwort, Datei oder Export
    a = client.post(url, json={"slot": "person.svnr", "wert": "1234 010180"}).json()
    svnr = next(x for x in a["angaben"] if x["slot"] == "person.svnr")
    assert svnr["wert"] == "hinterlegt" and svnr["wert_roh"] == "" and "1234010180" not in json.dumps(a)
    roh = (speicher.ordner() / f"{sid}.json").read_text(encoding="utf-8")
    assert "1234010180" not in roh and "person.svnr" not in roh
    assert "1234010180" not in client.get(f"/api/sitzung/{sid}/export").text

    # Neustart: die Änderung bleibt, die sensible Angabe fehlt bewusst
    monkeypatch.setattr(web, "_sitzungen", type(web._sitzungen)())
    nachher = {x["slot"]: x for x in client.get(f"/api/sitzung/{sid}").json()["angaben"]}
    assert nachher["person.bundesland"]["herkunft"] == "von Ihnen geändert" and "person.svnr" not in nachher

    # löschen (null oder "")
    a = client.post(url, json={"slot": "person.bundesland", "wert": None}).json()
    assert "person.bundesland" not in {x["slot"] for x in a["angaben"]}
    assert a["ansage"].startswith("Gelöscht: Bundesland.")
    client.post(url, json={"slot": "person.ort", "wert": "Graz"})
    a = client.post(url, json={"slot": "person.ort", "wert": ""}).json()
    assert "person.ort" not in {x["slot"] for x in a["angaben"]}
