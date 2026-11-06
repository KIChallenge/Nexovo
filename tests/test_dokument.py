"""Tests der Dokumentfunktion. Für SV-Box-Befunde werden nur Format und Vorhandensein geprüft, keine Personenwerte."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from lotse import config
from lotse.dokument import (
    BildNichtLesbar, Dokument, empfehlungen, impfeintraege, lade_dokument, medikamente, stammdaten,
)
from lotse.models import THEMEN

BEISPIELE = Path(__file__).resolve().parent.parent / "examples"
BEISPIEL = BEISPIELE / "entlassungsbrief_synthetisch.txt"
IMPFPASS = BEISPIELE / "impfpass_synthetisch.txt"
FOTO = BEISPIELE / "entlassungsbrief_foto.jpg"
ADMIN_SLOTS = {
    "person.vorname", "person.nachname", "person.geburtsdatum", "person.svnr", "person.strasse",
    "person.hausnummer", "person.plz", "person.ort", "aufenthalt.krankenhaus", "aufenthalt.entlassungsdatum",
    "reha.form",
}
# Allgemeine medizinische Wortstämme, die in keinem Zitat stehen dürfen
MEDIZINISCH = ("diagnos", "karzinom", "tumor", "krebs", "onkolog", "chemo", "strahl", "medikament", "mg ", "therapie")
# Finite Verben: ein Zitat mit einem davon ist kein bloßes Satzfragment
FINIT = re.compile(r"\b(?:empfiehlt|empfehlen|raten|rät|wird|werden|sollte|sollten|soll|sollen|ist|sind|muss|müssen)\b")


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
        assert not _fragment(e.zitat), e.zitat
    assert len({e.thema for e in liste}) == len(liste)  # je Thema genau eine


def _fragment(zitat: str) -> bool:
    """Satzfragment: beginnt mit „zu …“ oder klein ohne finites Verb, oder ist eine bloße Infinitivgruppe."""
    if zitat.startswith("zu "):
        return True
    if FINIT.search(zitat):
        return False
    return zitat[0].islower() or re.search(r"\bzu [a-zäöüß]+(?:en|ern|eln)\.?$", zitat) is not None


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


# ---------------------------------------------------------------- Fotos/Scans (nur Offline-Pfade)


@pytest.fixture
def ohne_ki(monkeypatch):
    monkeypatch.setenv("AZURE_API_KEY", "")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")


@pytest.mark.parametrize(
    ("name", "inhalt"),
    [
        ("foto.jpg", b"\xff\xd8\xff\xe0" + bytes(32)),
        ("scan.png", b"\x89PNG\r\n\x1a\n" + bytes(32)),
        ("scan.webp", b"RIFF\x00\x00\x00\x00WEBPVP8 " + bytes(32)),
        ("brief.pdf", b"\x89PNG\r\n\x1a\n" + bytes(32)),  # Inhalt zählt vor der Endung
        ("foto.jpeg", b"ohne Signatur"),  # Endung genügt
    ],
)
def test_bild_ohne_ki_modus(ohne_ki, name, inhalt):
    with pytest.raises(BildNichtLesbar) as fehler:
        lade_dokument(name, inhalt)
    assert fehler.value.grund == "ki_inaktiv"
    assert isinstance(fehler.value, ValueError)  # bestehende Aufrufer fangen ValueError


def test_beispielfoto_wird_als_bild_erkannt(ohne_ki):
    with pytest.raises(BildNichtLesbar) as fehler:
        lade_dokument(FOTO.name, FOTO.read_bytes())
    assert fehler.value.grund == "ki_inaktiv"


@pytest.mark.parametrize(
    ("name", "inhalt"),
    [
        ("foto.gif", b"GIF89a" + bytes(32)),
        ("IMG_0001.HEIC", b"\x00\x00\x00\x18ftypheic" + bytes(32)),
        ("bild.jpg", b"\x00\x00\x00\x18ftypmif1" + bytes(32)),  # HEIF mit falscher Endung
        ("scan.tiff", b"II*\x00" + bytes(32)),
        ("foto.heic", b"irgendwas"),
    ],
)
def test_nicht_unterstuetztes_bildformat(ohne_ki, name, inhalt):
    with pytest.raises(BildNichtLesbar) as fehler:
        lade_dokument(name, inhalt)
    assert fehler.value.grund == "format"


def test_textdatei_ist_nicht_transkribiert():
    assert lade_dokument(BEISPIEL.name, BEISPIEL.read_bytes()).transkribiert is False
    assert _text("Kein Bild").transkribiert is False


# ---------------------------------------------------------------- Synthetischer Brief


def test_synthetischer_brief_empfehlungen_und_grenze():
    text = BEISPIEL.read_text(encoding="utf-8")
    dok = lade_dokument(BEISPIEL.name, text.encode("utf-8"))
    liste = empfehlungen(dok)
    _pruefe_zitate(dok, liste)
    nach_thema = {e.thema: e for e in liste}
    assert nach_thema["rehabilitation"].zitat == "Eine ambulante Rehabilitation wird empfohlen."
    assert {"pflegegeld", "hauskrankenpflege"} <= set(nach_thema)
    assert nach_thema["kontrolltermine"].zitat == "Kontrolle bei der Hausärztin in einer Woche."
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


@pytest.mark.parametrize(
    ("satz", "thema", "zitat"),
    [
        ("Wegen der Chemotherapie empfehlen wir, eine Rezeptgebührenbefreiung zu beantragen.",
         "rezeptgebuehrenbefreiung", "empfehlen wir, eine Rezeptgebührenbefreiung zu beantragen."),
        ("Aufgrund der Demenz wird die Organisation einer Heimhilfe empfohlen.",
         "pflege_zu_hause", "wird die Organisation einer Heimhilfe empfohlen."),
        ("Wir empfehlen, Pflegegeld zu beantragen, da eine Demenz vorliegt.",
         "pflegegeld", "Wir empfehlen, Pflegegeld zu beantragen"),
        ("Wegen der Chemotherapie: Die Rezeptgebührenbefreiung sollte beantragt werden.",
         "rezeptgebuehrenbefreiung", "Die Rezeptgebührenbefreiung sollte beantragt werden."),
    ],
)
def test_medizinischer_satz_wird_mit_vollstaendigem_praedikat_gekuerzt(satz, thema, zitat):
    dok = _text(satz)
    liste = empfehlungen(dok)
    _pruefe_zitate(dok, liste)
    assert [(e.thema, e.zitat) for e in liste] == [(thema, zitat)]


@pytest.mark.parametrize(
    "zitat", ["Pflegegeld zu beantragen.", "eine Rezeptgebührenbefreiung zu beantragen.", "zu beantragen"]
)
def test_fragmentpruefung_erkennt_infinitivgruppen(zitat):
    assert _fragment(zitat)


def test_ohne_vollstaendiges_praedikat_kein_gekuerztes_zitat():
    # Der einzige nichtmedizinische Teil wäre die Infinitivgruppe „Rezeptgebührenbefreiung zu beantragen.“
    assert empfehlungen(_text("Wegen der Chemotherapie, Rezeptgebührenbefreiung zu beantragen.")) == []


def test_synthetischer_brief_ohne_fragment_zitate():
    dok = lade_dokument(BEISPIEL.name, BEISPIEL.read_bytes())
    zitate = {e.thema: e.zitat for e in empfehlungen(dok)}
    assert zitate["pflegegeld"] == "empfehlen wir, Pflegegeld zu beantragen."
    assert not any(_fragment(z) for z in zitate.values())


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


# ---------------------------------------------------------------- Kontrolltermine


@pytest.mark.parametrize(
    ("text", "zitat"),
    [
        ("Kontrolltermin bei der Hausärztin vereinbaren", "Kontrolltermin bei der Hausärztin vereinbaren"),
        ("Aufgabe Zuständig\nTermin zur hausärztlichen Kontrolle\nvereinbaren\nPatientin",
         "Termin zur hausärztlichen Kontrolle vereinbaren"),
        ("Weitere Termine koordinieren Hausärztin", "Weitere Termine koordinieren"),
        ("Ein Nachsorgetermin in drei Monaten wird empfohlen.", "Ein Nachsorgetermin in drei Monaten wird empfohlen."),
        ("Wiedervorstellung in 2 Wochen.", "Wiedervorstellung in 2 Wochen."),
        ("• Kontrolle beim Hausarzt nach 10 Tagen", "Kontrolle beim Hausarzt nach 10 Tagen"),
    ],
)
def test_kontrolltermin_wird_erkannt(text, zitat):
    dok = _text(text)
    liste = empfehlungen(dok)
    _pruefe_zitate(dok, liste)
    assert [(e.thema, e.zitat) for e in liste] == [("kontrolltermine", zitat)]


@pytest.mark.parametrize(
    "text",
    [
        "Eine strukturierte Unterstützung und Kontrolle werden empfohlen.",  # keine Terminaufgabe
        "Klinische Überwachung und Kontrolle der Vitalparameter.",
        "Zeitnahe Kontrolle nach der Entlassung.",  # weder Aufgabe noch Zeitangabe
        "Kontrolle des Blutdrucks in einer Woche.",  # medizinischer Inhalt
        "Weitere Bestrahlungstermine koordinieren",  # medizinischer Inhalt
        "Ein Kontrolltermin ist nicht erforderlich.",
    ],
)
def test_kein_kontrolltermin(text):
    assert [e for e in empfehlungen(_text(text)) if e.thema == "kontrolltermine"] == []


def test_zeitangabe_ohne_signal_liefert_nur_kontrolltermin():
    dok = _text("Kontrolle in 2 Wochen, danach Pflegegeld.")
    assert [e.thema for e in empfehlungen(dok)] == ["kontrolltermine"]


# ---------------------------------------------------------------- Impfeinträge


def test_synthetischer_impfpass():
    dok = lade_dokument(IMPFPASS.name, IMPFPASS.read_bytes())
    liste = impfeintraege(dok)
    assert [(i.impfung, i.datum) for i in liste] == [
        ("COVID-19", "14.10.2026"),
        ("COVID-19", "02.10.2025"),
        ("Influenza ('echte Grippe')", "14.10.2026"),
        ("Influenza ('echte Grippe')", "06.11.2025"),
        ("Pneumokokken", "20.03.2024"),
        ("Herpes Zoster", "11.01.2024"),
        ("Herpes Zoster", "15.05.2024"),
        ("Diphtherie, Tetanus, Pertussis, Poliomyelitis", "03.09.2019"),
    ]
    for i in liste:
        assert i.seite == 1 and i.zitat in dok.seiten[0]
        assert re.match(r"\d{1,2}\. \w+\.? \d{4} Impfstoff: ", i.zitat), i.zitat  # Kopfdatum + Impfstoff
    assert set(vars(liste[0])) == {"impfung", "datum", "seite", "zitat"}  # keine Bewertung (fällig o. Ä.)
    # Impfpass enthält keine Aufgaben und keine Medikationsliste
    assert empfehlungen(dok) == [] and medikamente(dok) == []


def test_impfgruppe_gilt_auf_folgeseite_und_ohne_ueberschrift_zaehlt_impfstoff():
    dok = _text(
        "Elektronischer Impfpass\nFSME\n2. Mai 2025\nImpfstoff: FSME-Immun 0,5 ml\nImpfdatum: 2. Mai 2025\n"
        "Eingetragen am: 3. Mai 2025 um 10:00 Uhr\f"
        "Patient: Max Muster geboren am: 1. Jänner 1960\n1. Apr. 2024\nImpfstoff: FSME-Immun 0,5 ml\n"
        "Impfdatum: 1. April 2024"
    )
    assert [(i.impfung, i.datum, i.seite) for i in impfeintraege(dok)] == [
        ("FSME", "02.05.2025", 1), ("FSME", "01.04.2024", 2),
    ]
    ohne = _text("Impfstoff: Boostrix Polio\nImpfdatum: 12.03.2019")
    assert [(i.impfung, i.datum, i.zitat) for i in impfeintraege(ohne)] == [
        ("Boostrix Polio", "12.03.2019", "Impfstoff: Boostrix Polio"),
    ]


def test_abfotografierter_papier_impfpass_als_tabelle():
    dok = _text(
        "Internationale Bescheinigungen über Impfungen – Impfpass\nDatum | Impfstoff | Impfung gegen | Stempel\n"
        "12.03.2019 | Boostrix Polio | Diphtherie, Tetanus, Pertussis, Polio | Dr. Fiktiv\n"
        "geb. 01.01.1960\nHepatitis A/B\n04.05.2021 | Twinrix | Ordination Fiktiv\n"
        "04.05.2021 | Twinrix | Ordination Fiktiv\n07.08.21 | Twinrix | zweistellige Jahreszahl"
    )
    assert [(i.impfung, i.datum) for i in impfeintraege(dok)] == [
        ("Diphtherie, Tetanus, Pertussis, Polio", "12.03.2019"),
        ("Hepatitis A/B", "04.05.2021"),  # Überschrift; doppelte Zeile nur einmal
    ]


def test_kein_impfdokument_keine_impfeintraege():
    assert impfeintraege(lade_dokument(BEISPIEL.name, BEISPIEL.read_bytes())) == []
    # Krankheitsname mit Datum in einem Arztbrief ist kein Impfeintrag
    assert impfeintraege(_text("Entlassungsbrief\nCOVID-19-Infektion 03.03.2022 | stationär")) == []


# ---------------------------------------------------------------- Medikation (nur Namen)


def test_synthetischer_brief_medikamente_nur_namen():
    dok = lade_dokument(BEISPIEL.name, BEISPIEL.read_bytes())
    liste = medikamente(dok)
    assert [m.name for m in liste] == ["Torasemid", "Entresto", "Pantoloc"]
    for m in liste:
        assert m.seite == 1 and m.zitat in dok.seiten[0]
        assert not re.search(r"\d|mg\b|Tabl", m.name + m.zitat), m  # keine Stärke, kein Schema


def test_medikationsabschnitt_grenzen_und_namensformen():
    dok = _text(
        "Pantoloc 20 mg vor dem Abschnitt\nMedikation:\n• Torasemid \"Hexal\" 10 mg Tabl. 1-0-0\n"
        "2) Ramipril HCT 5 mg/25 mg 1-0-0\nWeitere 5 mg nach Rücksprache\nEmpfehlungen\nConcor 5 mg 1-0-0\n"
        "Dauermedikation: Euthyrox® 50 µg 1-0-0"
    )
    assert [(m.name, m.zitat) for m in medikamente(dok)] == [
        ('Torasemid "Hexal"', 'Torasemid "Hexal"'),
        ("Ramipril HCT", "Ramipril HCT"),
        ("Euthyrox", "Euthyrox®"),
    ]
    assert medikamente(_text("Die Patientin nimmt Pantoloc 20 mg.")) == []  # kein Medikationsabschnitt


@pytest.mark.daten
def test_medikationstabelle_ohne_dosis_ueber_erstattungskodex():
    dok = _text(
        "5. Entlassungsmedikation\nMedikament /\nWirkstoff Zweck Hinweise\nAmlodipin Behandlung laut Arztbrief\n"
        "Pantoprazol\nMagenschutz bei\nIndikation\nEinnahme gemäß Medikationsplan\nWeitere onkologische\n"
        "Medikamente\nWichtige Hinweise zur Medikation:\nMacrogol nur nach Rücksprache"
    )
    assert [m.name for m in medikamente(dok)] == ["Amlodipin", "Pantoprazol"]


# ---------------------------------------------------------------- SV-Box-Befunde


@pytest.mark.befunde
def test_entlassungsbefund_alle_fuenf_aufgaben():
    dok = _befund("Entlassungsbefund.pdf")
    assert len(dok.seiten) == 7
    liste = empfehlungen(dok)
    _pruefe_zitate(dok, liste)
    themen = {e.thema for e in liste}
    assert {"rehabilitation", "pflegegeld", "hauskrankenpflege", "fahrtkosten", "rezeptgebuehrenbefreiung"} <= themen
    assert themen <= set(THEMEN)


@pytest.mark.befunde
def test_entlassungsbefund_kontrolltermin():
    dok = _befund("Entlassungsbefund.pdf")
    treffer = [e for e in empfehlungen(dok) if e.thema == "kontrolltermine"]
    assert len(treffer) == 1
    _pruefe_zitate(dok, treffer)
    assert re.search(r"Termin|Kontroll", treffer[0].zitat)


@pytest.mark.befunde
def test_impfpass_befund_eintraege_format():
    dok = _befund("Impfpass.pdf")
    liste = impfeintraege(dok)
    assert len(liste) > 0
    for i in liste:
        assert _datum_ok(i.datum)
        assert i.impfung and 1 <= i.seite <= len(dok.seiten) and i.zitat in dok.seiten[i.seite - 1]
    assert len({(i.impfung, i.datum) for i in liste}) == len(liste)


@pytest.mark.befunde
@pytest.mark.daten
def test_entlassungsbefund_medikamente_format():
    dok = _befund("Entlassungsbefund.pdf")
    liste = medikamente(dok)
    assert len(liste) == 4  # vier Tabellenzeilen; Spaltenreste und Hinweise sind keine Namen
    for m in liste:
        assert re.fullmatch(r"[A-ZÄÖÜ][\w-]+", m.name) and m.zitat == m.name
        assert 1 <= m.seite <= len(dok.seiten) and m.zitat in dok.seiten[m.seite - 1]
    assert impfeintraege(dok) == []


@pytest.mark.befunde
@pytest.mark.parametrize("name", ["Röntgen Befund.pdf", "Röntgen Befund2.pdf", "Befund bildgebende Diagnostik.pdf"])
def test_bildgebende_befunde_ohne_impfungen_und_medikamente(name):
    dok = _befund(name)
    assert impfeintraege(dok) == [] and medikamente(dok) == []


@pytest.mark.befunde
@pytest.mark.parametrize("name", ["Röntgen Befund.pdf", "Röntgen Befund2.pdf", "Befund bildgebende Diagnostik.pdf", "Impfpass.pdf"])
def test_befunde_ohne_empfehlung(name):
    assert empfehlungen(_befund(name)) == []


@pytest.mark.befunde
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


@pytest.mark.befunde
def test_entlassungsbefund_stammdaten_vorhanden():
    slots = {s.slot for s in stammdaten(_befund("Entlassungsbefund.pdf"))}
    assert {"person.vorname", "person.nachname", "person.geburtsdatum", "person.plz", "aufenthalt.entlassungsdatum"} <= slots


@pytest.mark.befunde
def test_roentgen_ohne_aufenthalt_und_ohne_ungueltige_svnr():
    slots = {s.slot for s in stammdaten(_befund("Röntgen Befund.pdf"))}
    assert not slots & {"aufenthalt.krankenhaus", "aufenthalt.entlassungsdatum", "person.svnr"}
