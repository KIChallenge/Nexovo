"""Tests der Dokumentfunktion. Für SV-Box-Befunde werden nur Format und Vorhandensein geprüft, keine Personenwerte."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from lotse import config
from lotse.dokument import Dokument, empfehlungen, lade_dokument, stammdaten
from lotse.models import THEMEN

BEISPIEL = Path(__file__).resolve().parent.parent / "examples" / "entlassungsbrief_synthetisch.txt"
ADMIN_SLOTS = {
    "person.vorname", "person.nachname", "person.geburtsdatum", "person.svnr", "person.strasse",
    "person.hausnummer", "person.plz", "person.ort", "aufenthalt.krankenhaus", "aufenthalt.entlassungsdatum",
    "reha.form",
}
# Allgemeine medizinische Wortstämme, die in keinem Zitat stehen dürfen
MEDIZINISCH = ("diagnos", "karzinom", "tumor", "krebs", "onkolog", "chemo", "strahl", "medikament", "mg ", "therapie")


def _text(inhalt: str, name: str = "brief.txt") -> Dokument:
    return lade_dokument(name, inhalt.encode("utf-8"))


def _befund(name: str) -> Dokument:
    pfad = config.datei(f"Befunde/{name}")
    return lade_dokument(pfad.name, pfad.read_bytes())


def _pruefe_zitate(dok: Dokument, liste) -> None:
    for e in liste:
        assert e.thema in THEMEN
        assert 1 <= e.seite <= len(dok.seiten)
        assert e.zitat and e.zitat in dok.seiten[e.seite - 1]
        assert e.quelle.art == "dokument" and e.quelle.titel == dok.name
        assert e.quelle.fundstelle == f"S. {e.seite}" and e.quelle.zitat == e.zitat
        assert not any(m in e.zitat.lower() for m in MEDIZINISCH), e.zitat
    assert len({e.thema for e in liste}) == len(liste)  # je Thema genau eine


def _datum_ok(wert: str) -> bool:
    if not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", wert):
        return False
    datetime.strptime(wert, "%d.%m.%Y")
    return True


# ---------------------------------------------------------------- Laden


def test_textdatei_mit_seitenumbruch_und_cp1252():
    dok = lade_dokument("a.txt", "Seite eins\n  mit   Leerraum\fSeite zwei".encode("cp1252"))
    assert dok.seiten == ["Seite eins mit Leerraum", "Seite zwei"]
    assert dok.zeilen[0] == ["Seite eins", "mit Leerraum"]
    assert lade_dokument("b.txt", "Größe".encode("cp1252")).seiten == ["Größe"]


def test_leeres_oder_kaputtes_dokument():
    with pytest.raises(ValueError):
        lade_dokument("leer.txt", b"  \n ")
    with pytest.raises(ValueError):
        lade_dokument("kaputt.pdf", b"%PDF-1.7 kein echtes pdf")


def test_dokument_ohne_zeilen_funktioniert():
    dok = Dokument(name="x", seiten=["Pflegegeld beantragen und prüfen lassen. Eine Rehabilitation wird empfohlen."])
    assert {e.thema for e in empfehlungen(dok)} == {"pflegegeld", "rehabilitation"}


# ---------------------------------------------------------------- Synthetischer Brief


def test_synthetischer_brief_empfehlungen_und_grenze():
    text = BEISPIEL.read_text(encoding="utf-8")
    dok = lade_dokument(BEISPIEL.name, text.encode("utf-8"))
    liste = empfehlungen(dok)
    _pruefe_zitate(dok, liste)
    nach_thema = {e.thema: e for e in liste}
    assert nach_thema["rehabilitation"].zitat == "Eine ambulante Rehabilitation wird empfohlen."
    assert {"pflegegeld", "hauskrankenpflege"} <= set(nach_thema)
    daten = stammdaten(dok)
    assert {s.slot: s.wert for s in daten}["reha.form"] == "ambulant"
    diagnose = next(z for z in text.splitlines() if z.startswith("Diagnose:"))
    ausgaben = [e.zitat for e in liste] + [s.zitat for s in daten] + [s.wert for s in daten]
    for a in ausgaben:
        assert diagnose not in a and "Herzinsuffizienz" not in a and "Torasemid" not in a, a


def test_synthetischer_brief_stammdaten():
    dok = lade_dokument(BEISPIEL.name, BEISPIEL.read_bytes())
    werte = {s.slot: s.wert for s in stammdaten(dok)}
    assert werte == {
        "aufenthalt.krankenhaus": "Klinikum Sonnental",
        "person.vorname": "Johanna",
        "person.nachname": "Beispiel",
        "person.geburtsdatum": "12.04.1941",
        "person.strasse": "Lindenweg",
        "person.hausnummer": "5/3",
        "person.plz": "1140",
        "person.ort": "Wien",
        "aufenthalt.entlassungsdatum": "03.11.2026",
        "reha.form": "ambulant",
    }


# ---------------------------------------------------------------- Regeln an kleinen Texten


@pytest.mark.parametrize(
    "satz",
    [
        "Eine Rehabilitation ist derzeit nicht erforderlich.",
        "Ein Antrag auf Pflegegeld wurde bereits gestellt.",
        "Die Patientin bezieht Pflegegeld der Stufe 2.",  # Feststellung, keine Empfehlung
        "Aufgrund des Karzinoms wird eine onkologische Rehabilitation empfohlen.",  # nur medizinisch begründet
    ],
)
def test_keine_empfehlung_ohne_ausdrueckliche_administrative_aufgabe(satz):
    assert empfehlungen(_text(satz)) == []


def test_medizinischer_satz_wird_auf_administrativen_teil_gekuerzt():
    dok = _text("Wegen der Chemotherapie empfehlen wir, eine Rezeptgebührenbefreiung zu beantragen.")
    (e,) = empfehlungen(dok)
    assert e.thema == "rezeptgebuehrenbefreiung"
    assert e.zitat == "eine Rezeptgebührenbefreiung zu beantragen."


def test_aufzaehlung_unter_empfohlen_werden():
    dok = _text("Empfohlen werden:\n• Mobile Hauskrankenpflege zur Unterstützung im Alltag.\n• Hilfe im Haushalt.")
    assert [(e.thema, e.zitat) for e in empfehlungen(dok)] == [
        ("hauskrankenpflege", "Mobile Hauskrankenpflege zur Unterstützung im Alltag."),
    ]


def test_aufgabentabelle_ueber_zeilenumbruch():
    dok = _text("Aufgabe Zuständig\nFahrtmöglichkeiten zu\nTherapieeinheiten klären\nSozialberatung\nPflegegeld beantragen Tochter")
    zitate = {e.thema: e.zitat for e in empfehlungen(dok)}
    assert zitate["pflegegeld"] == "Pflegegeld beantragen"
    assert "fahrtkosten" not in zitate  # Zeile enthält „Therapie…“ → medizinisch, verworfen


def test_widerspruechliche_reha_form_wird_nicht_gesetzt():
    dok = _text("Eine ambulante Rehabilitation wird empfohlen. Alternativ wird eine stationäre Rehabilitation empfohlen.")
    assert "reha.form" not in {s.slot for s in stammdaten(dok)}


def test_stammdaten_formate_aus_text():
    dok = _text(
        "Entlassungsbrief\nPatient:\nMax Mustermann (M) geb. 2. März 1950\nSVNR: 1234 010350\n"
        "Wohnort\nProbegasse. 7\n1100 Wien\nEntlassen am 3.11.2026"
    )
    werte = {s.slot: s.wert for s in stammdaten(dok)}
    assert werte["person.vorname"] == "Max" and werte["person.nachname"] == "Mustermann"
    assert werte["person.geburtsdatum"] == "02.03.1950"
    assert werte["person.svnr"] == "1234010350"
    assert (werte["person.strasse"], werte["person.hausnummer"], werte["person.plz"]) == ("Probegasse", "7", "1100")
    assert werte["aufenthalt.entlassungsdatum"] == "03.11.2026"
    assert "person.svnr" not in {s.slot for s in stammdaten(_text("SVNR: 123456789"))}  # nicht 10-stellig


# ---------------------------------------------------------------- SV-Box-Befunde


@pytest.mark.daten
def test_entlassungsbefund_alle_fuenf_aufgaben():
    dok = _befund("Entlassungsbefund.pdf")
    assert len(dok.seiten) == 7
    liste = empfehlungen(dok)
    _pruefe_zitate(dok, liste)
    themen = {e.thema for e in liste}
    assert {"rehabilitation", "pflegegeld", "hauskrankenpflege", "fahrtkosten", "rezeptgebuehrenbefreiung"} <= themen
    assert themen <= set(THEMEN)


@pytest.mark.daten
@pytest.mark.parametrize("name", ["Röntgen Befund.pdf", "Röntgen Befund2.pdf", "Befund bildgebende Diagnostik.pdf", "Impfpass.pdf"])
def test_befunde_ohne_empfehlung(name):
    assert empfehlungen(_befund(name)) == []


@pytest.mark.daten
@pytest.mark.parametrize(
    "name",
    ["Entlassungsbefund.pdf", "Röntgen Befund.pdf", "Röntgen Befund2.pdf", "Befund bildgebende Diagnostik.pdf", "Impfpass.pdf"],
)
def test_befund_stammdaten_nur_administrativ_und_formatiert(name):
    dok = _befund(name)
    daten = stammdaten(dok)
    for s in daten:
        assert s.slot in ADMIN_SLOTS
        assert s.zitat in dok.seiten[s.seite - 1]
        assert not any(m in s.zitat.lower() for m in MEDIZINISCH), s.slot
        if s.slot in ("person.geburtsdatum", "aufenthalt.entlassungsdatum"):
            assert _datum_ok(s.wert), s.slot
        if s.slot == "person.plz":
            assert re.fullmatch(r"\d{4}", s.wert)
        if s.slot == "person.svnr":
            assert re.fullmatch(r"\d{10}", s.wert)
    assert "person.geburtsdatum" in {s.slot for s in daten}


@pytest.mark.daten
def test_entlassungsbefund_stammdaten_vorhanden():
    slots = {s.slot for s in stammdaten(_befund("Entlassungsbefund.pdf"))}
    assert {"person.vorname", "person.nachname", "person.geburtsdatum", "person.plz", "aufenthalt.entlassungsdatum"} <= slots


@pytest.mark.daten
def test_roentgen_ohne_aufenthalt_und_ohne_ungueltige_svnr():
    slots = {s.slot for s in stammdaten(_befund("Röntgen Befund.pdf"))}
    assert not slots & {"aufenthalt.krankenhaus", "aufenthalt.entlassungsdatum", "person.svnr"}
