"""Persistenz und Export/Import: Rundreise, Neustart, beschädigte Dateien, Aufräumen, Prüfung beim Import."""

import json
import os
import time

import pytest

from lotse import config, speicher
from lotse.lotse import Lotse
from lotse.slots import SLOTS

PFLEGE = "Meine Mutter lebt in Wien, bezieht eine Pension von der PVA und kommt allein nicht mehr zurecht"
BRIEF = config.REPO_ROOT / "examples" / "entlassungsbrief_synthetisch.txt"


@pytest.fixture
def lotse(monkeypatch, tmp_path):
    monkeypatch.setenv("AZURE_API_KEY", "")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")
    monkeypatch.setattr(speicher, "ORDNER", tmp_path / "sitzungen")
    return Lotse()


def _fall(lotse):
    """Sitzung mit Szenario, Antworten, Dokument, Statuswechseln und vereinbartem Termin."""
    s = lotse.neue_sitzung()
    lotse.nachricht(s, PFLEGE)
    lotse.nachricht(s, "Nein")
    lotse.dokument(s, BRIEF.name, BRIEF.read_bytes())
    lotse.setze_status(s, "pflegegeld.antrag_unterschreiben", "erledigt")
    for text in ("Ich brauche einen Termin beim Zahnarzt", "egal", "nachmittags", "Termin am 12.11.2026 um 10:30"):
        lotse.nachricht(s, text)
    s.werte["person.svnr"] = "1234010180"  # sensibel: wird nie gespeichert
    s.herkunft["person.svnr"] = {"art": "dokument", "dokument": BRIEF.name, "seite": 1}
    return s


def _ohne_sensible(antwort: dict) -> dict:
    """Sensible Angaben werden bewusst nicht gespeichert – nach dem Laden fehlen sie wieder im Formular."""
    antwort["angaben"] = [a for a in antwort["angaben"] if not a["sensibel"]]
    for b in antwort["buendel"]:
        b["fehlende_angaben"] = [x for x in b["fehlende_angaben"] if not SLOTS[x["slot"]].sensibel]
    return antwort


def test_rundreise_ergibt_dieselbe_antwort(lotse):
    s = _fall(lotse)
    daten = json.loads(json.dumps(speicher.zu_dict(s)))
    assert daten["format"] == speicher.FORMAT and daten["version"] == speicher.VERSION
    kopie = speicher.aus_dict(daten)
    assert kopie.id == s.id
    assert _ohne_sensible(lotse.aktuell(kopie).to_dict()) == _ohne_sensible(lotse.aktuell(s).to_dict())
    assert kopie.fallakte.historie == s.fallakte.historie
    assert kopie.fallakte.termine == s.fallakte.termine
    assert lotse.termin_ics(kopie, "termin_1").split("DTSTAMP")[0] == lotse.termin_ics(s, "termin_1").split("DTSTAMP")[0]
    # der wiederhergestellte Fall läuft weiter
    a = lotse.setze_status(kopie, "pflegegeld.antrag_einreichen", "erledigt")
    assert a.status_uebersicht["erledigt"] > lotse.aktuell(s).status_uebersicht["erledigt"]


def test_sensible_angaben_und_verlauf_werden_nie_geschrieben(lotse):
    s = _fall(lotse)
    speicher.speichere(s)
    roh = (speicher.ordner() / f"{s.id}.json").read_text(encoding="utf-8")
    assert "1234010180" not in roh and "person.svnr" not in roh
    assert "verlauf" not in json.loads(roh)["sitzung"]


def test_freitext_einer_wissensfrage_wird_nicht_gespeichert(lotse):
    # Sensible Werte, die nicht als Rückfrage-Antwort kommen, landen sonst über die letzte Frage in Datei und Export
    s = _fall(lotse)
    lotse.nachricht(s, "Meine SVNR ist 1234010180 und meine IBAN AT611904300234573201")
    speicher.speichere(s)
    roh = (speicher.ordner() / f"{s.id}.json").read_text(encoding="utf-8")
    export = json.dumps(speicher.zu_dict(s), ensure_ascii=False)
    for inhalt in (roh, export):
        assert "1234010180" not in inhalt and "AT611904300234573201" not in inhalt


def test_neustart_laedt_sitzung_von_der_platte(lotse):
    s = _fall(lotse)
    speicher.speichere(s)
    assert not list(speicher.ordner().glob(".*.tmp"))  # atomar geschrieben
    geladen = speicher.lade(s.id)
    assert geladen is not None
    assert _ohne_sensible(lotse.aktuell(geladen).to_dict()) == _ohne_sensible(lotse.aktuell(s).to_dict())
    assert speicher.lade("0" * 32) is None


@pytest.mark.parametrize("inhalt", ["{kaputt", "[]", json.dumps({"format": speicher.FORMAT, "version": 99})])
def test_beschaedigte_datei_ergibt_keine_sitzung(lotse, inhalt):
    sid = "a" * 32
    speicher.ordner().mkdir(parents=True)
    (speicher.ordner() / f"{sid}.json").write_text(inhalt, encoding="utf-8")
    assert speicher.lade(sid) is None


def test_ungueltige_ids_werden_nicht_als_pfad_verwendet(lotse):
    for sid in ("../geheim", "A" * 32, "", "a" * 31):
        assert speicher.lade(sid) is None


def test_aufraeumen_loescht_nur_alte_dateien(lotse):
    alt, neu = lotse.neue_sitzung(), lotse.neue_sitzung()
    speicher.speichere(alt)
    speicher.speichere(neu)
    vor_40_tagen = time.time() - 40 * 86400
    os.utime(speicher.ordner() / f"{alt.id}.json", (vor_40_tagen, vor_40_tagen))
    assert speicher.aufraeumen() == 1
    assert speicher.lade(alt.id) is None and speicher.lade(neu.id) is not None


def _veraendert(daten: dict, pfad: list, wert) -> dict:
    kopie = json.loads(json.dumps(daten))
    ziel = kopie
    for schluessel in pfad[:-1]:
        ziel = ziel[schluessel]
    ziel[pfad[-1]] = wert
    return kopie


@pytest.mark.parametrize("pfad,wert", [
    (["format"], "etwas anderes"),
    (["version"], 2),
    (["sitzung", "leistungen"], ["gibt_es_nicht"]),
    (["sitzung", "szenarien"], ["urlaub"]),
    (["sitzung", "werte"], {"person.lieblingsfarbe": "blau"}),
    (["sitzung", "werte"], {"person.bundesland": "Bayern"}),
    (["sitzung", "stil"], "bunt"),
    (["sitzung", "fallakte", "status"], {"pflegegeld.gibt_es_nicht": "erledigt"}),
    (["sitzung", "fallakte", "status"], {"pflegegeld.antrag_ausfuellen": "fertig"}),
    (["sitzung", "fallakte", "termine"], [{"id": "termin_1", "anlass": "friseur"}]),
    (["sitzung", "dok_empfehlungen"], {"rehabilitation": [{"zitat": "x", "seite": 0, "quelle": {}}]}),
    (["sitzung", "id"], "../../etc/passwd"),
])
def test_import_lehnt_ungueltiges_ab(lotse, pfad, wert):
    daten = speicher.zu_dict(_fall(lotse))
    with pytest.raises(speicher.UngueltigeSitzung):
        speicher.aus_dict(_veraendert(daten, pfad, wert))


def test_import_mit_neuer_id_und_weitere_sprache_ohne_ki(lotse):
    daten = speicher.zu_dict(_fall(lotse))
    daten["sitzung"]["sprache"] = "tr"
    kopie = speicher.aus_dict(daten, neue_id="b" * 32)
    assert kopie.id == "b" * 32 and kopie.sprache == "en"
    with pytest.raises(speicher.UngueltigeSitzung):
        speicher.aus_dict("kein dict")
