"""Leistungskatalog: lädt `lotse/data/leistungen.json` und `lotse/data/termine.json`, filtert nach Szenario und Region,
erkennt Szenarien und passende Leistungen im Freitext.

Jede Leistung trägt ihre Quellen. `beleg="extern"` heißt: Kernaussagen nicht lokal geprüft (z. B. „Bewegt im Park“).
Einrichtungen, regionale Stellen, Nutzen und Trägerzuständigkeit tragen jeweils einen eigenen Beleg. `leicht` umschreibt
kurz/details/voraussetzungen/schritte in Leichter Sprache ohne neue Inhalte und wird beim Laden geprüft (`pruefe_leichte_sprache`).
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import get_args

from lotse import config
from lotse.models import FORMULARE, QuellenArt, Quelle
from lotse.slots import BUNDESLAENDER, SLOTS

SZENARIEN: tuple[str, ...] = ("pflege", "gesundheit", "entlassung", "kind", "unterstuetzung")
BEREICHE: tuple[str, ...] = ("A", "B", "C", "D", "E", "F")  # Bereiche laut Use Case
# Leistungen mit Formular führen diese Schritt-IDs in dieser Reihenfolge (Fallakte baut darauf auf).
ANTRAGSSCHRITTE: tuple[str, ...] = ("antrag_ausfuellen", "antrag_unterschreiben", "antrag_einreichen")
DATEI = config.PAKET_DATEN / "leistungen.json"
TERMIN_DATEI = config.PAKET_DATEN / "termine.json"
TERMIN_ANLAESSE: tuple[str, ...] = SLOTS["termin.anlass"].optionen
_SPRACHEN = ("de", "en")
_QUELLEN_ARTEN = set(get_args(QuellenArt))
_PFLICHTFELDER = ("stichworte", "nutzen", "nutzen_quelle", "einrichtungen", "regional", "formular_regionen", "termin_anlass",
                  "unterlagen_formular", "leicht")


class KatalogFehler(ValueError):
    """Ungültiger Eintrag in leistungen.json oder termine.json."""


@dataclass(frozen=True)
class Leistung:
    id: str
    titel: dict[str, str]
    kurz: dict[str, str]  # einfache Sprache, höchstens zwei Sätze
    leicht: dict[str, str]  # Leichte Sprache, 2–4 kurze Sätze; nur Inhalte (und Zahlen) aus kurz/details/voraussetzungen/schritte
    details: dict[str, str]
    bereiche: list[str]
    szenarien: list[str]
    stelle: dict  # {"name": {de,en}, "kontakt": str, "hinweis": {de,en}}
    stelle_nach: dict[str, dict[str, dict[str, str]]]  # slot_id → Slot-Wert → {de,en}
    regionen: list[str]  # [] = österreichweit
    formular: str | None
    rueckfragen: list[str]
    unterlagen: list[dict[str, str]]
    voraussetzungen: list[dict[str, str]]
    schritte: list[dict[str, str]]  # {"id", "de", "en"}
    quellen: list[Quelle]
    beleg: str  # "lokal" | "extern" (nur Kernaussagen aus `quellen`)
    stichworte: list[str]  # Kleinbuchstaben, Wortanfänge für passende_leistungen
    nutzen: dict[str, str]  # {de,en}, beide leer erlaubt
    nutzen_quelle: Quelle | None
    einrichtungen: list[dict]  # {"name": {de,en}, "regionen", "kontakt", "url", "quelle"}
    regional: dict[str, dict]  # Bundesland → {"stelle": {de,en}, "kontakt", "url", "quelle"}
    formular_regionen: list[str]  # [] = Formular gilt überall
    termin_anlass: str | None  # Wert von termin.anlass
    stelle_belege: dict[str, dict[str, Quelle]]  # slot_id → Slot-Wert → Beleg der aufgelösten Stelle
    stelle_kontakte: dict[str, dict[str, str]]  # slot_id → Slot-Wert → Kontakt der aufgelösten Stelle
    unterlagen_formular: list[dict[str, str]]  # Unterlagen nur für das Formular (gilt wie formular_regionen)

    @property
    def oesterreichweit(self) -> bool:
        return not self.regionen

    def stelle_fuer(self, werte: dict[str, str]) -> dict[str, str]:
        """Zuständige Stelle {de, en} für die bekannten Slot-Werte; ohne passenden Wert `stelle["name"]`."""
        for slot_id, je_wert in self.stelle_nach.items():
            wert = werte.get(slot_id)
            if wert in je_wert:
                return je_wert[wert]
        return self.stelle["name"]

    def stelle_beleg_fuer(self, werte: dict[str, str]) -> Quelle | None:
        """Beleg zur Stelle, die `stelle_fuer` liefert (z. B. svs.at); None ohne eigenen Beleg."""
        for slot_id, je_wert in self.stelle_nach.items():
            wert = werte.get(slot_id)
            if wert in je_wert:
                return self.stelle_belege.get(slot_id, {}).get(wert)
        return None

    def kontakt_fuer(self, werte: dict[str, str]) -> str:
        """Kontakt zur Stelle, die `stelle_fuer` liefert (z. B. SVS); ohne eigenen Eintrag `stelle["kontakt"]`."""
        for slot_id, je_wert in self.stelle_nach.items():
            wert = werte.get(slot_id)
            if wert in je_wert:
                return self.stelle_kontakte.get(slot_id, {}).get(wert, self.stelle["kontakt"])
        return self.stelle["kontakt"]

    def regional_fuer(self, bundesland: str | None) -> dict | None:
        """Regionale Stelle bzw. regionales Angebot für das Bundesland; None ohne Bundesland oder Eintrag."""
        if not bundesland:
            return None
        return self.regional.get(_bundesland(bundesland))

    def einrichtungen_fuer(self, bundesland: str | None) -> list[dict]:
        """Einrichtungen und Suchdienste: zuerst die des Bundeslandes, dann österreichweite; ohne Land nur österreichweite."""
        bundesweit = [e for e in self.einrichtungen if not e["regionen"]]
        if not bundesland:
            return bundesweit
        land = _bundesland(bundesland)
        return [e for e in self.einrichtungen if land in e["regionen"]] + bundesweit

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TerminInfo:
    """Wohin für einen Termin, was mitnehmen, wo suchen – mit Belegen; keine medizinische Einschätzung."""

    anlass: str
    wo: dict[str, str]
    hinweise: list[dict[str, str]]
    suche: list[dict]  # {"name": {de,en}, "url", "regionen", "quelle"}
    quellen: list[Quelle]
    beschwerden_hinweis: dict[str, str]  # nur bei anlass "beschwerden" nicht leer

    def to_dict(self) -> dict:
        return asdict(self)


# --- Laden und Prüfen -------------------------------------------------------------------------

def _text(wert, wo: str, leer_erlaubt: bool = False) -> dict[str, str]:
    if not isinstance(wert, dict):
        raise KatalogFehler(f"{wo}: Objekt mit de/en erwartet")
    for sprache in _SPRACHEN:
        inhalt = wert.get(sprache)
        if not isinstance(inhalt, str) or (not leer_erlaubt and not inhalt.strip()):
            raise KatalogFehler(f"{wo}: Text für „{sprache}“ fehlt")
    if leer_erlaubt and bool(wert["de"].strip()) != bool(wert["en"].strip()):
        raise KatalogFehler(f"{wo}: de und en nur gemeinsam leer")
    return {s: wert[s] for s in _SPRACHEN}


def _texte(liste, wo: str) -> list[dict[str, str]]:
    if not isinstance(liste, list):
        raise KatalogFehler(f"{wo}: Liste erwartet")
    return [_text(eintrag, f"{wo}[{i}]") for i, eintrag in enumerate(liste)]


def _quelle(q, wo: str) -> Quelle:
    if not isinstance(q, dict):
        raise KatalogFehler(f"{wo}: Quelle muss ein Objekt sein")
    try:
        quelle = Quelle(**q)
    except TypeError as fehler:
        raise KatalogFehler(f"{wo}: {fehler}") from None
    if quelle.art not in _QUELLEN_ARTEN:
        raise KatalogFehler(f"{wo}: unbekannte Quellenart „{quelle.art}“")
    if not quelle.titel.strip():
        raise KatalogFehler(f"{wo}: Titel fehlt")
    if len(quelle.zitat) > 300:
        raise KatalogFehler(f"{wo}: Zitat länger als 300 Zeichen")
    if quelle.art == "extern":
        if not quelle.url.startswith("http"):
            raise KatalogFehler(f"{wo}: externe Quelle braucht eine URL")
        if not quelle.zitat.strip():
            raise KatalogFehler(f"{wo}: externe Quelle braucht ein Zitat")
    else:
        if not (quelle.datei and quelle.fundstelle and quelle.zitat):
            raise KatalogFehler(f"{wo}: lokale Quelle braucht datei, fundstelle und zitat")
        if quelle.url:
            raise KatalogFehler(f"{wo}: URL nur bei externen Quellen")
    return quelle


def _slot_id(slot_id: str, wo: str) -> str:
    if slot_id not in SLOTS:
        raise KatalogFehler(f"{wo}: unbekannte Slot-ID „{slot_id}“")
    return slot_id


def _laender(werte, wo: str) -> list[str]:
    if not isinstance(werte, list) or any(r not in BUNDESLAENDER for r in werte) or len(set(werte)) != len(werte):
        raise KatalogFehler(f"{wo}: unbekanntes oder doppeltes Bundesland in {werte}")
    return list(werte)


def _str(wert, wo: str) -> str:
    if not isinstance(wert, str):
        raise KatalogFehler(f"{wo}: Text erwartet")
    return wert


def _url(wert, wo: str) -> str:
    url = _str(wert, wo)
    if url and not url.startswith(("https://", "http://")):
        raise KatalogFehler(f"{wo}: ungültige URL „{url}“")
    return url


def _einrichtungen(liste, wo: str) -> list[dict]:
    if not isinstance(liste, list):
        raise KatalogFehler(f"{wo}: Liste erwartet")
    ergebnis = []
    for i, e in enumerate(liste):
        stelle = f"{wo}[{i}]"
        if not isinstance(e, dict):
            raise KatalogFehler(f"{stelle}: Objekt erwartet")
        ergebnis.append({
            "name": _text(e.get("name"), f"{stelle}.name"),
            "regionen": _laender(e.get("regionen", []), f"{stelle}.regionen"),
            "kontakt": _str(e.get("kontakt", ""), f"{stelle}.kontakt"),
            "url": _url(e.get("url", ""), f"{stelle}.url"),
            "quelle": _quelle(e.get("quelle"), f"{stelle}.quelle"),
        })
    return ergebnis


def _regional(roh, regionen: list[str], wo: str) -> dict[str, dict]:
    if not isinstance(roh, dict):
        raise KatalogFehler(f"{wo}: Objekt erwartet")
    _laender(list(roh), wo)
    if regionen and not set(roh) <= set(regionen):
        raise KatalogFehler(f"{wo}: regionale Einträge nur für die Regionen der Leistung {regionen}")
    return {
        land: {
            "stelle": _text(e.get("stelle"), f"{wo}.{land}.stelle"),
            "kontakt": _str(e.get("kontakt", ""), f"{wo}.{land}.kontakt"),
            "url": _url(e.get("url", ""), f"{wo}.{land}.url"),
            "quelle": _quelle(e.get("quelle"), f"{wo}.{land}.quelle"),
        }
        for land, e in roh.items()
    }


def _stichworte(liste, wo: str) -> list[str]:
    if not isinstance(liste, list) or any(not isinstance(s, str) or not s.strip() or s != s.strip().lower() for s in liste):
        raise KatalogFehler(f"{wo}: stichworte müssen kleingeschriebene, nicht leere Texte sein")
    if len(set(liste)) != len(liste):
        raise KatalogFehler(f"{wo}: stichworte doppelt")
    return list(liste)


# --- Leichte Sprache --------------------------------------------------------------------------

LEICHT_SAETZE: tuple[int, int] = (2, 4)
LEICHT_WOERTER = 12  # höchstens je Satz
_LEICHT_ABKUERZUNG = re.compile(
    r"(?<![\w.])(?:z\.\s?b|u\.\s?a|d\.\s?h|o\.\s?ä|e\.\s?g|i\.\s?e)\."
    r"|\b(?:bzw|ggf|inkl|usw|etc)\b\.?"
    r"|\b(?:ca|evtl|vgl|bspw|sog|tel|nr|approx)\.", re.IGNORECASE)
_LEICHT_SATZENDE = re.compile(r"(?<=[.!?])\s+")
_ZAHL = re.compile(r"\d+(?:[.,]\d+)*")
_ZAHLWORT = {wort: str(n)
             for woerter in (("zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun", "zehn", "elf", "zwölf"),
                             ("two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"))
             for n, wort in enumerate(woerter, start=2)}


def _zahlen(text: str) -> set[str]:
    """Ziffernfolgen („1.308,39“, „0800“) und Zahlwörter zwei bis zwölf (als Ziffer) eines Texts."""
    return set(_ZAHL.findall(text)) | {_ZAHLWORT[w] for w in re.findall(r"[^\W\d_]+", text.lower()) if w in _ZAHLWORT}


def pruefe_leichte_sprache(text: str, belegt: str, saetze: tuple[int, int] = LEICHT_SAETZE) -> list[str]:
    """Regelverstöße eines Texts in Leichter Sprache; leere Liste = in Ordnung.

    Geprüft: Satzzahl im Bereich `saetze`, Satzzeichen am Ende, höchstens LEICHT_WOERTER Wörter je Satz, keine Abkürzungen
    wie „z. B.“ oder „bzw.“ und keine Zahl, die nicht schon im belegten Ausgangstext `belegt` steht – Leichte Sprache fügt
    keine Beträge, Fristen oder Nummern hinzu („6 Monate“ ist erlaubt, wenn dort „sechs Monate“ steht).
    """
    verstoesse = [f"Abkürzung „{m.group(0)}“" for m in _LEICHT_ABKUERZUNG.finditer(text)]
    text = text.strip()
    if not text.endswith((".", "!", "?")):
        verstoesse.append("Text endet ohne Satzzeichen")
    liste = _LEICHT_SATZENDE.split(text) if text else []
    if not saetze[0] <= len(liste) <= saetze[1]:
        verstoesse.append(f"{len(liste)} Sätze statt {saetze[0]} bis {saetze[1]}")
    for satz in liste:
        woerter = sum(1 for wort in satz.split() if re.search(r"\w", wort))
        if woerter > LEICHT_WOERTER:
            verstoesse.append(f"{woerter} Wörter (höchstens {LEICHT_WOERTER}): „{satz}“")
    neu = sorted(_zahlen(text) - _zahlen(belegt))
    if neu:
        verstoesse.append(f"Zahl nicht im belegten Text: {', '.join(neu)}")
    return verstoesse


def _leicht(roh, belegt: dict[str, str], wo: str) -> dict[str, str]:
    leicht = _text(roh, wo)
    for sprache in _SPRACHEN:
        verstoesse = pruefe_leichte_sprache(leicht[sprache], belegt[sprache])
        if verstoesse:
            raise KatalogFehler(f"{wo}.{sprache}: {'; '.join(verstoesse)}")
    return leicht


def _leistung(roh: dict, szenarien: list[str]) -> Leistung:
    lid = roh.get("id")
    if not isinstance(lid, str) or not re.fullmatch(r"[a-z0-9_]+", lid):
        raise KatalogFehler(f"ungültige Leistungs-ID: {lid!r}")
    wo = f"Leistung {lid}"
    fehlend = [feld for feld in _PFLICHTFELDER if feld not in roh]
    if fehlend:
        raise KatalogFehler(f"{wo}: Felder fehlen: {fehlend}")

    bereiche = roh.get("bereiche") or []
    if not bereiche or any(b not in BEREICHE for b in bereiche):
        raise KatalogFehler(f"{wo}: bereiche müssen aus {BEREICHE} stammen")

    stelle_roh = roh.get("stelle") or {}
    if not isinstance(stelle_roh.get("kontakt", ""), str):
        raise KatalogFehler(f"{wo}: stelle.kontakt muss Text sein")
    stelle = {
        "name": _text(stelle_roh.get("name"), f"{wo}: stelle.name"),
        "kontakt": stelle_roh.get("kontakt", ""),
        "hinweis": _text(stelle_roh.get("hinweis", {"de": "", "en": ""}), f"{wo}: stelle.hinweis", leer_erlaubt=True),
    }

    stelle_nach: dict[str, dict[str, dict[str, str]]] = {}
    stelle_belege: dict[str, dict[str, Quelle]] = {}
    stelle_kontakte: dict[str, dict[str, str]] = {}
    for slot_id, je_wert in (roh.get("stelle_nach") or {}).items():
        slot = SLOTS[_slot_id(slot_id, f"{wo}: stelle_nach")]
        if slot.typ != "auswahl":
            raise KatalogFehler(f"{wo}: stelle_nach nur für Auswahl-Slots, nicht „{slot_id}“")
        stelle_nach[slot_id] = {}
        for wert, text in je_wert.items():
            if wert not in slot.optionen:
                raise KatalogFehler(f"{wo}: „{wert}“ ist keine Option von {slot_id}")
            stelle_nach[slot_id][wert] = _text(text, f"{wo}: stelle_nach.{slot_id}.{wert}")
            if text.get("quelle") is not None:
                beleg = _quelle(text["quelle"], f"{wo}: stelle_nach.{slot_id}.{wert}.quelle")
                stelle_belege.setdefault(slot_id, {})[wert] = beleg
            if "kontakt" in text:
                kontakt = _str(text["kontakt"], f"{wo}: stelle_nach.{slot_id}.{wert}.kontakt")
                if not kontakt.strip():
                    raise KatalogFehler(f"{wo}: stelle_nach.{slot_id}.{wert}.kontakt ist leer")
                stelle_kontakte.setdefault(slot_id, {})[wert] = kontakt

    regionen = roh.get("regionen") or []
    if any(r not in BUNDESLAENDER for r in regionen):
        raise KatalogFehler(f"{wo}: unbekanntes Bundesland in {regionen}")

    rueckfragen = [_slot_id(s, f"{wo}: rueckfragen") for s in roh.get("rueckfragen") or []]
    if any(SLOTS[s].sensibel for s in rueckfragen):
        raise KatalogFehler(f"{wo}: sensible Slots gehören nicht in die Rückfragen")

    schritte = []
    for i, schritt in enumerate(roh.get("schritte") or []):
        sid = schritt.get("id") if isinstance(schritt, dict) else None
        if not isinstance(sid, str) or not re.fullmatch(r"[a-z0-9_]+", sid):
            raise KatalogFehler(f"{wo}: schritte[{i}] ohne gültige id")
        schritte.append({"id": sid, **_text(schritt, f"{wo}: schritte[{i}]")})
    schritt_ids = [s["id"] for s in schritte]
    if not schritte or len(set(schritt_ids)) != len(schritt_ids):
        raise KatalogFehler(f"{wo}: schritte fehlen oder IDs doppelt")

    formular = roh.get("formular")
    if formular is not None:
        if formular not in FORMULARE:
            raise KatalogFehler(f"{wo}: unbekanntes Formular „{formular}“")
        antrag = [sid for sid in schritt_ids if sid in ANTRAGSSCHRITTE]
        if antrag != list(ANTRAGSSCHRITTE):
            raise KatalogFehler(f"{wo}: Formular-Leistung braucht die Schritte {ANTRAGSSCHRITTE} in dieser Reihenfolge")
    formular_regionen = _laender(roh["formular_regionen"], f"{wo}: formular_regionen")
    if formular_regionen and formular is None:
        raise KatalogFehler(f"{wo}: formular_regionen ohne Formular")
    unterlagen_formular = _texte(roh["unterlagen_formular"], f"{wo}: unterlagen_formular")
    if unterlagen_formular and formular is None:
        raise KatalogFehler(f"{wo}: unterlagen_formular ohne Formular")

    quellen = [_quelle(q, f"{wo}: quellen[{i}]") for i, q in enumerate(roh.get("quellen") or [])]
    if not quellen:
        raise KatalogFehler(f"{wo}: mindestens eine Quelle nötig")
    beleg = roh.get("beleg")
    extern = any(q.art == "extern" for q in quellen)
    if beleg == "lokal" and extern:
        raise KatalogFehler(f"{wo}: beleg „lokal“, aber externe Quelle vorhanden")
    if beleg == "extern" and not extern:
        raise KatalogFehler(f"{wo}: beleg „extern“ ohne externe Quelle")
    if beleg not in ("lokal", "extern"):
        raise KatalogFehler(f"{wo}: beleg muss „lokal“ oder „extern“ sein")

    nutzen = _text(roh["nutzen"], f"{wo}: nutzen", leer_erlaubt=True)
    nutzen_quelle = None if roh["nutzen_quelle"] is None else _quelle(roh["nutzen_quelle"], f"{wo}: nutzen_quelle")
    if bool(nutzen["de"].strip()) != (nutzen_quelle is not None):
        raise KatalogFehler(f"{wo}: nutzen und nutzen_quelle nur gemeinsam")

    termin_anlass = roh["termin_anlass"]
    if termin_anlass is not None and termin_anlass not in TERMIN_ANLAESSE:
        raise KatalogFehler(f"{wo}: termin_anlass muss aus {TERMIN_ANLAESSE} stammen")

    kurz = _text(roh.get("kurz"), f"{wo}: kurz")
    details = _text(roh.get("details"), f"{wo}: details")
    voraussetzungen = _texte(roh.get("voraussetzungen") or [], f"{wo}: voraussetzungen")
    belegt = {sp: " ".join([kurz[sp], details[sp], *(t[sp] for t in voraussetzungen + schritte)]) for sp in _SPRACHEN}

    return Leistung(
        id=lid,
        titel=_text(roh.get("titel"), f"{wo}: titel"),
        kurz=kurz,
        leicht=_leicht(roh["leicht"], belegt, f"{wo}: leicht"),
        details=details,
        bereiche=list(bereiche),
        szenarien=szenarien,
        stelle=stelle,
        stelle_nach=stelle_nach,
        regionen=list(regionen),
        formular=formular,
        rueckfragen=rueckfragen,
        unterlagen=_texte(roh.get("unterlagen") or [], f"{wo}: unterlagen"),
        voraussetzungen=voraussetzungen,
        schritte=schritte,
        quellen=quellen,
        beleg=beleg,
        stichworte=_stichworte(roh["stichworte"], f"{wo}: stichworte"),
        nutzen=nutzen,
        nutzen_quelle=nutzen_quelle,
        einrichtungen=_einrichtungen(roh["einrichtungen"], f"{wo}: einrichtungen"),
        regional=_regional(roh["regional"], list(regionen), f"{wo}: regional"),
        formular_regionen=formular_regionen,
        termin_anlass=termin_anlass,
        stelle_belege=stelle_belege,
        stelle_kontakte=stelle_kontakte,
        unterlagen_formular=unterlagen_formular,
    )


def _baue(daten: dict) -> tuple[dict[str, Leistung], dict[str, list[str]]]:
    """Prüft den Katalog vollständig; liefert Leistungen (Dateireihenfolge) und Reihenfolge je Szenario."""
    reihenfolge = daten.get("reihenfolge") or {}
    if sorted(reihenfolge) != sorted(SZENARIEN):
        raise KatalogFehler(f"reihenfolge braucht genau die Szenarien {SZENARIEN}")
    roh_liste = daten.get("leistungen") or []
    ids = [roh.get("id") for roh in roh_liste]
    if len(set(ids)) != len(ids):
        raise KatalogFehler("Leistungs-IDs doppelt")
    for szenario, liste in reihenfolge.items():
        if len(set(liste)) != len(liste) or any(lid not in ids for lid in liste):
            raise KatalogFehler(f"reihenfolge.{szenario}: doppelte oder unbekannte IDs")

    leistungen: dict[str, Leistung] = {}
    for roh in roh_liste:
        szenarien = [s for s in SZENARIEN if roh.get("id") in reihenfolge[s]]
        if not szenarien:
            raise KatalogFehler(f"Leistung {roh.get('id')}: in keinem Szenario eingeordnet")
        leistung = _leistung(roh, szenarien)
        leistungen[leistung.id] = leistung
    return leistungen, {s: list(reihenfolge[s]) for s in SZENARIEN}


@lru_cache(maxsize=1)
def _katalog() -> tuple[dict[str, Leistung], dict[str, list[str]]]:
    return _baue(json.loads(DATEI.read_text(encoding="utf-8")))


def _baue_termine(daten: dict) -> dict:
    """Prüft termine.json: jeder Anlass aus termin.anlass mit Ort, Hinweisen und Suchdiensten, jede Aussage belegt."""
    suche_roh = daten.get("suche")
    if not isinstance(suche_roh, dict) or not suche_roh:
        raise KatalogFehler("termine: suche fehlt")
    suche = {}
    for sid, s in suche_roh.items():
        wo = f"termine.suche.{sid}"
        if not re.fullmatch(r"[a-z0-9_]+", sid) or not isinstance(s, dict):
            raise KatalogFehler(f"{wo}: ungültiger Eintrag")
        url = _url(s.get("url", ""), f"{wo}.url")
        if not url:
            raise KatalogFehler(f"{wo}: URL fehlt")
        suche[sid] = {
            "name": _text(s.get("name"), f"{wo}.name"),
            "url": url,
            "regionen": _laender(s.get("regionen", []), f"{wo}.regionen"),
            "quelle": _quelle(s.get("quelle"), f"{wo}.quelle"),
        }

    anlaesse_roh = daten.get("anlaesse") or {}
    if sorted(anlaesse_roh) != sorted(TERMIN_ANLAESSE):
        raise KatalogFehler(f"termine: anlaesse braucht genau {TERMIN_ANLAESSE}")
    anlaesse = {}
    for anlass, a in anlaesse_roh.items():
        wo = f"termine.anlaesse.{anlass}"
        wo_quellen = [_quelle(q, f"{wo}.wo_quellen[{i}]") for i, q in enumerate(a.get("wo_quellen") or [])]
        if not wo_quellen:
            raise KatalogFehler(f"{wo}: wo braucht einen Beleg")
        hinweise = []
        for i, h in enumerate(a.get("hinweise") or []):
            hinweise.append({**_text(h, f"{wo}.hinweise[{i}]"), "quelle": _quelle(h.get("quelle"), f"{wo}.hinweise[{i}].quelle")})
        unbekannt = [sid for sid in a.get("suche") or [] if sid not in suche]
        if unbekannt or not a.get("suche"):
            raise KatalogFehler(f"{wo}: suche fehlt oder unbekannt: {unbekannt}")
        anlaesse[anlass] = {
            "wo": _text(a.get("wo"), f"{wo}.wo"),
            "wo_quellen": wo_quellen,
            "hinweise": hinweise,
            "suche": list(a["suche"]),
        }

    bh = daten.get("beschwerden_hinweis") or {}
    beschwerden = {**_text(bh, "termine.beschwerden_hinweis"), "quelle": _quelle(bh.get("quelle"), "termine.beschwerden_hinweis.quelle")}
    return {"anlaesse": anlaesse, "suche": suche, "beschwerden": beschwerden}


@lru_cache(maxsize=1)
def _termine() -> dict:
    return _baue_termine(json.loads(TERMIN_DATEI.read_text(encoding="utf-8")))


# --- Öffentliche Schnittstelle ----------------------------------------------------------------

def leistung(id: str) -> Leistung:
    leistungen, _ = _katalog()
    if id not in leistungen:
        raise KeyError(f"Unbekannte Leistung: {id}")
    return leistungen[id]


def alle() -> list[Leistung]:
    return list(_katalog()[0].values())


def _bundesland(name: str) -> str:
    for land in BUNDESLAENDER:
        if land.casefold() == name.strip().casefold():
            return land
    raise ValueError(f"Unbekanntes Bundesland: {name}")


def fuer_szenario(szenario: str, bundesland: str | None = None) -> list[Leistung]:
    """Leistungen eines Szenarios nach Relevanz.

    Mit Bundesland fallen regionale Leistungen anderer Länder weg. Ohne Bundesland bleiben alle erhalten,
    österreichweite stehen zuerst (regionale brauchen noch die Rückfrage nach dem Bundesland).
    """
    if szenario not in SZENARIEN:
        raise ValueError(f"Unbekanntes Szenario: {szenario}")
    leistungen, reihenfolge = _katalog()
    liste = [leistungen[lid] for lid in reihenfolge[szenario]]
    if bundesland is None:
        return sorted(liste, key=lambda l: not l.oesterreichweit)  # stabil: Relevanz bleibt erhalten
    land = _bundesland(bundesland)
    return [l for l in liste if l.oesterreichweit or land in l.regionen]


def termin_info(anlass: str, bundesland: str | None = None) -> TerminInfo:
    """Terminvorbereitung je Anlass: wohin, Hinweise (e-card, Überweisung …), Suchdienste (österreichweit + Land)."""
    termine = _termine()
    if anlass not in termine["anlaesse"]:
        raise ValueError(f"Unbekannter Terminanlass: {anlass}")
    land = _bundesland(bundesland) if bundesland else None
    a = termine["anlaesse"][anlass]
    suche = [termine["suche"][sid] for sid in a["suche"]]
    suche = [s for s in suche if land in s["regionen"]] + [s for s in suche if not s["regionen"]]
    beschwerden = termine["beschwerden"] if anlass == "beschwerden" else None
    quellen: list[Quelle] = []
    for q in [*a["wo_quellen"], *(h["quelle"] for h in a["hinweise"]), *([beschwerden["quelle"]] if beschwerden else []),
              *(s["quelle"] for s in suche)]:
        if q not in quellen:
            quellen.append(q)
    return TerminInfo(
        anlass=anlass,
        wo=dict(a["wo"]),
        hinweise=[{sp: h[sp] for sp in _SPRACHEN} for h in a["hinweise"]],
        suche=[dict(s) for s in suche],
        quellen=quellen,
        beschwerden_hinweis={sp: beschwerden[sp] for sp in _SPRACHEN} if beschwerden else {"de": "", "en": ""},
    )


# --- Szenario-Erkennung (Schlagworte, de + österreichischer Dialekt + en) ----------------------

_ANGEHOERIGE_DE = (r"(mutter|mama|mami|vater|papa|papi|oma|omi|opa|opi|großmutter|großvater|eltern|schwiegermutter|schwiegervater"
                   r"|tante|onkel|angehörige\w*)")
_ANGEHOERIGE_EN = r"(mother|mum|mom|father|dad|parents|grandmother|grandfather|grandma|grandpa|grandad|granddad|mother-in-law|father-in-law|aunt|uncle)"
_NIMMA = r"(nimma|nimmer|nimmamehr|nimmermehr)"  # Dialekt: nicht mehr

# (Muster, Gewicht); ein Szenario zählt ab Gewicht 2. „Tochter“/„Sohn“ zählt für Kind nur mit Altersangabe,
# weil die helfende Person oft „die Tochter“ ist.
_MUSTER: dict[str, list[tuple[str, int]]] = {
    "pflege": [
        (r"\bpflege\w*", 3),
        (r"\bbetreu\w*", 2),
        (r"\bnicht mehr\b[^.?!]{0,25}\b(allein|alleine|zurecht)", 3),
        (r"\b(allein|alleine)\b[^.?!]{0,25}\bnicht mehr\b", 3),
        (rf"\b{_NIMMA}\b[^.?!]{{0,25}}\b(allein|alleine|alloa|alloan|zurecht|z'recht|söba|söwa|selba|selber|selbst)\b", 3),
        (rf"\b(schafft|schaffts|schafft's|packt|packts|packt's|derpackt|kummt|kommt)\b[^.?!]{{0,25}}\b{_NIMMA}\b", 3),
        (r"\b(braucht|brauchen|benötigt|benötigen|braucht's)\b[^.?!]{0,25}\b(hilfe|unterstützung|hüf|hülf)\b", 2),
        (rf"\b(meine[nmrs]?|unsere[nmrs]?|mei|mein|unser|unsa|um meine[nmrs]?)\s+{_ANGEHOERIGE_DE}\b", 1),
        (r"\b(chronisch krank\w*|demenz\w*|dement\w*|alzheimer|bettlägerig\w*|bettlägrig\w*|gebrechlich\w*|24-stunden|24 stunden"
         r"|essen auf rädern|heimhilfe|mobile dienste|altenheim|seniorenheim|senior\w*)", 2),
        (r"(?<!child )(?<!health )(?<!self-)(?<!day )\bcar(e|er|ers|ing)\b", 3),
        (r"\b(nursing home|care home|home help|look(ing)? after|looks after)\b", 3),
        (r"\b(can't|cannot|can no longer|no longer able to|unable to)\b[^.?!]{0,20}\b(cope|manage)\b", 3),
        (r"\b(can't|cannot|can no longer|no longer able to)\b[^.?!]{0,25}\b(on (her|his|their) own|by (herself|himself|themselves))\b", 3),
        (r"\b(needs?|needing)\b[^.?!]{0,20}\b(help|support|assistance)\b", 2),
        (rf"\bmy\s+{_ANGEHOERIGE_EN}\b", 1),
        (r"\b(dementia|alzheimer\w*|chronically ill|bedridden|frail|24-hour)\b", 2),
    ],
    "entlassung": [
        (r"\bentlass\w*", 3),
        (r"\b(befund\w*|arztbrief\w*)", 2),
        (r"\b(krankenhaus\w*|spital\w*|klinik\w*)", 2),
        (r"\b(aus'm|ausm|aus'n|aus dem|vom|von der)\s+(spital|krankenhaus|klinik|reha)\b", 3),
        (r"\b(reha|rehabilitation\w*|anschlussheilverfahren|nachsorge|hauskrankenpflege|kontrolltermin\w*)\b", 2),
        (r"\b(bestrahlung\w*|chemo\w*|strahlentherapie|dialyse)", 2),
        (r"\b(operation|operiert|krankenstand|op)\b", 1),
        (r"\bdischarg\w*", 3),
        (r"\b(home|back) from (the )?(hospital|clinic|rehab)\b", 3),
        (r"\b(hospital|clinic|medical report|doctor's letter|rehab\w*|aftercare|follow-up care|follow-up appointment\w*|home nursing)\b", 2),
        (r"\b(radiotherapy|radiation therapy|chemotherapy|chemo|dialysis)\b", 2),
        (r"\b(surgery|operation|sick leave)\b", 1),
    ],
    "kind": [
        (r"\bkind\w*", 3),
        (r"\b(baby\w*|babies|säugling\w*|neugeboren\w*|kleinkind\w*|schwanger\w*|geburt(?!sdatum|stag)\w*|entbindung\w*|stillzeit|wochengeld"
         r"|familienbeihilfe|eltern-kind-pass|mutter-kind-pass|zahnspange\w*|jugendlich\w*|teenager)", 3),
        (r"\b(meine?|unsere?|mei|unsa)\s+(kleine[rn]?\s+|neugeborene[rn]?\s+)?(tochter|sohn|bua|bub|bube|madl|mädl|mädel|maderl|dirndl)\s+(ist|is|wird)\s+(jetzt\s+|scho\s+|schon\s+|grad\s+)?\d{1,2}\b", 3),
        (r"\b(tochter|sohn|bua|bub|madl|mädl|mädel|dirndl)\b[^.?!]{0,15}\b\d{1,2}\s*(jahre|jahr|monate|wochen)\b", 3),
        (r"\b(meine?|unsere?|mei|unsa)\s+(kleine[rn]?|neugeborene[rn]?)\s+(tochter|sohn)\b", 3),
        (r"\b(mei|mein|meine|unser|unsa|unsere)\s+(bua|bub|bube|buam|madl|mädl|mädel|maderl|dirndl|kloane[rn]?|kloana|zwerg\w*)\b", 3),
        (r"\b(child|children|childcare|kid|kids|baby|babies|toddler|infant|newborn|pregnan\w*|maternity|braces|teenager)\b", 3),
        (r"\b(my|our)\s+(little\s+|baby\s+|newborn\s+)?(son|daughter|boy|girl)\s+is\s+\d{1,2}\b", 3),
        (r"\b(my|our)\s+(little|baby|newborn)\s+(son|daughter|boy|girl)\b", 3),
    ],
    "unterstuetzung": [
        (r"\b(sozialhilfe\w*|sozialunterstützung\w*|mindestsicherung\w*|ausgleichszulage\w*|notstandshilfe|arbeitslosengeld"
         r"|arbeitslos\w*|schulden\w*|schuldenberatung|schuldnerberatung|privatkonkurs|delogier\w*|wohnbeihilfe|alleinerzieh\w*"
         r"|familienberatung\w*|existenzminimum|armut\w*|ams)\b", 3),
        (r"\b(miete|mietrückstand\w*|rechnung\w*|strom\w*|heizung|heizkosten|lebensmittel|essen)\b[^.?!]{0,40}"
         r"\b(nicht|kaum|nimma|nimmer|ned)\b[^.?!]{0,15}\b(leisten|zahlen|bezahlen|zoin|zahln|zoln)\b", 3),
        (r"\b(nicht|kaum|nimma|nimmer|ned)\b[^.?!]{0,15}\b(leisten|zahlen|bezahlen|zoin)\b[^.?!]{0,30}\b(miete|rechnung\w*|strom|heizung)\b", 3),
        (r"\b(kein|ka|keine|koa|zu wenig|nicht genug|ned gnua|kaum)\s+(geld|göd|gööd|gäd|einkommen)\b", 3),
        (r"\b(geld|göd|gööd|einkommen|pension|rente)\b[^.?!]{0,25}\b(reicht nicht|reicht ned|reicht nimma|nicht aus|ned aus|zu niedrig|zu gering|zu wenig|knapp)\b", 3),
        (r"\b(miete|mietschulden)\b", 2),
        (r"\b(geld|göd|gööd)\b", 1),
        (r"\b(unemployed|jobless|lost my job|debts?|in debt|social assistance|social benefits?|welfare|minimum income|single (mum|mom|parent|mother|father)"
         r"|low income|can't afford|cannot afford|barely afford|can't pay|cannot pay|struggling financially|money problems"
         r"|financial (help|support|difficulties|hardship)|equali[sz]ation supplement)\b", 3),
        (r"\b(pension|income)\b[^.?!]{0,25}\b(too low|not enough)\b", 3),
        (r"\b(rent|bills)\b", 2),
    ],
    "gesundheit": [
        (r"\b(gesundheit|gsundheit)\b", 3),
        (r"\b(gesund|gesünder|gsund|gsünder|xund|fit|fitter)\b", 2),
        (r"\b(vorsorge\w*|gesundenuntersuchung|früherkennung|prävention|impf\w*|bewegung\w*|sport\w*|abnehmen|ernährung\w*"
         r"|rauchen|rauchstopp|nichtraucher\w*|stress\w*|entspann\w*|rücken\w*|mammografie|gesundheits-?check|bewegt im park)", 2),
        (r"\b(my|your|our)\s+health\b", 3),
        (r"\b(healthy|healthier|fitness|exercise|check-?up|screening|prevention|vaccin\w*|immunis\w*|quit smoking|smoking|diet|nutrition"
         r"|stress|back pain|wellbeing|well-being)\b", 2),
    ],
}
_KOMPILIERT = {s: [(re.compile(m), g) for m, g in liste] for s, liste in _MUSTER.items()}
_RANG = ("entlassung", "pflege", "kind", "unterstuetzung", "gesundheit")  # Gleichstand: spezifischeres Szenario zuerst
_SCHWELLE = 2
# Reine Sachfragen („Was ist der Unterschied zwischen Kur und Reha?“) ohne eigene Lebenslage öffnen kein Szenario.
_SACHFRAGE = re.compile(
    r"^(was ist der unterschied|was sind die unterschiede|worin unterscheide?t?|unterschied zwischen|was versteht man unter"
    r"|was (ist|sind|bedeutet|bedeuten|heißt|heisst) (ein|eine|einen|der|die|das|denn)?\s*\S+\s*\?$"
    r"|what('s| is) the difference|difference between|what (is|are|does) (a|an|the)\b)")
_PERSOENLICH = re.compile(
    r"\b(ich|i|mir|mich|mein\w*|mei|wir|uns|unser\w*|unsa|du|my|me|we|us|our|mama|papa|oma|opa|mutter|vater|tochter|sohn|bua|madl)\b")


def _normalisiere(text: str) -> str:
    return " ".join(text.lower().replace("’", "'").replace("`", "'").split())


def erkenne_szenarien(text: str) -> list[str]:
    """Szenario-IDs, die zum Freitext passen, absteigend nach Trefferstärke."""
    t = _normalisiere(text)
    if _SACHFRAGE.search(t) and not _PERSOENLICH.search(t):
        return []
    punkte = {s: sum(g for muster, g in liste if muster.search(t)) for s, liste in _KOMPILIERT.items()}
    treffer = [s for s in _RANG if punkte[s] >= _SCHWELLE]
    return sorted(treffer, key=lambda s: -punkte[s])


# --- Passende Leistungen (Stichworte) und Vorsorgeprogramme ------------------------------------

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_WORT = re.compile(r"[a-z0-9]+")


def _falte(text: str) -> str:
    return " ".join(_WORT.findall(_normalisiere(text).translate(_UMLAUTE)))


@lru_cache(maxsize=1)
def _stichwort_index() -> tuple[list[tuple[Leistung, tuple[str, ...]]], dict[str, float]]:
    eintraege = [(l, tuple(dict.fromkeys(_falte(s) for s in l.stichworte if _falte(s)))) for l in alle()]
    haeufigkeit = Counter(s for _, stichworte in eintraege for s in stichworte)
    n = len(eintraege)
    return eintraege, {s: math.log(1 + n / df) for s, df in haeufigkeit.items()}


def _trifft(stichwort: str, woerter: list[str], gefaltet: str) -> bool:
    if " " in stichwort:  # Mehrwortbegriff: als Wortfolge
        return f" {stichwort}" in f" {gefaltet}"
    return any(w.startswith(stichwort) for w in woerter)


def passende_leistungen(text: str, k: int = 3) -> list[tuple[Leistung, float]]:
    """Leistungen, deren Stichworte im Text vorkommen (Wortanfang), gewichtet nach Seltenheit; beste zuerst, nur Score > 0."""
    gefaltet = _falte(text)
    woerter = gefaltet.split()
    if not woerter or k <= 0:
        return []
    eintraege, gewicht = _stichwort_index()
    bewertet = []
    for rang, (l, stichworte) in enumerate(eintraege):
        score = sum(gewicht[s] for s in stichworte if _trifft(s, woerter, gefaltet))
        if score > 0:
            bewertet.append((-score, rang, l))
    bewertet.sort()
    return [(l, round(-minus, 4)) for minus, _, l in bewertet[:k]]


# Familiäre Vorbelastung → offizielle Programme, deren Inhalt die Quellen nennen (SR 2026 S. 12–13).
# Bewusst ohne Risikoaussage: geliefert werden nur Leistungs-IDs.
_FAMILIE = (r"(vater|papa|mutter|mama|eltern|oma|opa|großmutter|großvater|bruder|schwester|geschwister|onkel|tante|cousin\w*"
            r"|familie\w*|familiär\w*|erblich\w*|vererb\w*|father|dad|mother|mum|mom|parents?|grandmother|grandfather|grandma|grandpa"
            r"|brother|sister|siblings?|uncle|aunt|family|hereditary|inherited)")
_VORSORGE_THEMEN: list[tuple[str, tuple[str, ...]]] = [
    (r"(brustkrebs\w*|mammakarzinom\w*|breast cancer)", ("brustkrebs_frueherkennung", "vorsorgeuntersuchung")),
    (r"(darmkrebs\w*|dickdarmkrebs\w*|kolonkarzinom\w*|bowel cancer|colon cancer|colorectal cancer)", ("vorsorgeuntersuchung",)),
    (r"(herzinfarkt\w*|schlaganfall\w*|herz-kreislauf\w*|herzkreislauf\w*|herzkrank\w*|bluthochdruck|heart attack|stroke|heart disease"
     r"|cardiovascular)", ("vorsorgeuntersuchung",)),
    (r"(diabetes|zuckerkrank\w*|zucker|diabetic)", ("vorsorgeuntersuchung",)),
    (r"(\w*krebs\w*|cancer|tumou?r\w*)", ("vorsorgeuntersuchung",)),
]
_VORSORGE_KOMPILIERT = [
    (re.compile(rf"\b{_FAMILIE}\b[^.?!]{{0,60}}\b{thema}|\b{thema}[^.?!]{{0,60}}\b{_FAMILIE}\b"), ids)
    for thema, ids in _VORSORGE_THEMEN
]


def vorsorge_hinweise(text: str) -> list[str]:
    """IDs offizieller Vorsorgeprogramme, wenn der Text eine Erkrankung in der Familie erwähnt – ohne Risikoaussage."""
    t = _normalisiere(text)
    ids: list[str] = []
    for muster, programm in _VORSORGE_KOMPILIERT:
        if muster.search(t):
            ids += [p for p in programm if p not in ids]
    return [lid for lid in ids if lid in _katalog()[0]]
