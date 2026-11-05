"""Engine-Tests: Szenarien, Rückfragen, Grenze, Sprache/Stil, Fallakte, Dokument, Wissensfragen."""

import json
from io import BytesIO

import pytest
from pypdf import PdfReader

from lotse import config, dokument, katalog, llm, wissen
from lotse.fallakte import Fallakte
from lotse.lotse import Lotse, extrahiere, normalisiere
from lotse.slots import SLOTS

SAETZE = {
    "pflege": "Meine Mutter ist chronisch krank und kommt allein nicht mehr zurecht",
    "gesundheit": "Ich möchte etwas für meine Gesundheit tun",
    "entlassung": "Ich habe einen Befund/Entlassungsbrief bekommen – was muss ich jetzt erledigen?",
    "kind": "Ich habe ein Kind und möchte wissen, welche Angebote es gibt",
}
PFLEGE_EN = "My mother is chronically ill and can no longer manage on her own"
BRIEF = config.REPO_ROOT / "examples" / "entlassungsbrief_synthetisch.txt"

# Antworten einer Bürgerin im Pflegefall (synthetisch)
ANTWORT = {
    "person.bundesland": "Wien",
    "versicherung.pension": "PVA",
    "pflege.antragsart": "Nein",
    "versicherung.krankenversicherung": "ÖGK",
    "anliegen.fuer_wen": "für meine Mutter",
    "kind.alter": "3",
}


def _antwort_fuer(slot_id: str) -> str:
    if slot_id in ANTWORT:
        return ANTWORT[slot_id]
    slot = SLOTS[slot_id]
    return slot.optionen[0] if slot.optionen else "weiß nicht"


def _durchlauf(lotse, s, a, max_fragen=10):
    """Beantwortet Rückfragen, bis keine mehr kommt; liefert letzte Antwort und gestellte Slots."""
    gestellt = []
    while a.rueckfrage and len(gestellt) < max_fragen:
        gestellt.append(a.rueckfrage["slot"])
        a = lotse.nachricht(s, _antwort_fuer(gestellt[-1]))
    return a, gestellt


def _quellentitel(a):
    return [[q["titel"] for q in b["quellen"]] for b in a.buendel]


@pytest.fixture
def lotse(monkeypatch):
    # Regelbasierter Modus, unabhängig von einer lokalen .env
    monkeypatch.setenv("AZURE_API_KEY", "")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")
    return Lotse()


# ---------------------------------------------------------------- Szenarien und Rückfragen

@pytest.mark.parametrize("szenario", list(SAETZE))
def test_szenario_liefert_mindestens_drei_buendel_mit_quelle_und_stelle(lotse, szenario):
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, SAETZE[szenario])
    assert a.grenze is None
    assert szenario in [x["id"] for x in a.szenarien]
    assert len(a.buendel) >= 3
    for b in a.buendel:
        assert b["quellen"], b["leistung_id"]
        assert all(q["titel"] and (q["fundstelle"] or q["url"]) for q in b["quellen"]), b["leistung_id"]
        assert b["stelle"]["name"].strip(), b["leistung_id"]
    json.dumps(a.to_dict())


@pytest.mark.daten
def test_pflegefall_erreicht_pal080_entwurf_mit_hoechstens_fuenf_rueckfragen(lotse):
    s = lotse.neue_sitzung()
    a, gestellt = _durchlauf(lotse, s, lotse.nachricht(s, SAETZE["pflege"]))
    assert 1 <= len(gestellt) <= 5
    assert len(set(gestellt)) == len(gestellt)
    assert not any(SLOTS[x].sensibel for x in gestellt)
    pg = next(b for b in a.buendel if b["formular"] and b["formular"]["id"] == "PAL080")
    assert pg["stelle"]["aufgeloest"] and pg["stelle"]["abhaengig_von"] is None
    # persönliche Angaben ergänzt die Person im PDF; bereits Bekanntes fehlt nicht
    fehlend = {f["slot"] for f in pg["fehlende_angaben"]}
    assert "person.svnr" in fehlend and "pflege.antragsart" not in fehlend
    pdf = lotse.formular_pdf(s, "PAL080")
    assert pdf.startswith(b"%PDF")
    felder = PdfReader(BytesIO(pdf)).get_fields() or {}
    assert any(str(f.get("/V", "")) not in ("", "/Off", "None") for f in felder.values())
    assert s.fallakte.schritt(f"{pg['leistung_id']}.antrag_ausfuellen").status == "in_arbeit"


def test_rueckfragen_in_reihenfolge_region_zustaendigkeit_antragsart(lotse):
    s = lotse.neue_sitzung()
    _, gestellt = _durchlauf(lotse, s, lotse.nachricht(s, SAETZE["pflege"]))
    if any(l.regionen for l in katalog.fuer_szenario("pflege")):
        assert gestellt[0] == "person.bundesland"
    assert gestellt.index("versicherung.pension") < gestellt.index("pflege.antragsart")


def test_rueckfrage_fuellt_slot_und_naechste_frage_ist_anders(lotse):
    s = lotse.neue_sitzung()
    erste = lotse.nachricht(s, SAETZE["pflege"]).rueckfrage["slot"]

    unklar = lotse.nachricht(s, "blau")
    assert unklar.rueckfrage["slot"] == erste
    assert erste not in s.werte

    a = lotse.nachricht(s, _antwort_fuer(erste))
    assert s.werte[erste] == normalisiere(erste, _antwort_fuer(erste))
    assert s.herkunft[erste]["art"] == "dialog"
    assert a.rueckfrage is None or a.rueckfrage["slot"] != erste


def test_nebenbei_genannte_angaben_werden_nicht_erfragt(lotse):
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, "Meine Mutter lebt in Tirol, bezieht eine Pension von der PVA und kommt allein "
                           "nicht mehr zurecht")
    assert s.werte["person.bundesland"] == "Tirol"
    assert s.werte["versicherung.pension"] == "PVA"
    assert a.rueckfrage is None or a.rueckfrage["slot"] not in ("person.bundesland", "versicherung.pension")
    # regionale Angebote anderer Bundesländer fallen weg
    assert all(not b["regionen"] or "Tirol" in b["regionen"] for b in a.buendel)


@pytest.mark.parametrize("slot_id,eingabe,erwartet", [
    ("pflege.antragsart", "Ja", "erhoehung"),
    ("pflege.antragsart", "nein, noch nicht", "zuerkennung"),
    ("pflege.antragsart", "No", "zuerkennung"),
    ("pflege.antragsart", "yes, already", "erhoehung"),
    ("versicherung.pension", "Pensionsversicherungsanstalt", "PVA"),
    ("versicherung.pension", "pva", "PVA"),
    ("versicherung.pension", "keine Pension", "keine"),
    ("versicherung.pension", "SVS", "SVS"),
    ("versicherung.krankenversicherung", "Österreichische Gesundheitskasse", "ÖGK"),
    ("person.bundesland", "vienna", "Wien"),
    ("person.bundesland", "Lower Austria", "Niederösterreich"),
    ("person.bundesland", "in der Steiermark", "Steiermark"),
    ("person.bundesland", "NÖ", "Niederösterreich"),
    ("person.bundesland", "Kaernten", "Kärnten"),
    ("person.geburtsdatum", "1.3.1950", "01.03.1950"),
    ("person.geburtsdatum", "1950-03-01", "01.03.1950"),
    ("pflege.stufe", "Stufe drei", "3"),
    ("kind.alter", "sie ist 4", "4"),
    ("anliegen.fuer_wen", "für meinen Vater", "angehoerige"),
])
def test_normalisiere_antworten(slot_id, eingabe, erwartet):
    assert normalisiere(slot_id, eingabe) == erwartet


@pytest.mark.parametrize("slot_id,eingabe", [
    ("person.geburtsdatum", "31.02.1950"),
    ("pflege.stufe", "9"),
    ("person.bundesland", "Bayern"),
    ("person.bundesland", "Wien oder Tirol"),
    ("versicherung.pension", "ja"),
])
def test_normalisiere_lehnt_ungueltiges_ab(slot_id, eingabe):
    assert normalisiere(slot_id, eingabe) is None


def test_extrahiere_nebenbei_genannte_angaben():
    assert extrahiere("Meine Mutter lebt in Tirol, bezieht eine Pension von der PVA und bekommt noch kein "
                      "Pflegegeld") == {
        "person.bundesland": "Tirol",
        "versicherung.pension": "PVA",
        "anliegen.fuer_wen": "angehoerige",
        "pflege.antragsart": "zuerkennung",
    }
    assert extrahiere("My father lives in Upper Austria") == {
        "person.bundesland": "Oberösterreich", "anliegen.fuer_wen": "angehoerige",
    }
    assert extrahiere("Mein Kind ist 3 Jahre alt", ["kind"]) == {"kind.alter": "3"}
    assert extrahiere(SAETZE["gesundheit"]) == {}


# ---------------------------------------------------------------- Grenze

@pytest.mark.parametrize("frage", [
    "Welche Dosis Ibuprofen soll ich nehmen?",
    "Brauche ich wegen meiner Diagnose eine Reha?",
    "What dose of ibuprofen should I take?",
])
def test_medizinische_frage_wird_ohne_buendel_abgelehnt(lotse, frage):
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, frage)
    assert a.grenze is not None and a.grenze["erlaubt"] is False
    assert a.buendel == []
    assert s.szenarien == [] and s.werte == {}
    assert a.text.strip()


def test_grenzfrage_mitten_im_fall_laesst_fallakte_bestehen(lotse):
    s = lotse.neue_sitzung()
    vorher = [b["leistung_id"] for b in lotse.nachricht(s, SAETZE["pflege"]).buendel]
    a = lotse.nachricht(s, "Welche Dosis Ibuprofen soll ich nehmen?")
    assert a.grenze is not None and a.buendel == []
    assert [b["leistung_id"] for b in lotse.einstellungen(s, sprache="en").buendel] == vorher


# ---------------------------------------------------------------- Sprache und Darstellung

def test_englisch_liefert_englischen_text_mit_gleichen_quellen(lotse):
    de, en = lotse.neue_sitzung("de"), lotse.neue_sitzung("en")
    a_de = lotse.nachricht(de, SAETZE["pflege"])
    a_en = lotse.nachricht(en, PFLEGE_EN)
    assert "Ich habe Ihr Anliegen so verstanden" in a_de.text
    assert "I understood your request" in a_en.text
    assert [b["leistung_id"] for b in a_de.buendel] == [b["leistung_id"] for b in a_en.buendel]
    assert _quellentitel(a_de) == _quellentitel(a_en)
    assert a_en.rueckfrage["frage"] == SLOTS[a_en.rueckfrage["slot"]].frage["en"]


def test_ausfuehrlich_ergaenzt_details_bei_gleichen_quellen(lotse):
    s = lotse.neue_sitzung()
    einfach = lotse.nachricht(s, SAETZE["pflege"])
    ausf = lotse.einstellungen(s, stil="ausfuehrlich")
    assert len(ausf.text) > len(einfach.text)
    assert all(not b["details"] and not b["voraussetzungen"] for b in einfach.buendel)
    assert any(b["details"] or b["voraussetzungen"] for b in ausf.buendel)
    assert _quellentitel(ausf) == _quellentitel(einfach)
    en = lotse.einstellungen(s, sprache="en")
    assert en.sprache == "en" and en.stil == "ausfuehrlich" and "I understood your request" in en.text
    with pytest.raises(ValueError):
        lotse.einstellungen(s, sprache="fr")


# ---------------------------------------------------------------- Fallakte

def _akte() -> Fallakte:
    fa = Fallakte()
    fa.ergaenze(
        "pflegegeld", {"de": "Pflegegeld", "en": "Care allowance"},
        [{"id": i, "de": f"{i} (de)", "en": f"{i} (en)"} for i in (
            "antrag_ausfuellen", "unterlagen_sammeln", "antrag_unterschreiben", "antrag_einreichen", "bescheid_abwarten")],
        [({"de": "Ärztlicher Befund", "en": "Medical report"}, None)],
    )
    fa.ergaenze("reha", {"de": "Reha", "en": "Rehab"}, [{"id": "antrag_ausfuellen", "de": "a", "en": "a"}], [])
    return fa


def test_fallakte_antragskette_und_naechster_schritt():
    fa = _akte()
    assert fa.naechster_schritt().id == "pflegegeld.antrag_ausfuellen"
    fa.setze("pflegegeld.antrag_unterschreiben", "erledigt")
    assert fa.schritt("pflegegeld.antrag_ausfuellen").status == "erledigt"
    # nächster Schritt folgt dem Fortschritt; Übersprungenes bleibt offen
    assert fa.naechster_schritt("pflegegeld").id == "pflegegeld.antrag_einreichen"
    assert fa.schritt("pflegegeld.unterlagen_sammeln").status == "offen"
    assert [(h["schritt_id"], h["nach"]) for h in fa.historie] == [
        ("pflegegeld.antrag_ausfuellen", "erledigt"), ("pflegegeld.antrag_unterschreiben", "erledigt"),
    ]
    fa.setze("pflegegeld.unterlagen_sammeln", "erledigt")
    d = fa.to_dict("en")
    json.dumps(d)
    assert d["naechster_schritt"]["id"] == "pflegegeld.antrag_einreichen"
    assert d["naechster_schritt"]["text"] == "antrag_einreichen (en)"
    assert d["eintraege"][0]["erledigt"] == 3 and d["eintraege"][0]["gesamt"] == 5


def test_fallakte_in_arbeit_hat_vorrang_und_fehler():
    fa = _akte()
    fa.setze("reha.antrag_ausfuellen", "in_arbeit")
    assert fa.naechster_schritt().id == "reha.antrag_ausfuellen"
    with pytest.raises(ValueError):
        fa.setze("reha.antrag_ausfuellen", "fertig")
    with pytest.raises(KeyError):
        fa.setze("reha.unbekannt", "erledigt")


def test_fallakte_ergaenzt_idempotent_und_behaelt_begonnenes():
    fa = _akte()
    fa.ergaenze("pflegegeld", {"de": "Pflegegeld", "en": "Care allowance"},
                [{"id": "antrag_ausfuellen", "de": "x", "en": "x"}],
                [({"de": "ärztlicher  befund", "en": "x"}, None)])
    assert len(fa.eintraege["pflegegeld"].schritte) == 5
    assert len(fa.eintraege["pflegegeld"].unterlagen) == 1
    fa.setze("pflegegeld.unterlage_1", "erledigt")
    fa.behalte([])
    assert list(fa.eintraege) == ["pflegegeld"]


def test_statuswechsel_aendert_naechsten_schritt(lotse):
    s = lotse.neue_sitzung()
    lotse.nachricht(s, SAETZE["pflege"])
    vorher = s.fallakte.naechster_schritt("pflegegeld").id
    a = lotse.setze_status(s, "pflegegeld.antrag_unterschreiben", "erledigt")
    eintrag = next(e for e in a.fallakte["eintraege"] if e["leistung_id"] == "pflegegeld")
    assert eintrag["naechster_schritt"] not in (vorher, "pflegegeld.antrag_ausfuellen",
                                                "pflegegeld.antrag_unterschreiben")
    assert "erledigt" in a.text
    # dasselbe per Chat
    lotse.nachricht(s, "Ich habe den Pflegegeld-Antrag eingereicht")
    assert s.fallakte.schritt("pflegegeld.antrag_einreichen").status == "erledigt"
    with pytest.raises(ValueError):
        lotse.setze_status(s, "pflegegeld.antrag_einreichen", "fertig")
    with pytest.raises(KeyError):
        lotse.setze_status(s, "pflegegeld.gibt_es_nicht", "erledigt")


# ---------------------------------------------------------------- Dokument

def test_synthetischer_brief_ergibt_reha_buendel_mit_woertlichem_zitat(lotse):
    inhalt = BRIEF.read_bytes()
    brieftext = " ".join(inhalt.decode("utf-8").split())
    s = lotse.neue_sitzung()
    a = lotse.dokument(s, BRIEF.name, inhalt)
    assert "entlassung" in [x["id"] for x in a.szenarien]
    reha = next(b for b in a.buendel if b["leistung_id"] == "rehabilitation")
    assert any("Rehabilitation" in d["zitat"] for d in reha["dokument"])
    for d in reha["dokument"]:
        assert d["zitat"] in brieftext
        assert f"In Ihrem Dokument steht: „{d['zitat']}“" in a.text
        assert d["quelle"]["art"] == "dokument" and d["quelle"]["fundstelle"] == f"S. {d['seite']}"
        assert d["quelle"] in reha["quellen"]
    en = lotse.einstellungen(s, sprache="en")
    assert f"Your document states: “{reha['dokument'][0]['zitat']}”" in en.text

    # Angaben aus dem Dokument werden nicht noch einmal erfragt
    aus_dokument = {k for k, h in s.herkunft.items() if h["art"] == "dokument"}
    _, gestellt = _durchlauf(lotse, s, lotse.einstellungen(s, sprache="de"))
    assert aus_dokument.isdisjoint(gestellt)


def test_unlesbares_dokument_wird_gemeldet(lotse):
    s = lotse.neue_sitzung()
    a = lotse.dokument(s, "kaputt.pdf", b"%PDF-1.7 kaputt")
    assert "nicht lesen" in a.text and a.buendel == [] and s.dokumente == []


@pytest.mark.parametrize("frage", ["Wie hoch ist das Krankengeld?", "Wie hoch ist das Pflegegeld in Stufe 3?",
                                   "Muss das Medikament mit der PZN 1234567 bewilligt werden?"])
def test_wissensfrage_ohne_sv_box_daten_meldet_fehlende_quellen(lotse, monkeypatch, frage):
    def fehlt():
        raise FileNotFoundError("SV-Box-Quelldaten fehlen")
    monkeypatch.setattr(wissen, "wissensbasis", fehlt)
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, frage)
    assert "SV-Box-Daten" in a.text and a.quellen == []


@pytest.mark.daten
def test_entlassungsbefund_alle_empfehlungen_woertlich_mit_seite(lotse):
    pfad = config.datei("Befunde/Entlassungsbefund.pdf")
    dok = dokument.lade_dokument(pfad.name, pfad.read_bytes())
    erwartet = {e.thema for e in dokument.empfehlungen(dok)}
    s = lotse.neue_sitzung()
    a = lotse.dokument(s, pfad.name, pfad.read_bytes())
    mit_zitat = {b["leistung_id"] for b in a.buendel if b["dokument"]}
    assert len(mit_zitat) >= 5 and mit_zitat == erwartet
    for b in a.buendel:
        for d in b["dokument"]:
            assert d["zitat"] in " ".join(dok.seiten[d["seite"] - 1].split())


# ---------------------------------------------------------------- Wissensfragen

@pytest.mark.daten
def test_pflegegeld_2026_aus_anpassungsverordnung(lotse):
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, "Wie hoch ist das Pflegegeld in Stufe 3?")
    assert "592,60 €" in a.text and "451,80" not in a.text
    assert a.quellen[0]["fundstelle"] == "BGBl. II Nr. 263/2025"
    assert "[1]" in a.text
    assert "€592.60" in lotse.einstellungen(s, sprache="en").text


@pytest.mark.daten
def test_erstattungsstatus_nach_pzn_ohne_medizinische_bewertung(lotse):
    eintrag = wissen.wissensbasis().ekodex("a", k=1)[0]
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, f"Muss das Medikament mit der PZN {eintrag.pzn} bewilligt werden?")
    assert a.grenze is None
    assert eintrag.pzn in a.text and eintrag.name in a.text
    assert eintrag.quelle.to_dict() in a.quellen
    assert a.buendel == []


@pytest.mark.daten
def test_wissensfrage_antwortet_mit_zitierten_quellen(lotse):
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, "Was regelt das ASVG zur Rezeptgebühr?")
    assert a.quellen and "[1]" in a.text
    assert a.quellen[0]["titel"] in a.text


# ---------------------------------------------------------------- Sprachmodell-Prüfung (ohne Netz)

FAKTEN = [{"n": 1, "text": "in Stufe 3 statt 577,00 € mit 592,60 €", "quelle": "BGBl. II Nr. 263/2025"}]


def test_ki_ausgabe_mit_belegen_ist_gueltig():
    assert llm.pruefe_ausgabe("Das Pflegegeld der Stufe 3 beträgt 2026 592,60 € [1].", FAKTEN, "Pflegegeld 2026?") == []


def test_ki_ausgabe_ohne_beleg_oder_mit_erfundener_zahl_wird_verworfen():
    assert "keine Quellenangabe" in llm.pruefe_ausgabe("Das Pflegegeld beträgt 592,60 €.", FAKTEN)
    assert "unbekannte Quellennummer" in llm.pruefe_ausgabe("Es sind 592,60 € [2].", FAKTEN)
    assert "unbelegte Zahl" in llm.pruefe_ausgabe("Es sind 650,00 € [1].", FAKTEN)


def test_ohne_schluessel_bleibt_der_lotse_regelbasiert(lotse):
    assert not llm.aktiv()
    assert llm.verstehe(SAETZE["pflege"], "de") == {"szenarien": [], "slots": {}}
    assert llm.formuliere(FAKTEN, "de", "einfach") == ""
    s = lotse.neue_sitzung()
    assert lotse.nachricht(s, SAETZE["pflege"]).modus == "regelbasiert"
