"""Erstattungskodex (EKO): Erstattungsstatus je PZN – nur administrativ (Box, Kennzeichen, Bewilligungspflicht).

Quelle: SV-Box `Medikamenten Erstattungskodex/`. Es gibt keine Auswahl-, Therapie- oder Dosierungsaussagen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from lotse import config
from lotse.models import Quelle
from lotse.pdfquellen import LEGENDE, info as pdf_info

ORDNER = "Medikamenten Erstattungskodex"
MEDIKAMENT = f"{ORDNER}/medikament.txt"
REGELTEXT = f"{ORDNER}/regeltext.txt"
INDTEXT = f"{ORDNER}/indtext.txt"
KODIERUNG = "cp1252"

# Feste Spalten in medikament.txt (Satzlänge 195)
_PZN = slice(0, 7)
_NAME = slice(18, 118)
_REST = 118
_ZEILE = re.compile(r"\|(\d{7})\|;\|(.*)\|", re.S)  # Text darf ";" enthalten


@dataclass(frozen=True)
class Legende:
    """Wörtlicher Eintrag der EKO-Zeichenerklärung (PDF-S. = Seite der Legenden-PDF)."""

    seite: int
    de: str
    en: str  # Übersetzung des deutschen Wortlauts


# Wortlaut laut „Zeichenerklärungen und Abkürzungen“ (EKO 1/2024); Test prüft Wörtlichkeit gegen die PDF.
_BOX: dict[str, Legende] = {
    "G": Legende(2, "Grüner Bereich des EKO", "Green area of the EKO"),
    "Y": Legende(4, "Gelber Bereich des EKO", "Yellow area of the EKO"),
}
_FACHGRUPPE_ERLAEUTERUNG = (
    Legende(
        1,
        "Die Aufnahme der Arzneispezialität in den Grünen Bereich des EKO bezieht sich auf eine oder mehrere "
        "ärztliche Fachgruppen.",
        "The inclusion of the medicinal product in the green area of the EKO refers to one or more medical "
        "specialist groups.",
    ),
    Legende(
        2,
        "Für Verordnungen außerhalb dieser Voraussetzungen ist eine ärztliche Bewilligung des chef- und "
        "kontrollärztlichen Dienstes einzuholen.",
        "For prescriptions outside these conditions, approval by the chief and control medical service "
        "(chef- und kontrollärztlicher Dienst) must be obtained.",
    ),
)
_FACHGRUPPE: dict[str, tuple[str, str]] = {
    "A": ("Lungenkrankheiten", "pulmonology"),
    "Au": ("Augenheilkunde", "ophthalmology"),
    "D": ("Haut- und Geschlechtskrankheiten", "dermatology and venereology"),
    "F": ("Frauenheilkunde und Geburtshilfe", "gynaecology and obstetrics"),
    "K": ("Kinderheilkunde", "paediatrics"),
    "L": ("Hals-, Nasen- und Ohrenkrankheiten", "ear, nose and throat"),
    "N": (
        "Neurologie oder Neurologie und Psychiatrie oder Psychiatrie und Neurologie oder Neuropädiatrie",
        "neurology, neurology and psychiatry, psychiatry and neurology, or neuropaediatrics",
    ),
    "P": (
        "Psychiatrie oder Psychiatrie und Neurologie oder Neurologie und Psychiatrie oder Kinder- und "
        "Jugendpsychiatrie",
        "psychiatry, psychiatry and neurology, neurology and psychiatry, or child and adolescent psychiatry",
    ),
    "R": ("Radiologie", "radiology"),
    "U": ("Urologie", "urology"),
}
_KENNZEICHEN: dict[str, Legende] = {
    "IND": Legende(
        2,
        "Die Arzneispezialität ist nur für die angegebenen Voraussetzungen in den jeweiligen Bereich des EKO "
        "aufgenommen. Das Vorliegen der angegebenen Voraussetzungen muss von der verordnenden Ärztin/vom "
        "verordnenden Arzt durch den Vermerk IND am Rezept bestätigt werden. Für Verordnungen außerhalb der "
        "angegebenen Voraussetzungen ist eine ärztliche Bewilligung des chef- und kontrollärztlichen Dienstes "
        "einzuholen.",
        "The medicinal product is included in the respective area of the EKO only for the stated conditions. "
        "The prescribing doctor must confirm that the stated conditions are met by noting IND on the "
        "prescription. For prescriptions outside the stated conditions, approval by the chief and control "
        "medical service must be obtained.",
    ),
    "RE1": Legende(
        3,
        "Die Arzneispezialitäten dürfen erst nach Vorliegen der ärztlichen Bewilligung des chef- und "
        "kontrollärztlichen Dienstes abgegeben werden. Für die Erteilung der ärztlichen Bewilligung des chef- "
        "und kontrollärztlichen Dienstes sind die angegebenen bestimmten Voraussetzungen maßgeblich.",
        "The medicinal products may only be dispensed once approval by the chief and control medical service "
        "has been granted. The specified conditions are decisive for granting this approval.",
    ),
    "RE2": Legende(
        3,
        "Bei diesen Arzneispezialitäten kann die sonst notwendige ärztliche Bewilligung des chef- und "
        "kontrollärztlichen Dienstes durch eine nachfolgende Kontrolle der Einhaltung der bestimmten "
        "Verwendungen ersetzt werden, wenn die angegebenen bestimmten Verwendungen vorliegen und eine den "
        "Richtlinien über die ökonomische Verschreibweise von Heilmitteln und Heilbehelfen entsprechende "
        "Dokumentation angefertigt wurde.",
        "For these medicinal products, the otherwise required approval by the chief and control medical service "
        "can be replaced by a subsequent check of compliance with the specified uses, if the specified uses "
        "apply and documentation in line with the guidelines on economical prescribing of medicines and "
        "medical aids has been prepared.",
    ),
    "F2J": Legende(
        2,
        "Die Arzneispezialität ist nur für die Behandlung von Kindern bis zum vollendeten 2. Lebensjahr in den "
        "Grünen Bereich des EKO aufgenommen.",
        "The medicinal product is included in the green area of the EKO only for children up to their 2nd "
        "birthday.",
    ),
    "F6J": Legende(
        2,
        "Die Arzneispezialität ist nur für die Behandlung von Kindern bis zum vollendeten 6. Lebensjahr in den "
        "Grünen Bereich des EKO aufgenommen.",
        "The medicinal product is included in the green area of the EKO only for children up to their 6th "
        "birthday.",
    ),
    "F14": Legende(
        2,
        "Die Arzneispezialität ist nur für die Behandlung von Kindern und Jugendlichen bis zum vollendeten 14. "
        "Lebensjahr in den Grünen Bereich des EKO aufgenommen.",
        "The medicinal product is included in the green area of the EKO only for children and adolescents up "
        "to their 14th birthday.",
    ),
}
_ALTER_ERLAEUTERUNG = Legende(
    2,
    "Für Verordnungen außerhalb der angegebenen Altersbeschränkung ist die Arzneispezialität wie eine "
    "Arzneispezialität des Gelben Bereichs des EKO zu behandeln",
    "For prescriptions outside the stated age limit, the medicinal product is treated like a product of the "
    "yellow area of the EKO",
)
_FACHGRUPPE_SEITE = 1

_HINWEIS = {
    "de": "Hinweis: Das ist nur der Erstattungsstatus laut Erstattungskodex. Über Verordnung und Bewilligung "
    "entscheiden die Ärztin bzw. der Arzt und der chef- und kontrollärztliche Dienst.",
    "en": "Note: this is only the reimbursement status according to the Austrian Reimbursement Code (EKO). "
    "Prescription and approval are decided by the doctor and the chief and control medical service.",
}


def legenden_eintraege() -> list[Legende]:
    """Alle hinterlegten Legendenzitate (für die Wörtlichkeitsprüfung)."""
    fach = [Legende(_FACHGRUPPE_SEITE, de, en) for de, en in _FACHGRUPPE.values()]
    return [*_BOX.values(), *_FACHGRUPPE_ERLAEUTERUNG, *fach, *_KENNZEICHEN.values(), _ALTER_ERLAEUTERUNG]


def legende_quelle(eintrag: Legende) -> Quelle:
    return Quelle(
        art="ekodex",
        titel=pdf_info(LEGENDE).titel,
        fundstelle=f"PDF-S. {eintrag.seite}",
        datei=LEGENDE,
        zitat=eintrag.de[:300],
    )


def _norm(text: str) -> str:
    return " ".join(text.split())


@dataclass(frozen=True)
class EkoEintrag:
    pzn: str
    name: str
    box: str  # "gruen" | "gelb"
    kennzeichen: list[str]
    packung: str
    regeltext: str
    indtext: str
    quelle: Quelle
    regel_quelle: Quelle | None = None
    ind_quelle: Quelle | None = None
    recht: tuple[Quelle, ...] = ()  # Rechtsgrundlagen zur Box (aus der Wissensbasis)

    @property
    def box_kuerzel(self) -> str:
        return "G" if self.box == "gruen" else "Y"

    def _legenden(self) -> list[tuple[str, Legende]]:
        """(Anzeigepräfix, Legendeneintrag) in Anzeigereihenfolge."""
        teile: list[tuple[str, Legende]] = [(self.box_kuerzel, _BOX[self.box_kuerzel])]
        fach = [k for k in self.kennzeichen if k in _FACHGRUPPE]
        for k in self.kennzeichen:
            if k in _KENNZEICHEN:
                teile.append((k, _KENNZEICHEN[k]))
        if any(k in ("F2J", "F6J", "F14") for k in self.kennzeichen):
            teile.append(("", _ALTER_ERLAEUTERUNG))
        for k in fach:
            de, en = _FACHGRUPPE[k]
            teile.append((k, Legende(_FACHGRUPPE_SEITE, de, en)))
        if fach:
            teile += [("", e) for e in _FACHGRUPPE_ERLAEUTERUNG]
        return teile

    def erklaerung(self, sprache: str = "de") -> str:
        """Bedeutung von Box und Kennzeichen laut EKO-Zeichenerklärung (rein administrativ, mit Fundstelle)."""
        en = sprache == "en"
        zeilen: list[str] = []
        for kz, eintrag in self._legenden():
            if en:
                ref = f"(EKO legend, PDF p. {eintrag.seite}; translated from German)"
                text = f"specialist group: {eintrag.en}" if kz in _FACHGRUPPE else eintrag.en
            else:
                ref = f"(Zeichenerklärung, PDF-S. {eintrag.seite})"
                text = f"Fachärztin/Facharzt für „{eintrag.de}“" if kz in _FACHGRUPPE else f"„{eintrag.de}“"
            zeilen.append(f"{kz + ': ' if kz else ''}{text} {ref}")
        for kz in self.kennzeichen:
            if kz not in _KENNZEICHEN and kz not in _FACHGRUPPE:
                zeilen.append(
                    f"{kz}: code not explained in the local EKO legend." if en
                    else f"{kz}: Kennzeichen in der lokalen Zeichenerklärung nicht erläutert."
                )
        for q in self.recht:
            if en:
                zeilen.append(f"{q.titel} ({q.fundstelle}), German original: „{q.zitat}“")
            else:
                zeilen.append(f"{q.titel} ({q.fundstelle}): „{q.zitat}“")
        zeilen.append(_HINWEIS["en" if en else "de"])
        return "\n".join(zeilen)

    def quellen(self) -> list[Quelle]:
        """Alle Belege: EKO-Zeile, Regel-/Indikationstext, Legendenseiten, Rechtsgrundlagen."""
        qs = [self.quelle]
        qs += [q for q in (self.regel_quelle, self.ind_quelle) if q is not None]
        gesehen: set[int] = set()
        for _, eintrag in self._legenden():
            if eintrag.seite not in gesehen:
                gesehen.add(eintrag.seite)
                qs.append(legende_quelle(eintrag))
        return qs + list(self.recht)


def _lies(rel: str) -> list[str]:
    """Zeilen einer CRLF-Datei; Zeilenumbrüche im Text bleiben dadurch unberührt."""
    with open(config.datei(rel), encoding=KODIERUNG, newline="") as f:
        return f.read().split("\r\n")


def _texte(rel: str) -> dict[str, tuple[int, str]]:
    """`|PZN|;|Text|` → {PZN: (Zeilennummer, Text)}."""
    texte: dict[str, tuple[int, str]] = {}
    for nr, zeile in enumerate(_lies(rel), 1):
        if not zeile:
            continue
        m = _ZEILE.fullmatch(zeile)
        if m is None:
            raise ValueError(f"{rel}, Zeile {nr}: unerwartetes Format")
        texte[m.group(1)] = (nr, _norm(m.group(2)))
    return texte


def _text_quelle(rel: str, pzn: str, nr: int, text: str, titel: str) -> Quelle:
    return Quelle(art="ekodex", titel=f"{titel} PZN {pzn}", fundstelle=f"{rel.split('/')[-1]}, Zeile {nr}",
                  datei=rel, zitat=text[:300])


def parse_zeile(zeile: str) -> tuple[str, str, str, list[str], str]:
    """Eine Satzzeile aus medikament.txt → (pzn, name, box, kennzeichen, packung)."""
    pzn = zeile[_PZN]
    if not pzn.isdigit():
        raise ValueError(f"Ungültige PZN: {pzn!r}")
    token = zeile[_REST:].split()
    if not token or token[0] not in ("G", "Y"):
        raise ValueError(f"PZN {pzn}: unbekannte Box {token[:1]}")
    kennzeichen: list[str] = []
    packung = ""
    for t in token[1:]:
        if t[0].isdigit():
            packung = t
            break
        kennzeichen.append(t)
    return pzn, _norm(zeile[_NAME]), "gruen" if token[0] == "G" else "gelb", kennzeichen, packung


class Erstattungskodex:
    def __init__(self, eintraege: list[EkoEintrag]):
        self.eintraege = eintraege
        self._pzn = {e.pzn: e for e in eintraege}
        self._namen = [(e.name.casefold(), e) for e in eintraege]
        self.recht: tuple[Quelle, ...] = ()  # Rechtsgrundlage Grüner Bereich, von der Wissensbasis gesetzt

    def __len__(self) -> int:
        return len(self.eintraege)

    def _mit_recht(self, e: EkoEintrag) -> EkoEintrag:
        return replace(e, recht=self.recht) if e.box == "gruen" and self.recht else e

    def pzn(self, pzn: str) -> EkoEintrag | None:
        e = self._pzn.get(pzn.strip().zfill(7))
        return self._mit_recht(e) if e else None

    def suche(self, begriff: str, k: int = 5) -> list[EkoEintrag]:
        """Exakte PZN oder Name (Anfang vor Teilwort, Groß-/Kleinschreibung egal)."""
        begriff = " ".join(begriff.split())
        if not begriff:
            return []
        if re.fullmatch(r"\d{1,8}", begriff.replace(" ", "")):
            e = self.pzn(begriff.replace(" ", ""))
            return [e] if e else []
        q = begriff.casefold()
        anfang = [e for n, e in self._namen if n.startswith(q)]
        teil = [e for n, e in self._namen if q in n and not n.startswith(q)]
        treffer = sorted(anfang, key=lambda e: e.name) + sorted(teil, key=lambda e: e.name)
        return [self._mit_recht(e) for e in treffer[:k]]


def lade() -> Erstattungskodex:
    """Lädt medikament.txt, regeltext.txt und indtext.txt (v1, cp1252)."""
    regel = _texte(REGELTEXT)
    ind = _texte(INDTEXT)
    eintraege: list[EkoEintrag] = []
    for nr, zeile in enumerate(_lies(MEDIKAMENT), 1):
        if not zeile.strip():
            continue
        pzn, name, box, kennzeichen, packung = parse_zeile(zeile)
        r = regel.get(pzn)
        i = ind.get(pzn)
        eintraege.append(EkoEintrag(
            pzn=pzn,
            name=name,
            box=box,
            kennzeichen=kennzeichen,
            packung=packung,
            regeltext=r[1] if r else "",
            indtext=i[1] if i else "",
            quelle=Quelle(
                art="ekodex",
                titel=f"Erstattungskodex (EKO) – {name}",
                fundstelle=f"medikament.txt, Zeile {nr}, PZN {pzn}",
                datei=MEDIKAMENT,
                zitat=_norm(zeile)[:300],
            ),
            regel_quelle=_text_quelle(REGELTEXT, pzn, *r, "EKO-Regeltext") if r else None,
            ind_quelle=_text_quelle(INDTEXT, pzn, *i, "EKO-Indikationstext") if i else None,
        ))
    return Erstattungskodex(eintraege)
