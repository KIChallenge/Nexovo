"""Persistenz und Export/Import: Rundreise, Neustart, beschädigte Dateien, Aufräumen, Prüfung beim Import."""

import json
import os
import time

import pytest

from lotse import config, speicher
from lotse.lotse import Lotse

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
        b["fehlende_angaben"] = [x for x in b["fehlende_angaben"] if not x["sensibel"]]
        if b["formular"]:
            b["formular"]["fehlende_angaben"] = [x for x in b["formular"]["fehlende_angaben"] if not x["sensibel"]]
    antwort["fehlende_angaben_primaer"] = [x for x in antwort["fehlende_angaben_primaer"] if not x["sensibel"]]
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
    (["sitzung", "herkunft"], {"person.bundesland": {"art": "erfunden"}}),
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


def test_leichte_sprache_und_geaenderte_angaben_ueberstehen_rundreise(lotse):
    s = lotse.neue_sitzung(stil="leicht")
    lotse.nachricht(s, PFLEGE)
    lotse.angabe(s, "pflege.antragsart", "zuerkennung")
    lotse.angabe(s, "person.svnr", "1234010180")
    daten = json.loads(json.dumps(speicher.zu_dict(s)))
    assert daten["sitzung"]["stil"] == "leicht"
    assert daten["sitzung"]["herkunft"]["pflege.antragsart"] == {"art": "geaendert"}
    assert "1234010180" not in json.dumps(daten)
    kopie = speicher.aus_dict(daten)
    vorher, nachher = (_ohne_sensible(lotse.aktuell(x).to_dict()) for x in (s, kopie))
    assert nachher == vorher
    assert nachher["stil"] == "leicht" and nachher["text"].startswith("Ich habe geändert") and nachher["ansage"]
    # Umschalten nach dem Laden rendert die gespeicherte Antwort in der anderen Darstellung
    assert lotse.einstellungen(kopie, stil="einfach").text.startswith("Geändert: Sozialversicherungsnummer.")


def test_haken_aelterer_faelle_an_doppelten_unterlagen_bleiben_erhalten(lotse):
    """Früher standen Katalog- und Formulartext derselben Unterlage nebeneinander (Pflegegeld: unterlage_1 =
    „Vorhandene Befunde … in Kopie“ aus dem Katalog, unterlage_5 = dieselbe Unterlage laut Formular)."""
    s = lotse.neue_sitzung()
    lotse.nachricht(s, PFLEGE)
    daten = json.loads(json.dumps(speicher.zu_dict(s)))
    daten["sitzung"]["fallakte"]["status"].update({
        "pflegegeld.unterlage_1": "erledigt",  # ersetzte Katalog-Unterlage → Haken geht auf die Formular-Unterlage
        "pflegegeld.unterlage_42": "erledigt",  # Nummer aus einer älteren Zählung → Haken entfällt, kein Abbruch
    })
    daten["sitzung"]["fallakte"]["historie"].append({"zeit": "2026-11-01T10:00:00", "schritt_id": "pflegegeld.unterlage_1",
                                                    "leistung_id": "pflegegeld", "von": "offen", "nach": "erledigt"})
    kopie = speicher.aus_dict(daten)
    befunde = kopie.fallakte.schritt("pflegegeld.unterlage_1")
    assert befunde.id == "pflegegeld.unterlage_5" and befunde.status == "erledigt" and befunde.quelle is not None
    akte = next(e for e in lotse.aktuell(kopie).fallakte["eintraege"] if e["leistung_id"] == "pflegegeld")
    assert [u["id"] for u in akte["unterlagen"]] == [f"pflegegeld.unterlage_{n}" for n in range(5, 10)]
    assert lotse.aktuell(kopie).fallakte["historie"][-1]["text"] == befunde.text["de"]
    # nach dem Speichern steht der Haken unter der neuen ID
    assert speicher.zu_dict(kopie)["sitzung"]["fallakte"]["status"]["pflegegeld.unterlage_5"] == "erledigt"
