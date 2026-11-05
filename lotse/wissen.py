"""Wissensbasis: Rechtstexte, Leistungskataloge, Formulare und Erstattungskodex mit Suche und Rechtsstand-Auflösung.

Der geparste Korpus samt Index liegt als Pickle in `config.CACHE_DIR` und wird neu gebaut, sobald sich Anzahl oder
jüngste Änderungszeit der Quelldateien (oder dieser Module) ändern.
"""

from __future__ import annotations

import hashlib
import logging
import os
import pickle
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from lotse import config, ekodex as eko, pdfquellen, recht
from lotse.models import Quelle, Treffer
from lotse.recht import Norm, kuerze
from lotse.suche import Analysator, Index, ausschnitt, baue_vokabular, stuecke

log = logging.getLogger(__name__)

CACHE_VERSION = 2
CACHE_DATEI = "wissensbasis.pkl"
_QUELLORDNER = ("Rechtstexte", "Leistungskataloge", "Anträge und Formulare", "Medikamenten Erstattungskodex")
_MODULE = ("recht.py", "suche.py", "pdfquellen.py", "ekodex.py", "wissen.py")

# Ranking-Regeln
_MALUS_VERZEICHNIS = 0.3  # Inhaltsverzeichnisse sind Navigation, kein Beleg
_MALUS_ALTE_ANPASSUNG = 0.4  # Anpassungsverordnung eines anderen Jahres
_VORRANG_ANPASSUNG = 1.05  # geltende Anpassungsverordnung knapp vor der Grundnorm
_DUPLIKAT_DECKUNG = 0.8  # Wortmengen-Überdeckung, ab der zwei Fassungen derselben Norm als Duplikat gelten
# Zielgruppe Bürger:innen: Dienst-, Geschäfts- und Abrechnungsordnungen der Träger sowie zwischenstaatliche
# Abkommen sind nachrangig (Gewichtung nach metadaten/@dokart).
_DOKART_GEWICHT = {
    "DO": 0.5, "GO": 0.5, "AnhGO": 0.5, "PO": 0.5, "Weisung": 0.5, "Abrechnungsregeln": 0.5, "PauschBetr": 0.5,
    "IntR": 0.5, "MusterR": 0.6, "DSV": 0.6, "SVAbk": 0.7, "Handbuch": 0.7, "V Eur": 0.8, "E Eur": 0.8,
}

# "Die Beträge, die für das Kalenderjahr 2026 an die Stelle der im § 5 Abs. 1 BPGG genannten Beträge treten"
_ANPASSUNG = re.compile(
    r"für das Kalenderjahr (\d{4}) an die Stelle der im § (\d+[a-z]?) Abs\. (\d+) (.{2,60}?) genannten Beträge"
)
_STUFE = re.compile(r"Stufe\s*(\d)\s*statt\s*([\d\s.]+,\d{2})\s*€\s*\.?\s*mit\s*([\d\s.]+,\d{2})\s*€")
_JAHR = re.compile(r"\b(19[5-9]\d|20\d\d)\b")
_BETRAG_TERME = ("höhe", "betrag", "beträge", "viel", "euro", "amount", "much")


@dataclass(frozen=True)
class Dok:
    """Suchstück: Textbereich [von, bis) einer Norm oder einer PDF-Seite."""

    art: str
    norm: int = -1  # Index in `normen` bei art="recht"
    datei: str = ""  # PDF relativ zu DATA_DIR
    seite: int = 0  # 1-basiert
    von: int = 0
    bis: int = 0
    gewicht: float = 1.0  # Vorab-Gewichtung (Zielgruppe, Verzeichnis)

    @property
    def einheit(self) -> tuple:
        """Belegeinheit: eine Norm oder eine PDF-Seite."""
        return ("n", self.norm) if self.norm >= 0 else ("p", self.datei, self.seite)


@dataclass(frozen=True)
class Anpassung:
    """Verordnung, die Beträge einer Grundnorm für ein Kalenderjahr ersetzt."""

    basis: tuple[str, str]  # (Kürzel-Schlüssel, §-Nummer) der Grundnorm, z. B. ("bpgg", "5")
    jahr: int
    norm: int


@dataclass
class PflegegeldAuskunft:
    jahr: int
    betraege: dict[int, float]  # Stufe 1..7 → € monatlich; leer, wenn lokal nicht belegt
    quellen: list[Quelle]
    hinweis: dict[str, str]
    belege: dict[int, str] = field(default_factory=dict)  # Stufe → wörtliche Zeile der Verordnung


def _signatur() -> tuple:
    """Anzahl und jüngste Änderungszeit je Quellordner plus Stand der Wissensmodule."""
    teile: list = [CACHE_VERSION]
    for ordner in _QUELLORDNER:
        pfad = config.datei(ordner)
        anzahl, juengste = 0, 0
        if pfad.is_dir():
            for e in os.scandir(pfad):
                if e.is_file():
                    anzahl += 1
                    juengste = max(juengste, e.stat().st_mtime_ns)
        teile.append((ordner, anzahl, juengste))
    hier = Path(__file__).resolve().parent
    teile.append(max((hier / m).stat().st_mtime_ns for m in _MODULE))
    return tuple(teile)


def _betrag(text: str) -> float:
    """"1 206,90" → 1206.9"""
    return float(re.sub(r"[\s.]", "", text).replace(",", "."))


def _woerter_menge(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


class Wissensbasis:
    def __init__(
        self,
        normen: list[Norm],
        pdfs: dict[str, list[str]],
        kodex: eko.Erstattungskodex,
        doks: list[Dok],
        index: Index,
        anpassungen: list[Anpassung],
    ):
        self.normen = normen
        self.pdfs = pdfs
        self.kodex = kodex
        self.doks = doks
        self.index = index
        self.anpassungen = anpassungen
        self.ladezeit = 0.0  # Sekunden
        self.aus_cache = False
        self._normschluessel: dict[tuple[str, str, str], int] = {}
        for i, n in enumerate(normen):
            for k in {recht.schluessel(n.kuerzel), recht.schluessel(n.abkuerzung)} - {""}:
                self._normschluessel.setdefault((k, n.typ.upper(), recht.nummer_schluessel(n.nummer)), i)
        self._einheit_doks: dict[tuple, list[int]] = {}
        for d, dok in enumerate(doks):
            self._einheit_doks.setdefault(dok.einheit, []).append(d)
        # Exakt gleiche Normtexte (mehrfach abgelegte Übersichten) teilen sich einen Schlüssel
        self._textschluessel = {
            i: hashlib.blake2b(n.text.encode(), digest_size=8).digest() for i, n in enumerate(normen) if n.text
        }
        self._anpassung_normen = {a.norm for a in anpassungen}
        # Rechtsgrundlage zum Grünen Bereich des EKO: RöV 2024 § 5 Abs. 1 vollständig (in Zitaten ≤ 300 Zeichen)
        gruen = self.norm("RoeV_2024", "5")
        if gruen:
            absatz1 = gruen.text.split("\n(2)")[0]
            self.kodex.recht = tuple(gruen.quelle(z) for z in _zeilenpakete(absatz1))

    # -- Bau -------------------------------------------------------------------------------------------------

    @classmethod
    def baue(cls) -> Wissensbasis:
        normen = recht.lade_alle()
        pdfs = pdfquellen.lade_alle()
        kodex = eko.lade()
        doks: list[Dok] = []
        texte: list[tuple[str, str]] = []  # (Kopf, Rumpf) je Dok, nur für den Indexbau
        for i, n in enumerate(normen):
            if n.aufgehoben or not n.text:
                continue
            kontext = f"{n.abkuerzung or n.kuerzel}\n{n.gesetz}\n"
            gewicht = _DOKART_GEWICHT.get(n.dokart.strip(), 1.0) * (_MALUS_VERZEICHNIS if n.typ == "INH" else 1.0)
            for von, bis in stuecke(n.text):
                doks.append(Dok(art="recht", norm=i, von=von, bis=bis, gewicht=gewicht))
                texte.append((n.kopf_bei(bis), kontext + n.text[von:bis]))
        for datei, seiten in pdfs.items():
            info = pdfquellen.info(datei)
            kapitel = pdfquellen.inhaltsverzeichnis(seiten, datei)
            for nr, text in enumerate(seiten, 1):
                if not text:
                    continue
                # Formulartitel gilt für jede Seite des Formulars; sonst Kapitel laut Inhaltsverzeichnis
                kopf = " ".join(kapitel.get(nr, [])) + (f" {info.titel}" if info.art == "formular" else "")
                gewicht = _MALUS_VERZEICHNIS if pdfquellen.ist_verzeichnis(text) else 1.0
                for von, bis in stuecke(text):
                    doks.append(Dok(art=info.art, datei=datei, seite=nr, von=von, bis=bis, gewicht=gewicht))
                    texte.append((kopf, f"{info.titel}\n{text[von:bis]}"))
        analysator = Analysator(baue_vokabular([k + " " + r for k, r in texte]))
        index = Index(analysator)
        index.baue(texte)
        return cls(normen, pdfs, kodex, doks, index, _finde_anpassungen(normen))

    # -- Abfragen --------------------------------------------------------------------------------------------

    def _norm_index(self, kuerzel: str, nummer: str, typ: str = "PARA") -> int | None:
        return self._normschluessel.get((recht.schluessel(kuerzel), typ.upper(), recht.nummer_schluessel(nummer)))

    def norm(self, kuerzel: str, nummer: str, typ: str = "PARA") -> Norm | None:
        """Norm nach Kürzel (Dateiname oder amtliche Abkürzung), Nummer und Gliederungsart."""
        i = self._norm_index(kuerzel, nummer, typ)
        return self.normen[i] if i is not None else None

    def pdf_seite(self, datei: str, seite: int) -> str:
        """Normalisierter Text einer PDF-Seite (1-basiert). KeyError/IndexError bei unbekannter Datei/Seite."""
        seiten = self.pdfs[datei]
        if not 1 <= seite <= len(seiten):
            raise IndexError(f"{datei}: Seite {seite} nicht vorhanden (1–{len(seiten)})")
        return seiten[seite - 1]

    def ekodex(self, suchbegriff: str, k: int = 5) -> list[eko.EkoEintrag]:
        """Erstattungskodex nach exakter PZN oder Name (Anfang/Teilwort)."""
        return self.kodex.suche(suchbegriff, k)

    def suche(self, frage: str, k: int = 5, arten: set[str] | None = None) -> list[Treffer]:
        """Top-k-Belege (je Norm bzw. PDF-Seite höchstens einer) aus Recht und PDFs; `arten` filtert die Quellenart."""
        gewichte = self.index.analysator.anfrage(frage)
        if not gewichte or k <= 0:
            return []
        # bestes Stück je Belegeinheit
        beste: dict[tuple, tuple[float, int]] = {}
        for d, p in self.index.bewerte(gewichte).items():
            dok = self.doks[d]
            if arten is not None and dok.art not in arten:
                continue
            p *= dok.gewicht
            if p > beste.get(dok.einheit, (0.0, -1))[0]:
                beste[dok.einheit] = (p, d)
        self._rechtsstand(frage, gewichte, beste)
        reihenfolge = sorted(beste, key=lambda e: (-beste[e][0], beste[e][1]))
        return [self._treffer(beste[e][1], beste[e][0], gewichte) for e in self._ohne_duplikate(reihenfolge, k)]

    def _rechtsstand(self, frage: str, gewichte: dict[str, float], beste: dict[tuple, tuple[float, int]]) -> None:
        """Rechtsstand-Regel: die Anpassungsverordnung des Zieljahres schlägt die Grundnorm, ältere fallen zurück."""
        jahre = [int(j) for j in _JAHR.findall(frage)]
        betrag_frage = bool(jahre) or any(self.index.analysator.stamm(w) in gewichte for w in _BETRAG_TERME)
        for basis in {a.basis for a in self.anpassungen}:
            verfuegbar = [a for a in self.anpassungen if a.basis == basis]
            ziel_jahr = jahre[-1] if jahre else min(date.today().year, max(a.jahr for a in verfuegbar))
            for a in verfuegbar:
                e = ("n", a.norm)
                if e in beste and a.jahr != ziel_jahr:
                    beste[e] = (beste[e][0] * _MALUS_ALTE_ANPASSUNG, beste[e][1])
            i_basis = self._norm_index(*basis)
            e_basis = ("n", i_basis)
            if not betrag_frage or e_basis not in beste:
                continue
            for a in verfuegbar:
                e = ("n", a.norm)
                if a.jahr != ziel_jahr or e not in self._einheit_doks:
                    continue
                vorrang = beste[e_basis][0] * _VORRANG_ANPASSUNG
                if e not in beste:
                    beste[e] = (vorrang, self._einheit_doks[e][0])
                elif beste[e][0] < vorrang:
                    beste[e] = (vorrang, beste[e][1])

    def _ohne_duplikate(self, einheiten: list[tuple], k: int) -> list[tuple]:
        """Mehrfach abgelegte Fassungen derselben Norm nur einmal zeigen (gleicher Text oder gleiche Fundstelle
        und Nummer bei weitgehend gleichem Wortbestand)."""
        auswahl: list[tuple] = []
        mengen: dict[int, set[str]] = {}
        for e in einheiten:
            if e[0] == "n" and any(o[0] == "n" and self._duplikat(e[1], o[1], mengen) for o in auswahl):
                continue
            auswahl.append(e)
            if len(auswahl) == k:
                break
        return auswahl

    def _duplikat(self, i: int, j: int, mengen: dict[int, set[str]]) -> bool:
        if self._textschluessel.get(i) == self._textschluessel.get(j):
            return True
        a, b = self.normen[i], self.normen[j]
        if (a.bgbl, a.typ, a.nummer) != (b.bgbl, b.typ, b.nummer):
            return False
        wa = mengen.setdefault(i, _woerter_menge(a.text))
        wb = mengen.setdefault(j, _woerter_menge(b.text))
        return bool(wa and wb) and len(wa & wb) / min(len(wa), len(wb)) >= _DUPLIKAT_DECKUNG

    def _treffer(self, d: int, score: float, gewichte: dict[str, float]) -> Treffer:
        """Treffer mit wörtlichem Zitat (≤ 300 Zeichen) und Kontext aus dem besten Suchstück."""
        dok = self.doks[d]
        if dok.norm >= 0:
            n = self.normen[dok.norm]
            if dok.norm in self._anpassung_normen:
                # Anpassungsverordnung: Zitat zeigt die festgestellten Beträge ab „Die Beträge, die für …“
                start = n.text.rfind("\n", 0, max(0, n.text.find("an die Stelle"))) + 1
                return Treffer(quelle=n.quelle(n.text[start:]), text=kuerze(n.text[start:], 1200),
                               score=round(score, 4))
            zitat, kontext = ausschnitt(self.index.analysator, n.text[dok.von:dok.bis], gewichte, self.index.idf)
            return Treffer(quelle=n.quelle(zitat), text=kontext, score=round(score, 4))
        text = self.pdfs[dok.datei][dok.seite - 1][dok.von:dok.bis]
        zitat, kontext = ausschnitt(self.index.analysator, text, gewichte, self.index.idf)
        return Treffer(quelle=pdfquellen.quelle(dok.datei, dok.seite, zitat), text=kontext, score=round(score, 4))

    # -- Pflegegeld ------------------------------------------------------------------------------------------

    def pflegegeld(self, jahr: int = 2026) -> PflegegeldAuskunft:
        """Pflegegeld-Monatsbeträge eines Jahres aus der Anpassungsverordnung; nie die Grundbeträge aus § 5 BPGG."""
        grundnorm = self.norm("BPGG", "5")
        basis_quelle = grundnorm.quelle(next(
            (z for z in grundnorm.text.split("\n") if "durch Verordnung festzustellen" in z), grundnorm.text
        )) if grundnorm else None
        kandidaten: list[tuple[Norm, dict[int, float], dict[int, str]]] = []
        for a in self.anpassungen:
            if a.basis != ("bpgg", "5") or a.jahr != jahr:
                continue
            n = self.normen[a.norm]
            betraege, belege = _pflegegeld_betraege(n.text)
            if len(betraege) == 7:
                kandidaten.append((n, betraege, belege))
        if not kandidaten:
            # nur Jahre mit vollständigen Euro-Beträgen (BPGGAnpV 1994 nennt Schilling)
            jahre = sorted({
                a.jahr for a in self.anpassungen
                if a.basis == ("bpgg", "5") and len(_pflegegeld_betraege(self.normen[a.norm].text)[0]) == 7
            })
            liste = ", ".join(map(str, jahre)) or "–"
            return PflegegeldAuskunft(
                jahr=jahr,
                betraege={},
                quellen=[basis_quelle] if basis_quelle else [],
                hinweis={
                    "de": f"Die Pflegegeld-Beträge für {jahr} sind in den lokalen Quellen nicht enthalten "
                    f"(lokal belegt: {liste}). § 5 BPGG enthält nur Grundbeträge, die jährlich durch Verordnung "
                    f"festgestellt werden; die für {jahr} geltende Verordnung ist lokal nicht vorhanden.",
                    "en": f"The care allowance (Pflegegeld) amounts for {jahr} are not contained in the local "
                    f"sources (available locally: {liste}). § 5 BPGG only contains base amounts that are set "
                    f"annually by regulation; the regulation for {jahr} is not available locally.",
                },
            )
        n, betraege, belege = max(kandidaten, key=lambda x: (x[0].kundmachung, x[0].datei))
        start = n.text.find("§ 1.")
        vo_quelle = n.quelle(n.text[start:] if start >= 0 else n.text)
        quellen = [vo_quelle] + ([basis_quelle] if basis_quelle else [])
        return PflegegeldAuskunft(
            jahr=jahr,
            betraege=betraege,
            quellen=quellen,
            belege=belege,
            hinweis={
                "de": f"Monatliche Pflegegeld-Beträge {jahr} laut {n.titel} ({n.bgbl}). Sie treten an die Stelle "
                "der Grundbeträge in § 5 Abs. 1 BPGG, die nach § 5 Abs. 2 und 3 BPGG jährlich durch Verordnung "
                "angepasst werden.",
                "en": f"Monthly care allowance (Pflegegeld) amounts for {jahr} according to {n.titel} ({n.bgbl}). "
                "They replace the base amounts in § 5 (1) BPGG, which are adjusted annually by regulation under "
                "§ 5 (2) and (3) BPGG.",
            },
        )


def _zeilenpakete(text: str, laenge: int = recht.ZITAT_MAX) -> list[str]:
    """Aufeinanderfolgende Zeilen zu wörtlichen Zitaten ≤ `laenge` bündeln (überlange Zeilen werden gekürzt)."""
    pakete: list[str] = []
    for zeile in (" ".join(z.split()) for z in text.split("\n")):
        if pakete and len(pakete[-1]) + 1 + len(zeile) <= laenge:
            pakete[-1] += " " + zeile
        elif zeile:
            pakete.append(kuerze(zeile, laenge))
    return pakete


def _pflegegeld_betraege(text: str) -> tuple[dict[int, float], dict[int, str]]:
    """"in Stufe 3 statt 577,00 € mit 592,60 €" → {3: 592.6} plus wörtliche Zeile je Stufe."""
    betraege: dict[int, float] = {}
    belege: dict[int, str] = {}
    for zeile in text.split("\n"):
        for m in _STUFE.finditer(zeile):
            stufe = int(m.group(1))
            betraege[stufe] = _betrag(m.group(3))
            belege[stufe] = kuerze(zeile)
    return betraege, belege


def _finde_anpassungen(normen: list[Norm]) -> list[Anpassung]:
    """Verordnungen der Form „für das Kalenderjahr J an die Stelle der im § n Abs. m <Gesetz> genannten Beträge“."""
    gesetze: dict[str, str] = {}
    for n in normen:
        k = recht.schluessel(n.kuerzel)
        for name in (n.abkuerzung, n.gesetz):
            gesetze.setdefault(recht.schluessel(name), k)
    funde: list[Anpassung] = []
    for i, n in enumerate(normen):
        if "an die Stelle" not in n.text:
            continue
        for m in _ANPASSUNG.finditer(" ".join(n.text.split())):
            gesetz = re.sub(r"^(des|der)\s+", "", m.group(4))
            k = gesetze.get(recht.schluessel(gesetz)) or gesetze.get(recht.schluessel(re.sub(r"e?s$", "", gesetz)))
            if k:
                funde.append(Anpassung(basis=(k, recht.nummer_schluessel(m.group(2))), jahr=int(m.group(1)), norm=i))
    return funde


# -- Singleton mit Pickle-Cache ------------------------------------------------------------------------------

_INSTANZ: Wissensbasis | None = None
_SPERRE = threading.Lock()


def _lade_cache(pfad: Path, signatur: tuple) -> Wissensbasis | None:
    try:
        with open(pfad, "rb") as f:
            inhalt = pickle.load(f)
    except (OSError, pickle.UnpicklingError, EOFError, AttributeError, ImportError, TypeError):
        return None
    if not isinstance(inhalt, dict) or inhalt.get("signatur") != signatur:
        return None
    return inhalt.get("wissensbasis")


def _schreibe_cache(pfad: Path, signatur: tuple, wb: Wissensbasis) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump({"signatur": signatur, "wissensbasis": wb}, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, pfad)


def wissensbasis() -> Wissensbasis:
    """Gemeinsame, beim ersten Aufruf geladene Wissensbasis (Pickle-Cache, sonst Neuaufbau)."""
    global _INSTANZ
    if _INSTANZ is not None:
        return _INSTANZ
    with _SPERRE:
        if _INSTANZ is not None:
            return _INSTANZ
        if not config.daten_vorhanden():
            raise FileNotFoundError(f"SV-Box-Quelldaten fehlen unter {config.DATA_DIR} (LOTSE_DATA_DIR setzen)")
        start = time.perf_counter()
        signatur = _signatur()
        pfad = config.CACHE_DIR / CACHE_DATEI
        wb = _lade_cache(pfad, signatur)
        if wb is not None:
            wb.aus_cache = True
        else:
            wb = Wissensbasis.baue()
            _schreibe_cache(pfad, signatur, wb)
        wb.ladezeit = time.perf_counter() - start
        log.info("Wissensbasis %s in %.2f s", "aus Cache" if wb.aus_cache else "neu gebaut", wb.ladezeit)
        _INSTANZ = wb
        return wb
