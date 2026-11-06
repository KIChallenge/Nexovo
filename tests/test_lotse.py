"""Engine-Tests: Szenarien, Rückfragen, Grenze, Sprache/Stil, Fallakte, Dokument, Wissensfragen, Termine, Status."""

import json
from datetime import date
from io import BytesIO

import pytest
from pypdf import PdfReader

from lotse import config, dokument, katalog, llm, suche, texte, wissen
from lotse.fallakte import Fallakte, Termin, ics
from lotse.lotse import Lotse, _eko_eintraege, _eko_zusammenfassung, _termin_datum, _uhrzeit, extrahiere, normalisiere
from lotse.slots import SLOTS

SAETZE = {
    "pflege": "Meine Mutter ist chronisch krank und kommt allein nicht mehr zurecht",
    "gesundheit": "Ich möchte etwas für meine Gesundheit tun",
    "entlassung": "Ich habe einen Befund/Entlassungsbrief bekommen – was muss ich jetzt erledigen?",
    "kind": "Ich habe ein Kind und möchte wissen, welche Angebote es gibt",
    "unterstuetzung": texte.BEISPIELE["unterstuetzung"]["de"],
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


@pytest.mark.befunde
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


# ---------------------------------------------------------------- Relevanz der Wissensantworten (P1)

def test_abdeckung_misst_anteil_der_fragewoerter():
    a = suche.Analysator({"pflegegeld": 5, "pflege": 5, "geld": 5, "höhe": 5, "antrag": 5, "stufe": 5})
    idx = suche.Index(a)
    idx.baue([("Höhe des Pflegegeldes", "Das Pflegegeld beträgt in Stufe 1 …")] * 3
             + [("Antrag", "Den Antrag stellen Sie bei der PVA.")] * 3)
    assert suche.abdeckung(idx, "Wie hoch ist das Pflegegeld?", "Höhe des Pflegegeldes: in Stufe 1 …") == 1.0
    assert suche.abdeckung(idx, "Wie hoch ist das Pflegegeld?", "Den Antrag stellen Sie bei der PVA.") == 0.0
    # Wörter, die im Korpus fehlen, deuten auf ein fremdes Thema und senken die Abdeckung
    assert suche.abdeckung(idx, "Pflegegeld Apfelstrudel", "Das Pflegegeld beträgt …") < 0.5
    # Personenbezug zählt nicht
    assert suche.abdeckung(idx, "Pflegegeld für meine Mutter", "Das Pflegegeld beträgt …") == 1.0


@pytest.mark.daten
def test_20_buergerfragen_bekommen_relevante_belege():
    from test_wissen import FRAGEN, _trifft
    mit_soll = 0
    for _, frage, soll in FRAGEN:
        treffer = Lotse._relevante(frage)
        assert treffer, frage
        mit_soll += any(_trifft(t, s) for t in treffer for s in soll)
    assert mit_soll >= 18


@pytest.mark.daten
@pytest.mark.parametrize("frage", [
    "Mama schafft's daheim nimma allein", "Ich kann die Miete nicht zahlen", "Wo ist der nächste Bahnhof?",
    "Rezept für Apfelstrudel", "Wie geht es dir?",
])
def test_themenfremde_frage_zitiert_keine_unpassenden_normen(lotse, frage):
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, frage)
    if a.szenarien:
        # als Anliegen erkannt: Belege nur aus den gezeigten Leistungen
        buendel_quellen = [q for b in a.buendel for q in b["quellen"]]
        assert all(q in buendel_quellen for q in a.quellen)
    else:
        assert a.quellen == [] and "nichts Belastbares" in a.text
        assert all(texte.SZENARIO_LABEL[x]["de"] in a.text for x in katalog.SZENARIEN)
        assert "Arzttermin" in a.text


def test_arzttermin_wird_nicht_als_wissensfrage_beantwortet(lotse):
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, "Ich möchte einen Arzttermin.")
    assert a.quellen == [] and a.rueckfrage["slot"] == "termin.anlass"


# ---------------------------------------------------------------- Termine (P2)

def _termin_durchlauf(lotse, s, anlass="Vorsorge", ort="1100 Wien", zeit="vormittags"):
    a = lotse.nachricht(s, "Ich möchte einen Arzttermin.")
    assert a.rueckfrage["slot"] == "termin.anlass"
    assert s.sprache != "de" or "Buchen kann ich ihn nicht" in a.text
    a = lotse.nachricht(s, anlass)
    assert a.rueckfrage["slot"] == "termin.ort"
    a = lotse.nachricht(s, ort)
    assert a.rueckfrage["slot"] == "termin.zeit"
    assert [o["wert"] for o in a.rueckfrage["optionen"]] == list(SLOTS["termin.zeit"].optionen)
    return lotse.nachricht(s, zeit)


def test_terminvorbereitung_wie_im_use_case(lotse):
    s = lotse.neue_sitzung()
    a = _termin_durchlauf(lotse, s)
    assert a.rueckfrage is None and len(a.termine) == 1
    tm = a.termine[0]
    assert (tm["anlass"], tm["ort"], tm["zeit"], tm["status"]) == ("vorsorge", "1100 Wien", "vormittags", "vorbereitet")
    assert s.werte["person.bundesland"] == "Wien"  # aus der Ortsangabe
    info = katalog.termin_info("vorsorge", "Wien")
    assert tm["wo"] == info.wo["de"] and tm["hinweise"] == [h["de"] for h in info.hinweise]
    assert [x["url"] for x in tm["suche"]] == [x["url"] for x in info.suche]
    assert all(not x["regionen"] or "Wien" in x["regionen"] for x in info.suche)
    assert tm["quellen"] and all(q["titel"] and (q["fundstelle"] or q["url"]) for q in tm["quellen"])
    assert all(x["beleg"] in ("lokal", "extern") for x in tm["suche"])
    for teil in ("Vorsorgeuntersuchung", "vormittags", "e-card"):
        assert teil in tm["anfrage_text"]
    assert tm["ics_url"] == "" and tm["datum"] == ""
    assert "Ihr Terminauftrag ist fertig" in a.text and "Termin am 12.11.2026" in a.text
    assert "gebucht habe" not in a.text and a.quellen
    eintrag = next(e for e in a.fallakte["eintraege"] if e["leistung_id"] == tm["id"])
    assert eintrag["art"] == "termin" and eintrag["termin_id"] == tm["id"]
    assert [x["schritt_id"] for x in eintrag["schritte"]] == ["anfragen", "eintragen", "wahrnehmen"]
    en = lotse.einstellungen(s, sprache="en")
    assert "Mornings suit me best" in en.termine[0]["anfrage_text"] and en.termine[0]["zeit"] == "mornings"


def test_gemeldeter_termin_wird_eingetragen_mit_kalenderdatei(lotse):
    s = lotse.neue_sitzung()
    _termin_durchlauf(lotse, s)
    a = lotse.nachricht(s, "Ich habe jetzt einen Termin am 12.11.2026 um 10:30")
    tm = a.termine[0]
    assert (tm["status"], tm["datum"], tm["uhrzeit"]) == ("vereinbart", "12.11.2026", "10:30")
    assert tm["ics_url"] == f"/api/sitzung/{s.id}/termin/{tm['id']}.ics"
    assert "ich habe ihn nur notiert" in a.text
    assert s.fallakte.schritt(f"{tm['id']}.anfragen").status == "erledigt"
    assert a.status_uebersicht["erledigt"] == 2
    kalender = lotse.termin_ics(s, tm["id"])
    zeilen = kalender.split("\r\n")
    assert zeilen[0] == "BEGIN:VCALENDAR" and zeilen[-2] == "END:VCALENDAR" and zeilen[-1] == ""
    for erwartet in ("VERSION:2.0", "TZID:Europe/Vienna", "DTSTART;TZID=Europe/Vienna:20261112T103000",
                     "SUMMARY:Termin: Vorsorgeuntersuchung", "LOCATION:1100 Wien", "BEGIN:VEVENT", "END:VEVENT"):
        assert erwartet in zeilen, erwartet
    assert all(len(z.encode()) <= 75 for z in zeilen)
    assert any(z.startswith("UID:") and z.endswith("@sv-ki-lotse") for z in zeilen)
    assert any(z.startswith("DTSTAMP:") and z.endswith("Z") for z in zeilen)
    # keine Angaben, die die Person nicht selbst gemacht hat (z. B. Name, SVNR)
    assert "person." not in kalender
    a = lotse.nachricht(s, "Ich habe den Termin wahrgenommen")
    assert a.termine[0]["status"] == "erledigt"


def test_ics_ganztaegig_und_gefaltet():
    tm = Termin(id="termin_1", anlass="zahn", ort="Ordination " + "sehr lange Adresse, " * 6, datum="03.12.2026")
    kalender = ics(tm, "Termin: Zahnarzt", "Zeile 1\nZeile 2; mit, Zeichen")
    zeilen = kalender.split("\r\n")
    assert "DTSTART;VALUE=DATE:20261203" in zeilen and "BEGIN:VTIMEZONE" not in zeilen
    assert all(len(z.encode()) <= 75 for z in zeilen)
    entfaltet = kalender.replace("\r\n ", "")
    assert "DESCRIPTION:Zeile 1\\nZeile 2\\; mit\\, Zeichen" in entfaltet
    assert "LOCATION:Ordination sehr lange Adresse\\, " in entfaltet
    with pytest.raises(ValueError):
        ics(Termin(id="termin_2", anlass="zahn"), "x", "y")


def test_termin_ohne_vorbereitung_gemeldet(lotse):
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, "Ich habe einen Termin beim Zahnarzt am 3.12.2026")
    tm = a.termine[0]
    assert (tm["anlass"], tm["status"], tm["uhrzeit"]) == ("zahn", "vereinbart", "")
    assert "DTSTART;VALUE=DATE:20261203" in lotse.termin_ics(s, tm["id"])


def test_termin_aus_buendel_fragt_nur_naehe_und_zeit(lotse):
    l = next(x for x in katalog.alle() if x.termin_anlass)
    s = lotse.neue_sitzung()
    a = lotse.termin_starten(s, leistung=l.id)
    assert a.rueckfrage["slot"] == "termin.ort"
    lotse.nachricht(s, "egal")
    a = lotse.nachricht(s, "Egal")
    tm = a.termine[0]
    assert tm["anlass"] == l.termin_anlass and tm["anlass_label"] == l.titel["de"] and tm["ort"] == ""
    assert l.titel["de"] in tm["anfrage_text"]
    with pytest.raises(ValueError):
        lotse.termin_starten(s, anlass="friseur")
    with pytest.raises(KeyError):
        lotse.termin_starten(s, leistung="gibt_es_nicht")


def test_termin_bei_beschwerden_nennt_1450_ohne_beurteilung(lotse):
    s = lotse.neue_sitzung()
    a = _termin_durchlauf(lotse, s, anlass="Beschwerden", ort="egal", zeit="egal")
    hinweis = katalog.termin_info("beschwerden").beschwerden_hinweis["de"]
    assert hinweis and "1450" in hinweis
    assert a.termine[0]["hinweise"][0] == hinweis and hinweis in a.text
    assert a.grenze is None


def test_termin_aktualisieren_prueft_eingaben(lotse):
    s = lotse.neue_sitzung()
    _termin_durchlauf(lotse, s)
    with pytest.raises(ValueError):
        lotse.termin_aktualisieren(s, "termin_1", datum="31.02.2026")
    with pytest.raises(ValueError):
        lotse.termin_aktualisieren(s, "termin_1", uhrzeit="10:30")  # ohne Datum
    with pytest.raises(ValueError):
        lotse.termin_aktualisieren(s, "termin_1", status="gebucht")
    with pytest.raises(KeyError):
        lotse.termin_aktualisieren(s, "termin_9", datum="12.11.2026")
    a = lotse.termin_aktualisieren(s, "termin_1", datum="2026-11-12", uhrzeit="9:05")
    assert (a.termine[0]["datum"], a.termine[0]["uhrzeit"], a.termine[0]["status"]) == ("12.11.2026", "09:05",
                                                                                         "vereinbart")


def test_neues_anliegen_bricht_terminvorbereitung_ab(lotse):
    s = lotse.neue_sitzung()
    lotse.nachricht(s, "Ich möchte einen Arzttermin.")
    a = lotse.nachricht(s, SAETZE["pflege"])
    assert "pflege" in [x["id"] for x in a.szenarien] and s.termin_entwurf is None
    assert a.rueckfrage is None or not a.rueckfrage["slot"].startswith("termin.")


@pytest.mark.parametrize("text,erwartet", [
    ("um 10:30", "10:30"), ("10.30 Uhr", "10:30"), ("um 9", "09:00"), ("at 3 pm", "15:00"), ("14 Uhr", "14:00"),
    ("am 12.11.2026", ""), ("Termin am 12.11.2026 um 8:15", "08:15"),
])
def test_uhrzeit_aus_freiem_text(text, erwartet):
    assert _uhrzeit(text) == erwartet


def test_termindatum_ohne_jahr_ist_naechster_solcher_tag():
    assert _termin_datum("am 12.11.", heute=date(2026, 11, 6)) == "12.11.2026"
    assert _termin_datum("am 3.1.", heute=date(2026, 11, 6)) == "03.01.2027"
    assert _termin_datum("am 12.11.2026") == "12.11.2026"


# ---------------------------------------------------------------- Weiterverfolgen (P9)

def test_statusfrage_antwortet_aus_der_fallakte(lotse):
    s = lotse.neue_sitzung()
    leer = lotse.nachricht(s, "Was ist noch offen?")
    assert "Fallakte ist noch leer" in leer.text and leer.status_uebersicht == {"erledigt": 0, "offen": 0,
                                                                             "naechster": ""}
    lotse.nachricht(s, SAETZE["pflege"])
    lotse.setze_status(s, "pflegegeld.antrag_ausfuellen", "erledigt")
    szenarien = list(s.szenarien)
    a = lotse.nachricht(s, "Wie weit ist mein Pflegegeld-Antrag?")
    assert s.szenarien == szenarien and a.grenze is None
    titel = katalog.leistung("pflegegeld").titel["de"]
    assert "Stand Ihrer Fallakte" in a.text and f"• {titel}:" in a.text and "nächster Schritt" in a.text
    assert a.text.count("• ") == 1  # nur die genannte Leistung
    # gezählt werden nur primäre Leistungen, begonnene Leistungen und Termine
    wichtig = [e for e in s.fallakte.eintraege.values()
               if e.leistung_id in s.leistungen[:3] or e.art == "termin" or e.hat_fortschritt()]
    assert len(wichtig) < len(s.fallakte.eintraege)
    schritte = [x for e in wichtig for x in e.schritte]
    assert a.status_uebersicht["erledigt"] == sum(x.status == "erledigt" for x in schritte) >= 1
    assert a.status_uebersicht["offen"] == len(schritte) - a.status_uebersicht["erledigt"]
    assert a.status_uebersicht["naechster"]
    alle = lotse.nachricht(s, "Was ist noch offen?")
    assert "wichtigsten Anliegen" in alle.text and alle.text.count("• ") == len(wichtig)
    assert f"Weitere {len(s.fallakte.eintraege) - len(wichtig)} Angebote" in alle.text
    # eine begonnene Leistung außerhalb der wichtigsten zählt mit
    weitere = next(lid for lid in s.leistungen if s.fallakte.eintraege[lid] not in wichtig)
    erster = s.fallakte.eintraege[weitere].schritte[0].id
    vorher = lotse.aktuell(s).status_uebersicht
    nachher = lotse.setze_status(s, erster, "erledigt").status_uebersicht
    assert nachher["erledigt"] == vorher["erledigt"] + 1
    assert nachher["offen"] == vorher["offen"] + len(s.fallakte.eintraege[weitere].schritte) - 1
    en = lotse.einstellungen(s, sprache="en")
    assert "Your case file" in lotse.nachricht(s, "what is still open?").text and en.sprache == "en"


# ---------------------------------------------------------------- Kürzen und Fokus (P18)

def test_fahrtkosten_zuerst_mit_naechstem_schritt(lotse):
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, "Wer zahlt mir die Fahrt zur Bestrahlung?")
    assert a.buendel[0]["leistung_id"] == "fahrtkosten"
    assert [b["primaer"] for b in a.buendel] == [i < 3 for i in range(len(a.buendel))]
    assert a.weitere_anzahl == max(0, len(a.buendel) - 3)
    fk = katalog.leistung("fahrtkosten")
    erster = s.fallakte.naechster_schritt("fahrtkosten")
    assert f"Nächster Schritt: {fk.titel['de']} – {erster.text['de'].rstrip('.')}" in a.text
    assert all(b["titel"] in a.text for b in a.buendel[:3])
    if a.weitere_anzahl:
        assert f"Weitere {a.weitere_anzahl} Angebote" in a.text


def test_vorsorge_bei_familiaerer_vorbelastung_ohne_risikoaussage(lotse):
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, "Mein Vater hatte Darmkrebs. Welche Vorsorgeuntersuchungen gibt es?")
    assert a.grenze is None and a.buendel[0]["leistung_id"] == "vorsorgeuntersuchung"
    assert "kein persönliches Risiko" in a.text
    vu = katalog.leistung("vorsorgeuntersuchung")
    if vu.nutzen["de"]:
        assert vu.nutzen["de"] in a.text and vu.nutzen_quelle.to_dict() in a.quellen


# ---------------------------------------------------------------- Neue Katalogdaten im Bündel

def test_buendel_traegt_nutzen_einrichtungen_und_regionales(lotse):
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, "Meine Mutter lebt in Wien und kommt allein nicht mehr zurecht")
    for b in a.buendel:
        l = katalog.leistung(b["leistung_id"])
        assert {"primaer", "nutzen", "nutzen_quelle", "einrichtungen", "regional", "termin_anlass"} <= set(b)
        assert bool(b["nutzen"]) == (b["nutzen_quelle"] is not None)
        assert b["termin_anlass"] == l.termin_anlass
        assert len(b["einrichtungen"]) == len(l.einrichtungen_fuer("Wien"))
        for e in b["einrichtungen"]:
            assert e["beleg"] == ("extern" if e["quelle"]["art"] == "extern" else "lokal")
            assert not e["regionen"] or "Wien" in e["regionen"]
            assert e["quelle"] in b["quellen"]
        if "Wien" in l.regional:
            assert b["regional"]["bundesland"] == "Wien" and b["regional"]["stelle"] == l.regional["Wien"]["stelle"]["de"]
        else:
            assert b["regional"] is None
    json.dumps(a.to_dict())


def _formular_leistung():
    return next(l for l in katalog.alle() if l.formular and l.formular_regionen and not l.regionen
                and "pflege" in l.szenarien)


@pytest.mark.parametrize("satz,sichtbar,hinweis", [
    ("Meine Mutter lebt in Tirol und kommt allein nicht mehr zurecht", False, False),
    ("Meine Mutter lebt in Wien und kommt allein nicht mehr zurecht", True, False),
    (SAETZE["pflege"], True, True),
])
def test_regionales_formular_nur_wo_es_gilt(lotse, satz, sichtbar, hinweis):
    l = _formular_leistung()
    s = lotse.neue_sitzung()
    b = next(x for x in lotse.nachricht(s, satz).buendel if x["leistung_id"] == l.id)
    assert (b["formular"] is not None) == sichtbar
    if sichtbar:
        assert bool(b["formular"]["region_hinweis"]) == hinweis and b["formular"]["regionen"] == l.formular_regionen
    else:
        assert b["fehlende_angaben"] == []


# ---------------------------------------------------------------- Fotos, Impfungen, Medikamente

@pytest.mark.parametrize("name,inhalt,erwartet", [
    ("brief.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 64, "KI-Modus"),
    ("brief.heic", b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64, "Bildformat"),
])
def test_foto_ohne_ki_wird_klar_abgelehnt(lotse, name, inhalt, erwartet):
    s = lotse.neue_sitzung()
    a = lotse.dokument(s, name, inhalt)
    assert erwartet in a.text and s.dokumente == [] and a.modus == "regelbasiert"


def test_impfeintraege_werden_nur_aufgelistet(lotse):
    pfad = config.REPO_ROOT / "examples" / "impfpass_synthetisch.txt"
    dok = dokument.lade_dokument(pfad.name, pfad.read_bytes())
    erwartet = dokument.impfeintraege(dok)
    assert erwartet
    s = lotse.neue_sitzung()
    a = lotse.dokument(s, pfad.name, pfad.read_bytes())
    assert [(i["impfung"], i["datum"], i["seite"]) for i in a.impfungen] == [(e.impfung, e.datum, e.seite)
                                                                            for e in erwartet]
    assert all(i["dokument"] == pfad.name for i in a.impfungen)
    assert "Laut Ihrem Impfpass dokumentiert" in a.text and "fällig" not in a.text
    assert "impfungen" in [b["leistung_id"] for b in a.buendel]
    assert a.dokumente == [{"name": pfad.name, "seiten": len(dok.seiten), "transkribiert": False}]


@pytest.mark.daten
def test_medikamente_aus_brief_werten_alle_eko_eintraege_aus(lotse):
    s = lotse.neue_sitzung()
    a = lotse.dokument(s, BRIEF.name, BRIEF.read_bytes())
    assert a.medikamente and "keine Empfehlung" in a.text
    gefunden = [m for m in a.medikamente if m["eko"]]
    assert gefunden
    for m in gefunden:
        eko = m["eko"]
        suchname, eintraege = _eko_eintraege(m["name_dokument"])
        assert eko["anzahl"] == len(eintraege) == sum(v["anzahl"] for v in eko["varianten"]) >= 1
        assert eko["suchname"] == suchname
        assert all(e.name.casefold().startswith(suchname.casefold()) for e in eintraege)
        assert eko["einheitlich"] == (len(eko["varianten"]) == 1)
        if eko["einheitlich"]:
            assert eko["box"] in ("gruen", "gelb") and eko["erklaerung"].startswith(("Alle", "Ein Eintrag"))
            assert f"alle {eko['anzahl']} Einträge" in a.text or eko["anzahl"] == 1
        else:
            assert "je nach Stärke bzw. Packung" in eko["erklaerung"] and "je nach Stärke bzw. Packung" in a.text
        assert eko["quellen"][0] in a.quellen
    assert _eko_eintraege("Gibtsnichtxyzpraeparat") == ("", [])


def _eko(pzn: str, name: str, box: str, kennzeichen: list[str]):
    from lotse.ekodex import EkoEintrag
    from lotse.models import Quelle
    q = Quelle(art="ekodex", titel=f"EKO – {name}", fundstelle=f"medikament.txt, PZN {pzn}", datei="x", zitat=name)
    return EkoEintrag(pzn=pzn, name=name, box=box, kennzeichen=kennzeichen, packung="", regeltext="", indtext="",
                      quelle=q)


def test_eko_zusammenfassung_einheitlich_und_varianten():
    gleich = [_eko("1000001", "Testin 10 mg Tabl.", "gruen", []), _eko("1000002", "Testin 20 mg Tabl.", "gruen", [])]
    z = _eko_zusammenfassung("Testin", gleich, "de")
    assert (z["anzahl"], z["einheitlich"], z["box"]) == (2, True, "gruen")
    assert z["erklaerung"].startswith("Alle 2 Einträge zu „Testin“ im Erstattungskodex: Grüne Box (z. B. Testin 10 mg")
    gemischt = gleich + [_eko("1000003", "Testin 40 mg Tabl.", "gelb", ["RE1"])]
    z = _eko_zusammenfassung("Testin", gemischt, "de", ausfuehrlich=True)
    assert (z["anzahl"], z["einheitlich"], z["box"], z["kennzeichen"]) == (3, False, "", [])
    assert [(v["box"], v["kennzeichen"], v["anzahl"]) for v in z["varianten"]] == [("gruen", [], 2), ("gelb", ["RE1"], 1)]
    assert "je nach Stärke bzw. Packung" in z["erklaerung"] and "Kennzeichen RE1" in z["erklaerung"]
    assert z["varianten"][1]["beispiel"] == {"name": "Testin 40 mg Tabl.", "pzn": "1000003"}
    assert z["quellen"][0]["fundstelle"] == "medikament.txt, PZN 1000001"


def test_kontrolltermin_aus_brief_bietet_terminvorbereitung_an(lotse):
    s = lotse.neue_sitzung()
    a = lotse.dokument(s, BRIEF.name, BRIEF.read_bytes())
    b = next(x for x in a.buendel if x["leistung_id"] == "kontrolltermine")
    assert b["dokument"] and b["termin_anlass"] == "kontrolle"
    assert texte.t("termin_angebot", "de") in a.text
    a = lotse.nachricht(s, "Termin vorbereiten")
    assert a.rueckfrage["slot"] in ("termin.anlass", "termin.ort")


# ---------------------------------------------------------------- Weitere Sprachen (P10)

def test_weitere_sprachen_nur_im_ki_modus(lotse):
    s = lotse.neue_sitzung()
    for sprache in ("tr", "ar"):
        with pytest.raises(ValueError):
            lotse.einstellungen(s, sprache=sprache)
        with pytest.raises(ValueError):
            lotse.neue_sitzung(sprache)
    assert texte.richtung("ar") == "rtl" and texte.richtung("tr") == "ltr"
    assert llm.uebersetze(["Hello [1]", ""], "tr") == [None, ""]
    with pytest.raises(ValueError):
        llm.uebersetze(["Hallo"], "de")


@pytest.mark.parametrize("quelle,ziel,ok", [
    ("Level 3: €592.60 [1]", "Seviye 3: €592.60 [1]", True),
    ("Level 3: €592.60 [1]", "Seviye 3: €592.60 [2]", False),
    ("Level 3: €592.60 [1]", "Seviye ٣: €592.60 [1]", False),
    ("Level 3: €592.60 [1]", "Seviye: €592.60 [1]", False),
    ("Your document states: ⟦0⟧ (p. 7)", "Belgenizde: ⟦0⟧ (s. 7)", True),
    ("Your document states: ⟦0⟧ (p. 7)", "Belgenizde (s. 7)", False),
    ("More services ({n})", "Diğer hizmetler ({n})", True),
    ("More services ({n})", "Diğer hizmetler", False),
])
def test_uebersetzung_wird_geprueft(quelle, ziel, ok):
    assert llm.pruefe_uebersetzung(quelle, ziel) is ok


def _uebersetzer(praefix: str, ziffern_aendern: bool = False):
    """Deterministischer Ersatz für das Modell: nur Übersetzungsaufrufe werden beantwortet."""
    def chat(system, nutzer, max_tokens, json_modus=False, timeout=None):
        if not system.startswith("Du übersetzt"):
            return ""
        texte_ = json.loads(nutzer)["texte"]
        return json.dumps({"texte": [f"{praefix} {t.replace('1', '7') if ziffern_aendern else t}" for t in texte_]})
    return chat


def test_weitere_sprache_uebersetzt_text_und_buendel_zitate_bleiben(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "aktiv", lambda: True)
    monkeypatch.setattr(llm, "_chat", _uebersetzer("[tr]"))
    monkeypatch.setattr(llm, "_cache", {})
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    lotse = Lotse()
    s = lotse.neue_sitzung("tr")
    a = lotse.dokument(s, BRIEF.name, BRIEF.read_bytes())
    assert a.sprache == "tr" and a.richtung == "ltr" and a.modus == "ki"
    assert a.text.startswith("[tr] ")
    reha = next(b for b in a.buendel if b["leistung_id"] == "rehabilitation")
    assert reha["titel"] == f"[tr] {katalog.leistung('rehabilitation').titel['en']}"
    # wörtliche Zitate aus dem Dokument bleiben im Original
    assert f"“{reha['dokument'][0]['zitat']}”" in reha["dokument"][0]["text"]
    assert all(x["text"].startswith("[tr] ") for e in a.fallakte["eintraege"] for x in e["schritte"])
    assert (tmp_path / "uebersetzungen" / "tr.json").is_file()
    # zweites Rendern kommt ohne Modell aus (Cache)
    monkeypatch.setattr(llm, "_chat", lambda *a, **k: "")
    assert lotse.aktuell(s).buendel[0]["titel"].startswith("[tr] ")
    ar = lotse.einstellungen(s, sprache="ar")
    assert ar.richtung == "rtl"


def test_weitere_sprache_faellt_bei_veraenderten_zahlen_auf_englisch_zurueck(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "aktiv", lambda: True)
    monkeypatch.setattr(llm, "_chat", _uebersetzer("[uk]", ziffern_aendern=True))
    monkeypatch.setattr(llm, "_cache", {})
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    lotse = Lotse()
    s = lotse.neue_sitzung("uk")
    _termin_durchlauf(lotse, s)
    a = lotse.nachricht(s, "Termin am 12.11.2026 um 10:30")
    assert a.text.startswith(texte.t("uebersetzung_fehlt", "en"))
    assert "12.11.2026" in a.text and "[uk]" not in a.text.split("\n\n", 1)[1]
    assert a.termine[0]["anfrage_text"].startswith("Guten Tag")  # für die Ordination auf Deutsch


# ---------------------------------------------------------------- Folgeauftrag (E2E-Befunde)

def test_formular_unterlagen_nur_wo_das_formular_gilt(lotse):
    l = _formular_leistung()
    zum_formular = {u["de"] for u in l.unterlagen_formular}
    assert zum_formular
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, SAETZE["pflege"])
    b = next(x for x in a.buendel if x["leistung_id"] == l.id)
    mit_hinweis = [u for u in b["unterlagen"] if u["text"] in zum_formular]
    assert mit_hinweis and all(u["region_hinweis"] for u in mit_hinweis)
    allgemein = {u["de"] for u in l.unterlagen}
    assert all(not u["region_hinweis"] for u in b["unterlagen"] if u["text"] in allgemein)
    a = lotse.nachricht(s, "Steiermark")
    b = next(x for x in a.buendel if x["leistung_id"] == l.id)
    assert b["formular"] is None and {u["text"] for u in b["unterlagen"]} == allgemein


def test_stelle_kontakt_folgt_der_aufgeloesten_stelle(lotse):
    l = next(x for x in katalog.alle() if "versicherung.krankenversicherung" in x.stelle_nach
             and x.kontakt_fuer({"versicherung.krankenversicherung": "SVS"}) != x.stelle.get("kontakt", ""))
    s = lotse.neue_sitzung()
    s.werte["versicherung.krankenversicherung"] = "SVS"
    b = lotse._buendel_eintrag(s, l.id)
    assert b["stelle"]["kontakt"] == l.kontakt_fuer(s.werte) and "svs" in b["stelle"]["kontakt"].casefold()


@pytest.mark.parametrize("text,land,stadt", [
    ("Meine Mutter lebt in Graz und kommt allein nicht mehr zurecht", "Steiermark", "Graz"),
    ("Mein Vater wohnt in St. Pölten und braucht Pflege", "Niederösterreich", "St. Pölten"),
])
def test_stadt_ergibt_bundesland_aus_ortsangabe(lotse, text, land, stadt):
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, text)
    assert s.werte["person.bundesland"] == land and s.herkunft["person.bundesland"] == {"art": "ort", "ort": stadt}
    angabe = next(x for x in a.angaben if x["slot"] == "person.bundesland")
    assert angabe["herkunft"] == f"aus Ihrer Ortsangabe {stadt}"
    assert a.rueckfrage is None or a.rueckfrage["slot"] != "person.bundesland"


def test_stadt_als_terminort_und_als_antwort_auf_die_bundeslandfrage(lotse):
    s = lotse.neue_sitzung()
    a = _termin_durchlauf(lotse, s, ort="Graz")
    assert s.werte["person.bundesland"] == "Steiermark"
    assert [x["url"] for x in a.termine[0]["suche"]] == [x["url"] for x in katalog.termin_info("vorsorge", "Steiermark").suche]
    s = lotse.neue_sitzung()
    assert lotse.nachricht(s, SAETZE["pflege"]).rueckfrage["slot"] == "person.bundesland"
    a = lotse.nachricht(s, "Innsbruck")
    assert s.werte["person.bundesland"] == "Tirol" and (a.rueckfrage is None or a.rueckfrage["slot"] != "person.bundesland")
    # bekanntes Bundesland wird nicht überschrieben
    lotse.nachricht(s, "Ich war in Graz beim Arzt, wer zahlt die Fahrt?")
    assert s.werte["person.bundesland"] == "Tirol"


@pytest.mark.daten
@pytest.mark.parametrize("frage", ["Wer gewinnt die Wahl?", "Ich will Urlaub machen", "Wie wird das Wetter?"])
def test_themenfremd_trotz_wortgleichheit_keine_belege(frage):
    assert Lotse._relevante(frage) == []


def test_vergleichsfrage_antwortet_mit_kuratierten_leistungen(lotse):
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, "Was ist der Unterschied zwischen Kur und Reha?")
    assert a.szenarien == [] and a.buendel == [] and a.grenze is None
    for lid in ("kur", "rehabilitation"):
        l = katalog.leistung(lid)
        assert f"• {l.titel['de']}: {l.kurz['de']}" in a.text
        assert l.quellen[0].to_dict() in a.quellen
        assert l.details["de"] not in a.text
    ausf = lotse.einstellungen(s, stil="ausfuehrlich")
    assert katalog.leistung("kur").details["de"] in ausf.text


def test_definitionsfrage_zu_einer_leistung(lotse):
    s = lotse.neue_sitzung()
    a = lotse.nachricht(s, "Was ist die Ausgleichszulage?")
    l = katalog.leistung("ausgleichszulage")
    assert a.szenarien == [] and f"• {l.titel['de']}: {l.kurz['de']}" in a.text
    assert l.quellen[0].to_dict() in a.quellen
    # Pflegegeldbetrag bleibt bei der genaueren Sonderantwort
    assert "Dazu steht in meinem Leistungskatalog" not in lotse.nachricht(s, "Was ist die Höhe des Pflegegeldes?").text


def test_weitere_sprache_titel_und_angaben_wie_auf_der_karte(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "aktiv", lambda: True)
    monkeypatch.setattr(llm, "_chat", _uebersetzer("[ar]"))
    monkeypatch.setattr(llm, "_cache", {})
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    lotse = Lotse()
    s = lotse.neue_sitzung("ar")
    a = lotse.nachricht(s, "Meine Mutter kommt allein nicht mehr zurecht")
    assert a.richtung == "rtl"
    for b in a.buendel[:3]:
        assert b["titel"].startswith("[ar] ") and b["titel"] in a.text
    englisch = [katalog.leistung(b["leistung_id"]).titel["en"] for b in a.buendel[:3]]
    assert not any(f" {t}" in a.text.replace(f"[ar] {t}", "") for t in englisch)
    fuer_wen = next(x for x in a.angaben if x["slot"] == "anliegen.fuer_wen")
    assert fuer_wen["label"].startswith("[ar] ") and fuer_wen["wert"].startswith("[ar] ")
    offen = [b["stelle"]["abhaengig_von"] for b in a.buendel if b["stelle"]["abhaengig_von"]]
    assert offen and all(x["label"].startswith("[ar] ") for x in offen)
