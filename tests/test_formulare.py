"""Tests für Formular-Registry und Vorausfüllen (synthetische Werte, keine echten Personendaten)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from io import BytesIO

import pytest
from pypdf import PdfReader

from lotse import config
from lotse.formulare import (
    alle_formulare,
    ausfuellen,
    exportwerte,
    feldkarte,
    fehlende_pflichtangaben,
    formular,
    hausnummer_teile,
    normalisiere,
)
from lotse.models import FORMULARE
from lotse.slots import SLOTS

# Frei erfundene Werte
WERTE = {
    "pflege.antragsart": "erhoehung",
    "person.svnr": "1234 010150",
    "person.vorname": "Erika",
    "person.nachname": "Beispielfrau",
    "person.geburtsdatum": "1.2.1950",
    "person.geschlecht": "weiblich",
    "person.strasse": "Probegasse",
    "person.hausnummer": "7/2/5",
    "person.plz": "1100",
    "person.ort": "Wien",
    "person.bundesland": "Wien",
    "person.telefon": "+43 660 1112233",
    "person.email": "erika@example.org",
    "vertretung.vorname": "Max",
    "vertretung.nachname": "Beispielmann",
    "vertretung.telefon": "+43 660 9998877",
    "versicherung.pension": "PVA",
    "pflege.stufe": "2",
    "aufenthalt.krankenhaus": "Klinikum Musterstadt",
    "aufenthalt.entlassungsdatum": "26.10.2026",
    "bank.iban": "AT61 1904 3002 3457 3201",
    "bank.kontoinhaber": "Erika Beispielfrau",
}


def _felder(pdf: bytes) -> dict[str, dict]:
    return feldkarte(PdfReader(BytesIO(pdf)))


def _wert(eintrag: dict) -> str | None:
    v = eintrag["feld"].get("/V")
    return None if v in (None, "", "/Off") else str(v)


def _angehakt(eintrag: dict) -> list[str]:
    return [str(w["/AS"]) for w in eintrag["widgets"] if str(w.get("/AS", "/Off")) != "/Off"]


def _norm(text: str) -> str:
    return " ".join(text.split())


# ---------------------------------------------------------------- ohne Quelldaten


def test_registry_fuer_jedes_formular_vollstaendig():
    assert set(alle_formulare()) == set(FORMULARE)
    for fid, f in alle_formulare().items():
        assert f.datei == FORMULARE[fid]
        for text in (f.titel, f.stelle, f.hinweise):
            assert text.get("de") and text.get("en"), fid
        assert f.unterlagen or (f.ohne_unterlagen.get("de") and f.ohne_unterlagen.get("en")), fid
        for u in f.unterlagen:
            assert u.text["de"] and u.text["en"]
            assert u.quelle.art == "formular" and u.quelle.fundstelle.startswith("PDF-S. ")
            assert 0 < len(u.quelle.zitat) <= 300
            assert set(u.leistungen) <= set(f.vorauswahl), fid
        assert set(f.pflicht) <= set(f.slots) <= set(SLOTS), fid


def test_vollstaendig_gemappte_formulare_haben_pflichtangaben():
    assert {"pflege.antragsart", "person.svnr", "person.nachname", "person.geburtsdatum"} <= set(formular("PAL080").pflicht)
    assert "bank.iban" in formular("FAHRTKOSTEN_OEGK_WIEN").pflicht
    assert {"pflege_zu_hause", "mobile_fruehfoerderung"} == set(formular("FSW_FOERDERUNG").vorauswahl)


def test_unbekanntes_formular():
    with pytest.raises(KeyError):
        formular("GIBT_ES_NICHT")


def test_fehlende_pflichtangaben_in_registry_reihenfolge():
    werte = {"person.vorname": "Erika", "person.nachname": "Beispielfrau", "person.svnr": "123"}  # SVNR ungültig
    assert fehlende_pflichtangaben("PAL080", werte) == [
        "pflege.antragsart", "person.svnr", "person.geburtsdatum",
        "person.strasse", "person.hausnummer", "person.plz", "person.ort",
    ]
    assert fehlende_pflichtangaben("PAL080", WERTE) == []


@pytest.mark.parametrize(
    ("wert", "erwartet"),
    [
        ("12", ("12", "", "")),
        ("12/4", ("12", "", "4")),
        ("12/3/4", ("12", "3", "4")),
        ("12a, Stiege 3, Tür 14", ("12a", "3", "14")),
        ("5 Top 7", ("5", "", "7")),
    ],
)
def test_hausnummer_teile(wert, erwartet):
    t = hausnummer_teile(wert)
    assert (t["hausnummer"], t["stiege"], t["tuer"]) == erwartet


@pytest.mark.parametrize(
    ("slot", "eingabe", "erwartet"),
    [
        ("person.geburtsdatum", "1.2.1950", "01.02.1950"),
        ("person.geburtsdatum", "1950-02-01", "01.02.1950"),
        ("person.geburtsdatum", "31.02.1950", "31.02.1950"),  # kein Kalenderdatum → bleibt (ungültig)
        ("person.svnr", "1234 01 01 50", "1234010150"),
        ("bank.iban", "at61 1904 3002 3457 3201", "AT611904300234573201"),
        ("person.ort", "  Wien  ", "Wien"),
    ],
)
def test_normalisiere(slot, eingabe, erwartet):
    assert normalisiere(slot, eingabe) == erwartet


def test_unterlagen_je_vorauswahl():
    f = formular("FSW_FOERDERUNG")
    pflege = {u.quelle.zitat for u in f.unterlagen_fuer("pflege_zu_hause")}
    frueh = {u.quelle.zitat for u in f.unterlagen_fuer("mobile_fruehfoerderung")}
    basis = {u.quelle.zitat for u in f.unterlagen_fuer(None)}
    assert basis < pflege and basis < frueh
    assert any("Hauptmietzins" in z for z in pflege - frueh)
    assert any("Frühförderstellen" in z for z in frueh - pflege)


# ---------------------------------------------------------------- mit Original-PDFs


@pytest.mark.daten
def test_pal080_werte_wieder_auslesbar():
    e = ausfuellen("PAL080", WERTE)
    felder = _felder(e.pdf)
    assert _wert(felder["Fam.Name"]) == "Beispielfrau"
    assert _wert(felder["Vorname"]) == "Erika"
    assert _wert(felder["Geburtsdatum"]) == "01.02.1950"
    assert _wert(felder["VSNR_1"]) == "1234010150"  # 10 Ziffern, Formatierung macht das Formular
    assert _wert(felder["Adresse Straße"]) == "Probegasse"
    assert _wert(felder["Hausnummer, Stiege, Tür"]) == "7/2/5"
    assert (_wert(felder["PLZ"]), _wert(felder["Ort"]), _wert(felder["Land"])) == ("1100", "Wien", "Österreich")
    assert _wert(felder["Name weitere Person"]) == "Beispielmann Max, Tel. +43 660 9998877"
    assert _angehakt(felder["Hausbesuch"]) == ["/02"]  # „ja“ – helfende Person wird verständigt
    assert _wert(felder["Spital"]) == "Klinikum Musterstadt" and _wert(felder["KH bis"]) == "26.10.2026"
    assert e.fehlend_pflicht == [] and e.ungueltig == []
    assert {"person.svnr", "pflege.antragsart", "aufenthalt.krankenhaus"} <= set(e.befuellt)
    assert bool(PdfReader(BytesIO(e.pdf)).trailer["/Root"]["/AcroForm"]["/NeedAppearances"]) is True


@pytest.mark.daten
@pytest.mark.parametrize(("antragsart", "export"), [("zuerkennung", "/01"), ("erhoehung", "/02"), ("weitergewaehrung", "/03")])
def test_pal080_antragsart_kreuzt_genau_ein_feld(antragsart, export):
    felder = _felder(ausfuellen("PAL080", {"pflege.antragsart": antragsart}).pdf)
    assert _wert(felder["Antrag Pflg"]) == export
    assert _angehakt(felder["Antrag Pflg"]) == [export]


@pytest.mark.daten
def test_fehlende_pflicht_und_ungueltige_werte():
    e = ausfuellen("PAL080", {"person.nachname": "Beispielfrau", "person.svnr": "12345", "person.plz": "AB12"})
    felder = _felder(e.pdf)
    assert _wert(felder["VSNR_1"]) is None and _wert(felder["PLZ"]) is None
    assert e.ungueltig == ["person.svnr", "person.plz"]
    assert e.befuellt == ["person.nachname"]
    assert e.fehlend_pflicht == [s for s in formular("PAL080").pflicht if s != "person.nachname"]


@pytest.mark.daten
def test_unbekannte_slots_werden_ignoriert():
    mit = _felder(ausfuellen("PAL080", {**WERTE, "foo.bar": "x", "person.lieblingsfarbe": "blau"}).pdf)
    ohne = _felder(ausfuellen("PAL080", WERTE).pdf)
    assert {k: _wert(v) for k, v in mit.items()} == {k: _wert(v) for k, v in ohne.items()}


@pytest.mark.daten
@pytest.mark.parametrize("fid", list(FORMULARE))
def test_unterschrift_und_gesperrte_seiten_bleiben_leer(fid):
    f = formular(fid)
    for leistung in [None, *f.vorauswahl]:
        felder = _felder(ausfuellen(fid, WERTE, leistung=leistung).pdf)
        for name, eintrag in felder.items():
            if eintrag["typ"] == "/Sig":
                assert _wert(eintrag) is None, (fid, name)
            if eintrag["seiten"] <= set(f.gesperrte_seiten):  # nur auf dem ärztlichen Teil
                assert _wert(eintrag) is None and not _angehakt(eintrag), (fid, name)


@pytest.mark.daten
def test_kur1_aerztlicher_teil_leer_und_bürgerteil_befuellt():
    felder = _felder(ausfuellen("KUR1", WERTE).pdf)
    seite2 = [n for n, e in felder.items() if e["seiten"] == {2}]
    assert len(seite2) > 40  # ärztliche Stellungnahme
    assert all(_wert(felder[n]) is None for n in seite2)
    assert _wert(felder["Patient(in)"]) == "Beispielfrau Erika"
    assert _wert(felder["Anschrift Patient(in)"]) == "Probegasse 7/2/5, 1100 Wien"
    assert _angehakt(felder["Pensionsversicherung"]) == ["/j"]
    assert _wert(felder["Pensionsversicherungsträger"]) == "PVA"
    assert _angehakt(felder["Pflegegeld"]) == ["/j"] and _wert(felder["Stufe1"]) == "2"


@pytest.mark.daten
def test_kur1_adresse_ohne_hausnummer():
    werte = {k: WERTE[k] for k in ("person.strasse", "person.plz", "person.ort")}
    assert _wert(_felder(ausfuellen("KUR1", werte).pdf)["Anschrift Patient(in)"]) == "Probegasse, 1100 Wien"


@pytest.mark.daten
def test_fsw_vorauswahl_pflege_zu_hause():
    ohne = _felder(ausfuellen("FSW_FOERDERUNG", WERTE).pdf)
    mit = _felder(ausfuellen("FSW_FOERDERUNG", WERTE, leistung="pflege_zu_hause").pdf)
    assert not _angehakt(ohne["Pflege und Betreuung zu Hause"])
    assert _angehakt(mit["Pflege und Betreuung zu Hause"]) == ["/Ja"]
    assert 5 in mit["Pflege und Betreuung zu Hause"]["seiten"]
    assert _angehakt(mit["Leistungen Pflege und Betreuung"]) == ["/Ja"]
    assert not _angehakt(mit["Mobile Fruehfoerderung"])
    assert _wert(mit["IBAN 3"]) == "AT611904300234573201"
    assert _angehakt(mit["Geschlecht KundIn"]) == ["/weiblich"]
    assert [_wert(mit[n]) for n in ("Hausnr Lebensmittelpunkt", "Stiege Lebensmittelpunkt", "Tuernr Lebensmittelpunkt")] == [
        "7", "2", "5",
    ]


@pytest.mark.daten
@pytest.mark.parametrize("fid", list(FORMULARE))
def test_registry_passt_zum_pdf(fid):
    f = formular(fid)
    karte = feldkarte(PdfReader(config.datei(f.datei)))
    assert all(_wert(e) is None for e in karte.values()), "Original-PDF sollte leer sein"
    regeln = [r for leistung in [None, *f.vorauswahl] for r in f.regeln(leistung)]
    for r in regeln:
        eintrag = karte[r["feld"]]
        assert eintrag["typ"] != "/Sig"
        assert not eintrag["seiten"] <= set(f.gesperrte_seiten), r["feld"]
        werte = list(r.get("werte", {}).values()) + ([r["wert"]] if "wert" in r else [])
        if eintrag["typ"] == "/Btn":
            assert werte and set(werte) <= exportwerte(eintrag), r["feld"]
        else:
            assert eintrag["typ"] == "/Tx", r["feld"]


@pytest.mark.daten
@pytest.mark.parametrize("fid", list(FORMULARE))
def test_zitate_stehen_woertlich_im_formular(fid):
    f = formular(fid)
    seiten = [_norm(s.extract_text() or "") for s in PdfReader(config.datei(f.datei)).pages]
    quellen = [f.quelle, f.stelle_quelle, *(u.quelle for u in f.unterlagen)]
    quellen += [a["quelle"] for a in f.adressen.values()] + list(f.hinweis_quellen)
    for q in quellen:
        if q.art == "formular":
            seite = int(q.fundstelle.removeprefix("PDF-S. "))
            assert q.zitat in seiten[seite - 1], (fid, q.fundstelle, q.zitat)
        else:
            assert q.art == "recht" and q.fundstelle.startswith("BGBl.")
            text = _norm(" ".join(ET.parse(config.datei(q.datei)).getroot().itertext()))
            assert q.zitat in text, (fid, q.titel)
