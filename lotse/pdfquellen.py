"""Seitentexte der SV-Box-PDFs (Leistungskataloge, Formulare, EKO-Zeichenerklärung) mit Quellenangabe je PDF-Seite."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from lotse import config
from lotse.models import Quelle

ORDNER = ("Leistungskataloge", "Anträge und Formulare")
LEGENDE = "Medikamenten Erstattungskodex/Zeichenerklärungen und Abkürzungen.pdf"
SERVICERATGEBER = "Leistungskataloge/Serviceratgeber-2026_Broschuere_A5_OEAM_99-19_klein_korr.pdf"


@dataclass(frozen=True)
class PdfInfo:
    art: str
    titel: str
    stand: str = ""  # ISO-Datum oder ""
    layout: bool = False  # pypdf-Layoutmodus (sauberer bei Tabellen mit Spalten)
    doppelseite: bool = False  # zwei Druckseiten je PDF-Seite


# Titel nach Deckblatt; Gültigkeitsbereich der Honorarordnungen steht im Titel.
_REGISTER: dict[str, PdfInfo] = {
    SERVICERATGEBER: PdfInfo(
        "serviceratgeber", "ÖGK – Leistungen und Services 2026", "2026-01-01", doppelseite=True
    ),
    "Leistungskataloge/ÖGK Honorarordnung-fuer-Vertragsaerzte-und-Vertragsgruppenpraxen.pdf": PdfInfo(
        "honorarordnung",
        "Honorarordnung für Vertragsärzte und Vertragsgruppenpraxen – nur Bundesland Steiermark, Stand 01.01.2025",
        "2025-01-01",
    ),
    "Leistungskataloge/Zahnärzte Honorarordnung_2026_aktuellste_Version_MAI_070526.pdf": PdfInfo(
        "honorarordnung",
        "Honorarordnungen & Honorartarife für Vertragszahnärzt:innen – gültig ab 1. Jänner 2026",
        "2026-01-01",
    ),
    "Anträge und Formulare/PAL080_0125_Mpfl_052026.pdf": PdfInfo(
        "formular", "PVA – Antrag auf Pflegegeld nach dem BPGG, PAL 080 (01.2025)"
    ),
    "Anträge und Formulare/Antrag Kur und Reha.pdf": PdfInfo(
        "formular", "Antrag auf Rehabilitations-, Kur- bzw. Erholungsaufenthalt (DVSV – KUR1)"
    ),
    "Anträge und Formulare/Antrag-auf-Zuschuss-zu-Fahrtkosten_Wien.pdf": PdfInfo(
        "formular", "ÖGK – Antrag auf Zuschuss zu Fahrtkosten für Versicherte mit Rezeptgebührenbefreiung"
    ),
    "Anträge und Formulare/fsw-antrag-auf-foerderung-von-leistungen.1779095804.pdf": PdfInfo(
        "formular", "FSW – Antrag auf Förderung von Leistungen (V8 03/2026)"
    ),
    "Anträge und Formulare/Bedarfsmeldung-Senior_innen-Wohngemeinschaft_Basispaket.1736522017.pdf": PdfInfo(
        "formular", "FSW – Bedarfsmeldung Senior:innen-Wohngemeinschaften – Basispaket (V2.0 12/2024)"
    ),
    "Anträge und Formulare/FSW-Antrag-Beilage-Einrichtungswunsch.1779345450.pdf": PdfInfo(
        "formular", "FSW – Einrichtungswunsch für Wohn- und Pflegehäuser (V5 05/2026)"
    ),
    "Anträge und Formulare/Reha_n_Unfall_052026.pdf": PdfInfo(
        "formular", "Antrag auf Anschlussheilverfahren oder Rehabilitation nach Unfall"
    ),
    LEGENDE: PdfInfo("ekodex", "Erstattungskodex (EKO 1/2024) – Zeichenerklärungen und Abkürzungen", layout=True),
}

_LIGATUREN = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
_PRIVAT = re.compile("[\ue000-\uf8ff]")  # Symbolschriften (Kästchen) aus Formularen
_LIGATUR_LUECKE = re.compile("([ﬀﬁﬂﬃﬄ]) (?=[a-zäöüß])")
# Silbentrennung am Zeilenende ("Kran- kenpflege"), nicht bei Aufzählungen ("Kranken- und Unfall…")
_TRENNUNG = re.compile(r"(\w) ?- (?!(?:und|oder|bzw|sowie|bis|als|wie|u|o)\b)([a-zäöüß])")


def normalisiere(text: str) -> str:
    """Whitespace normalisieren, Ligaturen auflösen, Symbolzeichen und Zeilenend-Trennungen entfernen."""
    text = " ".join(_PRIVAT.sub(" ", text).split())
    text = _LIGATUR_LUECKE.sub(r"\1", text)
    for lig, ersatz in _LIGATUREN.items():
        text = text.replace(lig, ersatz)
    return _TRENNUNG.sub(r"\1\2", text)


def info(datei: str) -> PdfInfo:
    """Registereintrag; unbekannte PDFs bekommen Art nach Ordner und den Dateinamen als Titel."""
    if datei in _REGISTER:
        return _REGISTER[datei]
    name = Path(datei).stem
    if datei.startswith("Anträge und Formulare/"):
        return PdfInfo("formular", name)
    return PdfInfo("honorarordnung" if "honorarordnung" in name.casefold() else "serviceratgeber", name)


def quelldateien() -> list[str]:
    """Alle indizierten PDFs, relativ zu DATA_DIR."""
    dateien: list[str] = []
    for ordner in ORDNER:
        pfad = config.datei(ordner)
        if pfad.is_dir():
            dateien += sorted(f"{ordner}/{p.name}" for p in pfad.iterdir() if p.suffix.lower() == ".pdf")
    if config.datei(LEGENDE).is_file():
        dateien.append(LEGENDE)
    return dateien


def lade_seiten(datei: str) -> list[str]:
    """Normalisierte Seitentexte (Index 0 = PDF-S. 1); Seiten ohne Text ergeben ""."""
    from pypdf import PdfReader

    # pypdf meldet fehlende Schriftdetails (fontTools) als Warnung; der Text ist trotzdem vollständig.
    pypdf_log = logging.getLogger("pypdf")
    vorher = pypdf_log.level
    pypdf_log.setLevel(logging.ERROR)
    try:
        leser = PdfReader(config.datei(datei))
        modus = "layout" if info(datei).layout else "plain"
        return [normalisiere(seite.extract_text(extraction_mode=modus) or "") for seite in leser.pages]
    finally:
        pypdf_log.setLevel(vorher)


def lade_alle() -> dict[str, list[str]]:
    return {datei: lade_seiten(datei) for datei in quelldateien()}


def quelle(datei: str, seite: int, zitat: str = "") -> Quelle:
    """Quelle für eine PDF-Seite (1-basiert, immer PDF-Seite, nie Druckseite)."""
    i = info(datei)
    return Quelle(art=i.art, titel=i.titel, fundstelle=f"PDF-S. {seite}", datei=datei, zitat=zitat, stand=i.stand)


_INHALT_EINTRAG = re.compile(r"([^.…]{3,120}?)\s*(?:\.\s?){4,}\s*(\d{1,3})(?!\d)")


def inhaltsverzeichnis(seiten: list[str], datei: str) -> dict[int, list[str]]:
    """Kapiteltitel je PDF-Seite aus Inhaltsverzeichnis-Seiten ("Titel ........ 23").

    Nur für Dokumente mit bekannter Seitenzuordnung (Doppelseiten: Druckseite p liegt auf PDF-S. p // 2 + 1).
    """
    if not info(datei).doppelseite:
        return {}
    titel: dict[int, list[str]] = {}
    for text in seiten:
        if not ist_verzeichnis(text):
            continue
        for m in _INHALT_EINTRAG.finditer(text):
            name = m.group(1).strip(" .")
            pdf_seite = int(m.group(2)) // 2 + 1
            if name and 1 <= pdf_seite <= len(seiten):
                titel.setdefault(pdf_seite, []).append(name)
    return titel


def ist_verzeichnis(text: str) -> bool:
    """Inhaltsverzeichnis-Seite (Navigation, kein Inhalt): viele Punktführer mit Seitenzahl."""
    return len(re.findall(r"(?:\.\s?){5,}\s*\d{1,3}(?!\d)", text)) >= 8 or "inhaltsverzeichnis" in text[:200].casefold()
