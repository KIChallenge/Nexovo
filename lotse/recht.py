"""Rechtstexte (SV-Box `Rechtstexte/`, RIS-Sozdok-XML) → `Norm`-Datensätze mit Fundstelle und Rechtsstand."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from lotse import config
from lotse.models import Quelle

ORDNER = "Rechtstexte"
ZITAT_MAX = 300

# Anzeige der Gliederungsart im Titel ("BPGG § 5", "… Art. 3")
_TYP_ANZEIGE = {
    "PARA": "§",
    "ART": "Art.",
    "ANL": "Anl.",
    "ANH": "Anh.",
    "ZIFF": "Ziff.",
    "ZAHL": "Z",
    "BEIL": "Beil.",
    "TEIL": "Teil",
    "EINFB": "Einführungsbest.",
    "EINL": "Einl.",
    "INH": "Inhaltsverzeichnis",
    "PROM": "Promulgationsklausel",
    "PRAE": "Präambel",
}
_TYP_OHNE_NUMMER = {"KEIN", "INH", "PROM", "PRAE", "0", ""}

# Überschriften-Typen: Normüberschrift vs. übergeordnete Gliederung
_UEBERSCHRIFT_NORM = {"para", "art", "anlage", "titel"}
_OHNE_TITEL = re.compile(r"\s*-?\s*\(ohne titel\)", re.IGNORECASE)
_AUFGEHOBEN = re.compile(r"(?:(?:§|Art\.|Artikel|Z|Ziff\.)\s*\w+\.?\s*)?\(?aufgehoben\)?\.?", re.IGNORECASE)

# Blockelemente werden zu eigenen Zeilen, Inline-Ersatz für Sonderelemente
_BLOCK = {
    "ueberschrift", "absatz", "listelem", "schlussteil", "schluss", "tr", "fntext", "inhaltsvz", "unterschrift",
}
_ERSATZ = {"br": " ", "nbsp": " ", "tab": " ", "gdash": "-", "bdash": "", "amp": "&", "lt": "<", "gt": ">"}
_AUSLASSEN = {"binary", "fnzeichen", "layoutdaten", "abstand"}


def _iso(datum: str) -> str:
    """ISO-Datum oder "" (Platzhalter `1111-…`, abgeschnittene Werte)."""
    datum = (datum or "").strip()
    if datum.startswith("1111") or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", datum):
        return ""
    return datum


@dataclass(frozen=True)
class Norm:
    kuerzel: str  # Kürzel laut Dateiname, z. B. "BPGG"
    typ: str  # PARA, ART, ANL, …
    nummer: str  # "5", "143a", …
    bgbl: str  # Fundstelle, z. B. "BGBl. I Nr. 80/2019"
    kundmachung: str  # ISO-Datum oder ""
    inkrafttreten: str  # ISO-Datum oder "" (Platzhalter 1111 = Stand unbekannt)
    ueberschrift: str  # Normüberschrift, z. B. "Höhe des Pflegegeldes"
    text: str  # Normtext, Absätze durch "\n" getrennt
    datei: str  # relativ zu DATA_DIR
    abkuerzung: str = ""  # amtliche Abkürzung (metadaten/@abkrvo), z. B. "BPGG"
    gesetz: str = ""  # Langtitel (metadaten/@titrvo)
    gliederung: str = ""  # übergeordnete Überschriften (Abschnitt, Hauptstück)
    dokart: str = ""  # BG, V, Satzung, …
    abschnitte: tuple[tuple[int, str], ...] = ()  # (Position im Text, Überschrift)

    def kopf_bei(self, position: int) -> str:
        """Die zwei letzten Überschriften vor `position` (z. B. Abschnitt + §-Überschrift)."""
        davor = [t for p, t in self.abschnitte if p < position]
        return " ".join(davor[-2:])

    @property
    def bezeichnung(self) -> str:
        """Gliederungsbezeichnung, z. B. "§ 5", "Art. 3", "" bei Gesamtdokumenten."""
        if self.typ in _TYP_OHNE_NUMMER:
            return _TYP_ANZEIGE.get(self.typ, "")
        anzeige = _TYP_ANZEIGE.get(self.typ, self.typ)
        return f"{anzeige} {self.nummer}".strip()

    @property
    def titel(self) -> str:
        return f"{self.abkuerzung or self.kuerzel} {self.bezeichnung}".strip()

    @property
    def aufgehoben(self) -> bool:
        """Aufgehobene Norm ohne geltenden Inhalt (Überschrift "aufgehoben …" oder Text "§ 14. Aufgehoben.")."""
        return self.ueberschrift.casefold().startswith("aufgehoben") or bool(_AUFGEHOBEN.fullmatch(self.text))

    def quelle(self, zitat: str = "") -> Quelle:
        """Quelle nach Konvention: art="recht", titel="BPGG § 5", fundstelle=BGBl, stand=Inkrafttreten."""
        return Quelle(
            art="recht",
            titel=self.titel,
            fundstelle=self.bgbl,
            datei=self.datei,
            zitat=kuerze(zitat or self.text),
            stand=self.inkrafttreten,
        )


def kuerze(text: str, laenge: int = ZITAT_MAX) -> str:
    """Wörtlicher, whitespace-normalisierter Anfang eines Texts (≤ `laenge`, an Wortgrenze)."""
    text = " ".join(text.split())
    if len(text) <= laenge:
        return text
    schnitt = text.rfind(" ", 0, laenge + 1)
    return text[: schnitt if schnitt > laenge // 2 else laenge]


def _fundstelle(metadaten: ET.Element, kundmachung: str) -> str:
    """Fundstelle aus dem ersten `puborgan` (jüngste Kundmachung), z. B. "BGBl. II Nr. 263/2025"."""
    p = metadaten.find("puborgane/puborgan")
    if p is None:
        return ""
    organ = " ".join(x for x in (p.get("puborg", "").strip(), p.get("gldpuborg", "").strip()) if x)
    nr = p.get("nrpuborg", "").strip()
    jahr = p.get("jahrgang", "").strip() or (kundmachung[:4] if kundmachung else "")
    if not nr:
        return organ
    return f"{organ} Nr. {nr}/{jahr}" if jahr else f"{organ} Nr. {nr}"


def _bloecke(nutzdaten: ET.Element) -> list[tuple[ET.Element | None, str]]:
    """Text in Dokumentreihenfolge als (Blockelement, Text)-Paare, whitespace-normalisiert."""
    bloecke: list[tuple[ET.Element | None, str]] = []
    puffer: list[str] = []

    def leeren(block: ET.Element | None) -> None:
        s = " ".join("".join(puffer).split())
        puffer.clear()
        if s:
            bloecke.append((block, s))

    def lauf(el: ET.Element, block: ET.Element | None) -> None:
        tag = el.tag
        if tag in _ERSATZ:
            puffer.append(_ERSATZ[tag])
        elif tag in _AUSLASSEN:
            pass
        elif tag in _BLOCK:
            leeren(block)
            if el.text:
                puffer.append(el.text)
            for kind in el:
                lauf(kind, el)
            leeren(el)
        else:
            if el.text:
                puffer.append(el.text)
            for kind in el:
                lauf(kind, block)
            if tag in ("symbol", "td", "h-td", "gldsym"):
                puffer.append(" ")
        if el.tail:
            puffer.append(el.tail)

    for kind in nutzdaten:
        lauf(kind, None)
    leeren(None)
    return bloecke


def lade_norm(pfad: Path) -> Norm:
    """Eine Sozdok-XML-Datei → `Norm`. Metadaten haben Vorrang vor dem (teils abgeschnittenen) Dateinamen."""
    name = pfad.stem
    teile = name.split("=")
    teile += [""] * (6 - len(teile))
    kuerzel, typ, nummer = teile[0], teile[1], teile[2]

    wurzel = ET.parse(pfad).getroot()
    rvo = wurzel.find("rvo")
    md = rvo.find("metadaten") if rvo is not None else None
    nd = rvo.find("nutzdaten") if rvo is not None else None
    if md is None or nd is None:
        raise ValueError(f"Unerwartete Struktur in {pfad.name}")

    kundmachung = _iso(md.get("pubdat", "")) or _iso(teile[4])
    inkrafttreten = _iso(md.get("ikra", "")) or _iso(teile[5])
    typ = typ or md.get("gldart", "")
    nummer = nummer or md.get("gldnr", "")

    ueberschriften: list[str] = []
    gliederung: list[str] = []
    absaetze: list[str] = []
    abschnitte: list[tuple[int, str]] = []  # (Textposition, Überschrift) in Dokumentreihenfolge
    laenge = 0
    for block, text in _bloecke(nd):
        if block is not None and block.tag == "ueberschrift":
            text = _OHNE_TITEL.sub("", text).strip(" -")
            if not text:
                continue
            (ueberschriften if block.get("typ", "") in _UEBERSCHRIFT_NORM else gliederung).append(text)
            abschnitte.append((laenge, text))
        else:
            absaetze.append(text)
            laenge += len(text) + 1

    return Norm(
        kuerzel=kuerzel,
        typ=typ,
        nummer=nummer,
        bgbl=_fundstelle(md, kundmachung),
        kundmachung=kundmachung,
        inkrafttreten=inkrafttreten,
        ueberschrift=" – ".join(ueberschriften),
        text="\n".join(absaetze),
        datei=f"{ORDNER}/{pfad.name}",
        abkuerzung=" ".join(md.get("abkrvo", "").split()),
        gesetz=" ".join(md.get("titrvo", "").split()),
        gliederung=" – ".join(gliederung),
        dokart=md.get("dokart", "").strip(),
        abschnitte=tuple(abschnitte),
    )


def quelldateien() -> list[Path]:
    ordner = config.datei(ORDNER)
    if not ordner.is_dir():
        return []
    return sorted(Path(e.path) for e in os.scandir(ordner) if e.name.endswith(".xml") and e.is_file())


def lade_alle() -> list[Norm]:
    """Alle Normen des Korpus (Momentaufnahme: genau eine Datei je Norm)."""
    return [lade_norm(p) for p in quelldateien()]


def schluessel(kuerzel: str) -> str:
    """Vergleichsschlüssel für Kürzel aus Dateiname oder `abkrvo` ("B-KUVG", "B_KUVG", "b-kuvg" → gleich)."""
    return re.sub(r"[\s_\-.,]+", "", kuerzel.casefold())


def nummer_schluessel(nummer: str) -> str:
    return re.sub(r"\s+", "", nummer.casefold())
