"""Gemeinsame Datentypen aller Module. Änderungen hier betreffen alle Module."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Sprache = Literal["de", "en"]
Stil = Literal["einfach", "ausfuehrlich"]
QuellenArt = Literal["recht", "serviceratgeber", "formular", "dokument", "ekodex", "honorarordnung", "extern"]

# Themen-IDs, die die Dokumentfunktion erkennt und der Leistungskatalog als `id` führt.
THEMEN: dict[str, str] = {
    "pflegegeld": "Pflegegeld",
    "rehabilitation": "Rehabilitation",
    "hauskrankenpflege": "Medizinische Hauskrankenpflege",
    "fahrtkosten": "Fahrtkosten/Transport zu Behandlungen",
    "rezeptgebuehrenbefreiung": "Rezeptgebührenbefreiung",
    "pflege_zu_hause": "Pflege und Betreuung zu Hause",
}

# Formular-IDs (Registry in lotse/data/formulare/<ID>.json).
FORMULARE: dict[str, str] = {
    "PAL080": "Anträge und Formulare/PAL080_0125_Mpfl_052026.pdf",
    "KUR1": "Anträge und Formulare/Antrag Kur und Reha.pdf",
    "FAHRTKOSTEN_OEGK_WIEN": "Anträge und Formulare/Antrag-auf-Zuschuss-zu-Fahrtkosten_Wien.pdf",
    "FSW_FOERDERUNG": "Anträge und Formulare/fsw-antrag-auf-foerderung-von-leistungen.1779095804.pdf",
    "FSW_WG": "Anträge und Formulare/Bedarfsmeldung-Senior_innen-Wohngemeinschaft_Basispaket.1736522017.pdf",
    "FSW_EINRICHTUNG": "Anträge und Formulare/FSW-Antrag-Beilage-Einrichtungswunsch.1779345450.pdf",
    "REHA_UNFALL": "Anträge und Formulare/Reha_n_Unfall_052026.pdf",
}


@dataclass(frozen=True)
class Quelle:
    """Beleg für eine Aussage. `datei` relativ zu DATA_DIR; `stand` ISO-Datum oder "" (unbekannt)."""

    art: QuellenArt
    titel: str  # z. B. "BPGG § 5", "ÖGK – Leistungen und Services 2026", "PAL 080 (01.2025)"
    fundstelle: str = ""  # z. B. "S. 23", "BGBl. II Nr. 263/2025"
    datei: str = ""
    zitat: str = ""  # wörtlich, höchstens 300 Zeichen
    stand: str = ""
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Treffer:
    quelle: Quelle
    text: str
    score: float


@dataclass(frozen=True)
class Empfehlung:
    """Ausdrücklich dokumentierte Empfehlung/Aufgabe aus einem hochgeladenen Dokument."""

    thema: str  # Schlüssel aus THEMEN
    zitat: str  # wörtlich aus dem Dokument
    seite: int  # 1-basiert
    quelle: Quelle

    def to_dict(self) -> dict:
        return {"thema": self.thema, "zitat": self.zitat, "seite": self.seite, "quelle": self.quelle.to_dict()}


@dataclass(frozen=True)
class Stammdatum:
    """Administratives Datum aus einem Dokument (nie Diagnosen/Befunde)."""

    slot: str  # Slot-ID aus lotse.slots
    wert: str
    seite: int
    zitat: str


@dataclass(frozen=True)
class Grenzentscheidung:
    erlaubt: bool
    kategorie: str | None = None  # diagnose | befund | risiko | therapie | medikament | dosis
    antwort: dict[str, str] = field(default_factory=dict)  # {"de": ..., "en": ...}

    def to_dict(self) -> dict:
        return asdict(self)
