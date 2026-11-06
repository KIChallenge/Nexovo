"""Sitzungen als versioniertes JSON: Persistenz unter `CACHE_DIR/sitzungen/` und Export/Import (ein Serializer).

Gespeichert wird nur, was den Fall fortsetzbar macht. Sensible Angaben (z. B. Sozialversicherungsnummer,
Geburtsdatum) und der Gesprächsverlauf werden nie geschrieben; Texte von Leistungen und Schritten kommen beim
Laden wieder aus Katalog und Formularen. Beim Laden wird alles geprüft: Format, Version, bekannte IDs und Werte.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import get_args

from lotse import config, katalog, llm
from lotse.fallakte import STATUS, Termin
from lotse.lotse import MAX_RUECKFRAGEN, Absatz, Inhalt, Lotse, Sitzung
from lotse.models import THEMEN, WEITERE_SPRACHEN, Empfehlung, QuellenArt, Quelle
from lotse.slots import BUNDESLAENDER, SLOTS
from lotse.texte import SPRACHEN, STILE

log = logging.getLogger(__name__)

FORMAT = "sv-ki-lotse-sitzung"
VERSION = 1
MAX_ALTER_TAGE = 30
ORDNER: Path | None = None  # None → config.CACHE_DIR / "sitzungen" (Tests setzen ein eigenes Verzeichnis)

_ID = re.compile(r"[0-9a-f]{32}")
_TERMIN_ID = re.compile(r"termin_\d{1,4}")
_MAX_TEXT = 4000
_QUELLEN_ARTEN = set(get_args(QuellenArt))


class UngueltigeSitzung(ValueError):
    """Datei ist kein (gültiger) Fall dieses Lotsen."""


def ordner() -> Path:
    return ORDNER or config.CACHE_DIR / "sitzungen"


# ---------------------------------------------------------------------------
# Serialisieren
# ---------------------------------------------------------------------------

def zu_dict(s: Sitzung) -> dict:
    """Sitzung → JSON-fähiges Dict (Export und Persistenz)."""
    werte = {k: v for k, v in s.werte.items() if not SLOTS[k].sensibel}
    fa = s.fallakte
    return {
        "format": FORMAT,
        "version": VERSION,
        "gespeichert": datetime.now().isoformat(timespec="seconds"),
        "sitzung": {
            "id": s.id,
            "sprache": s.sprache,
            "stil": s.stil,
            "werte": werte,
            "herkunft": {k: dict(h) for k, h in s.herkunft.items() if k in werte},
            "szenarien": list(s.szenarien),
            "leistungen": list(s.leistungen),
            "fokus": list(s.fokus),
            "dok_empfehlungen": {th: [e.to_dict() for e in liste] for th, liste in s.dok_empfehlungen.items()},
            "dok_leistungen": list(s.dok_leistungen),
            "offene_frage": s.offene_frage,
            "fragen_gestellt": s.fragen_gestellt,
            "uebersprungen": sorted(s.uebersprungen),
            "dokumente": [dict(d) for d in s.dokumente],
            "termin_entwurf": dict(s.termin_entwurf) if s.termin_entwurf else None,
            "impfungen": [dict(i) for i in s.impfungen],
            "medikamente": [dict(m) for m in s.medikamente],
            "fallakte": {
                "status": {x.id: x.status for e in fa.eintraege.values() for x in e.schritte + e.unterlagen
                           if x.status != "offen"},
                "historie": [dict(h) for h in fa.historie],
                "termine": [asdict(t) for t in fa.termine.values()],
            },
            "letzte": _inhalt_zu_dict(s.letzte),
        },
    }


def _inhalt_zu_dict(inhalt: Inhalt | None) -> dict | None:
    if inhalt is None or inhalt.art in ("grenze", "fehler"):
        return None
    return {
        "art": inhalt.art,
        "absaetze": [{"text": dict(a.text), "nur_ausfuehrlich": a.nur_ausfuehrlich} for a in inhalt.absaetze],
        "quellen": [q.to_dict() for q in inhalt.quellen],
        "fakten": [dict(f) for f in inhalt.fakten],
        # Freitext der Nutzerin bzw. des Nutzers nie speichern/exportieren (kann SVNR, IBAN o. Ä. enthalten)
        "frage": "",
        "ki_verstanden": inhalt.ki_verstanden,
    }


# ---------------------------------------------------------------------------
# Laden mit Prüfung
# ---------------------------------------------------------------------------

def _fehler(text: str) -> UngueltigeSitzung:
    return UngueltigeSitzung(text)


def _text(wert: object, wo: str, leer: bool = True) -> str:
    if not isinstance(wert, str) or len(wert) > _MAX_TEXT or (not leer and not wert.strip()):
        raise _fehler(f"{wo}: Text erwartet")
    return wert


def _ganzzahl(wert: object, wo: str, minimum: int = 0) -> int:
    if not isinstance(wert, int) or isinstance(wert, bool) or wert < minimum:
        raise _fehler(f"{wo}: Zahl ≥ {minimum} erwartet")
    return wert


def _liste(wert: object, wo: str) -> list:
    if not isinstance(wert, list):
        raise _fehler(f"{wo}: Liste erwartet")
    return wert


def _objekt(wert: object, wo: str) -> dict:
    if not isinstance(wert, dict):
        raise _fehler(f"{wo}: Objekt erwartet")
    return wert


def _leistung_id(wert: object, wo: str) -> str:
    try:
        return katalog.leistung(_text(wert, wo)).id
    except KeyError:
        raise _fehler(f"{wo}: unbekannte Leistung {wert!r}") from None


def _slot_id(wert: object, wo: str) -> str:
    if wert not in SLOTS:
        raise _fehler(f"{wo}: unbekannte Angabe {wert!r}")
    return wert


def _auswahl(wert: object, slot_id: str, wo: str) -> str:
    """Auswahlwert eines Slots oder "" (übersprungen)."""
    if wert != "" and wert not in SLOTS[slot_id].optionen:
        raise _fehler(f"{wo}: ungültiger Wert {wert!r}")
    return wert


def _quelle(q: object, wo: str) -> Quelle:
    q = _objekt(q, wo)
    felder = {"art", "titel", "fundstelle", "datei", "zitat", "stand", "url"}
    if not set(q) <= felder or q.get("art") not in _QUELLEN_ARTEN:
        raise _fehler(f"{wo}: ungültige Quelle")
    return Quelle(**{k: _text(v, wo) for k, v in q.items()})


def _datum_gueltig(wert: str) -> bool:
    if not SLOTS["termin.datum"].gueltig(wert):
        return False
    tag, monat, jahr = (int(x) for x in wert.split("."))
    try:
        date(jahr, monat, tag)
    except ValueError:
        return False
    return True


def _termin(roh: object, wo: str) -> Termin:
    d = _objekt(roh, wo)
    erwartet = {"id", "anlass", "ort", "zeit", "bundesland", "leistung_id", "datum", "uhrzeit", "erstellt", "uid"}
    if not set(d) <= erwartet or not _TERMIN_ID.fullmatch(str(d.get("id", ""))):
        raise _fehler(f"{wo}: ungültiger Termin")
    datum = _text(d.get("datum", ""), wo)
    uhrzeit = _text(d.get("uhrzeit", ""), wo)
    bundesland = _text(d.get("bundesland", ""), wo)
    if (datum and not _datum_gueltig(datum)) or (uhrzeit and not SLOTS["termin.uhrzeit"].gueltig(uhrzeit)) \
            or (bundesland and bundesland not in BUNDESLAENDER):
        raise _fehler(f"{wo}: ungültiges Datum, Uhrzeit oder Bundesland")
    leistung = d.get("leistung_id")
    uid = _text(d.get("uid") or uuid.uuid4().hex, wo)
    if not re.fullmatch(r"[0-9a-f]{32}", uid):
        raise _fehler(f"{wo}: ungültige UID")
    return Termin(
        id=d["id"],
        anlass=_auswahl(d.get("anlass", ""), "termin.anlass", wo),
        ort=_text(d.get("ort", ""), wo)[:200],
        zeit=_auswahl(d.get("zeit", ""), "termin.zeit", wo),
        bundesland=bundesland,
        leistung_id=None if leistung is None else _leistung_id(leistung, wo),
        datum=datum,
        uhrzeit=uhrzeit,
        erstellt=_text(d.get("erstellt", ""), wo),
        uid=uid,
    )


def _entwurf(roh: object) -> dict | None:
    if roh is None:
        return None
    d = _objekt(roh, "termin_entwurf")
    if not set(d) <= {"anlass", "ort", "zeit", "leistung"}:
        raise _fehler("termin_entwurf: unbekannte Felder")
    ort, zeit, leistung = d.get("ort"), d.get("zeit"), d.get("leistung")
    return {
        "anlass": _auswahl(d.get("anlass", ""), "termin.anlass", "termin_entwurf"),
        "ort": None if ort is None else _text(ort, "termin_entwurf.ort")[:200],
        "zeit": None if zeit is None else _auswahl(zeit, "termin.zeit", "termin_entwurf"),
        "leistung": None if leistung is None else _leistung_id(leistung, "termin_entwurf"),
    }


def _inhalt_aus_dict(roh: object) -> Inhalt | None:
    """Letzte Antwort (nur zum Neu-Rendern); bei jedem Fehler None statt Abbruch."""
    try:
        d = _objekt(roh, "letzte")
        absaetze = []
        for a in _liste(d["absaetze"], "letzte.absaetze"):
            text = {sp: _text(a["text"][sp], "letzte") for sp in SPRACHEN}
            absaetze.append(Absatz(text, bool(a.get("nur_ausfuehrlich"))))
        fakten = [{"n": _ganzzahl(f["n"], "fakt", 1), "text": _text(f["text"], "fakt"),
                   "quelle": _text(f["quelle"], "fakt")} for f in _liste(d.get("fakten", []), "fakten")]
        return Inhalt(
            art=_text(d.get("art", "fall"), "art"),
            absaetze=absaetze,
            quellen=[_quelle(q, "letzte.quellen") for q in _liste(d.get("quellen", []), "quellen")],
            fakten=fakten,
            frage=_text(d.get("frage", ""), "frage"),
            ki_verstanden=bool(d.get("ki_verstanden")),
        )
    except (UngueltigeSitzung, KeyError, TypeError, AttributeError):
        return None


def aus_dict(daten: object, neue_id: str | None = None) -> Sitzung:
    """Geprüftes Dict → Sitzung; `UngueltigeSitzung` bei falschem Format, Version, unbekannten IDs oder Werten."""
    try:
        return _aus_dict(daten, neue_id)
    except (KeyError, TypeError, AttributeError) as e:
        raise _fehler(f"Unvollständige Fall-Datei ({type(e).__name__})") from None


def _aus_dict(daten: object, neue_id: str | None) -> Sitzung:
    if not isinstance(daten, dict) or daten.get("format") != FORMAT:
        raise _fehler("Das ist keine Fall-Datei des SV KI-Lotsen")
    if daten.get("version") != VERSION:
        raise _fehler(f"Version {daten.get('version')!r} wird nicht unterstützt (erwartet {VERSION})")
    d = _objekt(daten.get("sitzung"), "sitzung")
    sid = neue_id or d.get("id")
    if not isinstance(sid, str) or not _ID.fullmatch(sid):
        raise _fehler("Ungültige Sitzungs-ID")

    sprache = d.get("sprache", "de")
    if sprache in WEITERE_SPRACHEN and not llm.aktiv():
        sprache = "en"  # weitere Sprachen nur im KI-Modus
    if sprache not in SPRACHEN and sprache not in WEITERE_SPRACHEN:
        raise _fehler(f"Unbekannte Sprache {sprache!r}")
    stil = d.get("stil", "einfach")
    if stil not in STILE:
        raise _fehler(f"Unbekannter Stil {stil!r}")

    werte: dict[str, str] = {}
    for k, v in _objekt(d.get("werte", {}), "werte").items():
        if not SLOTS[_slot_id(k, "werte")].gueltig(_text(v, f"werte.{k}")):
            raise _fehler(f"werte.{k}: ungültiger Wert")
        werte[k] = v
    herkunft: dict[str, dict] = {}
    for k, h in _objekt(d.get("herkunft", {}), "herkunft").items():
        h = _objekt(h, f"herkunft.{k}")
        if k not in werte or h.get("art") not in ("dialog", "dokument", "ort"):
            raise _fehler(f"herkunft.{k}: ungültig")
        if h["art"] == "dialog":
            herkunft[k] = {"art": "dialog"}
        elif h["art"] == "ort":
            herkunft[k] = {"art": "ort", "ort": _text(h.get("ort", ""), "herkunft", leer=False)[:100]}
        else:
            herkunft[k] = {"art": "dokument", "dokument": _text(h.get("dokument", ""), "herkunft"),
                           "seite": _ganzzahl(h.get("seite", 1), "herkunft", 1)}

    szenarien = _liste(d.get("szenarien", []), "szenarien")
    if any(sz not in katalog.SZENARIEN for sz in szenarien):
        raise _fehler("szenarien: unbekanntes Szenario")
    for lid in _liste(d.get("leistungen", []), "leistungen"):
        _leistung_id(lid, "leistungen")
    fokus = [_leistung_id(lid, "fokus") for lid in _liste(d.get("fokus", []), "fokus")]
    dok_leistungen = [_leistung_id(lid, "dok_leistungen") for lid in _liste(d.get("dok_leistungen", []), "dok")]

    dok_empfehlungen: dict[str, list[Empfehlung]] = {}
    for thema, liste in _objekt(d.get("dok_empfehlungen", {}), "dok_empfehlungen").items():
        if thema not in THEMEN:
            raise _fehler(f"dok_empfehlungen: unbekanntes Thema {thema!r}")
        _leistung_id(thema, "dok_empfehlungen")
        dok_empfehlungen[thema] = [
            Empfehlung(thema=thema, zitat=_text(e["zitat"], "zitat", leer=False),
                       seite=_ganzzahl(e["seite"], "seite", 1), quelle=_quelle(e["quelle"], "quelle"))
            for e in _liste(liste, f"dok_empfehlungen.{thema}")
        ]

    offene_frage = d.get("offene_frage")
    if offene_frage is not None:
        _slot_id(offene_frage, "offene_frage")
    uebersprungen = {_slot_id(x, "uebersprungen") for x in _liste(d.get("uebersprungen", []), "uebersprungen")}
    dokumente = [
        {"name": _text(x["name"], "dokument", leer=False), "seiten": _ganzzahl(x["seiten"], "seiten"),
         "transkribiert": bool(x.get("transkribiert", False))}
        for x in _liste(d.get("dokumente", []), "dokumente")
    ]
    impfungen = [
        {"impfung": _text(x["impfung"], "impfung", leer=False), "datum": _text(x["datum"], "datum"),
         "seite": _ganzzahl(x["seite"], "seite", 1), "dokument": _text(x["dokument"], "dokument")}
        for x in _liste(d.get("impfungen", []), "impfungen")
    ]
    medikamente = []
    for x in _liste(d.get("medikamente", []), "medikamente"):
        suche = x.get("eko_suche")
        if suche is not None:
            suche = _text(suche, "medikamente.eko_suche", leer=False)[:200]
        medikamente.append({"name_dokument": _text(x["name_dokument"], "medikament", leer=False),
                            "seite": _ganzzahl(x["seite"], "seite", 1), "dokument": _text(x["dokument"], "dokument"),
                            "eko_suche": suche})

    fa = _objekt(d.get("fallakte", {}), "fallakte")
    status: dict[str, str] = {}
    for schritt_id, wert in _objekt(fa.get("status", {}), "fallakte.status").items():
        if wert not in STATUS or not isinstance(schritt_id, str) or "." not in schritt_id:
            raise _fehler(f"fallakte.status: ungültig ({schritt_id!r})")
        status[schritt_id] = wert
    historie = []
    for h in _liste(fa.get("historie", []), "fallakte.historie"):
        h = _objekt(h, "historie")
        if h.get("von") not in STATUS or h.get("nach") not in STATUS:
            raise _fehler("fallakte.historie: ungültiger Status")
        historie.append({"zeit": _text(h["zeit"], "zeit"), "schritt_id": _text(h["schritt_id"], "schritt"),
                         "leistung_id": _text(h["leistung_id"], "leistung"), "von": h["von"], "nach": h["nach"]})
    termine = [_termin(x, "fallakte.termine") for x in _liste(fa.get("termine", []), "fallakte.termine")]
    if len({t.id for t in termine}) != len(termine):
        raise _fehler("fallakte.termine: doppelte IDs")

    s = Sitzung(
        id=sid, sprache=sprache, stil=stil, werte=werte, herkunft=herkunft, szenarien=list(szenarien),
        fokus=fokus, dok_empfehlungen=dok_empfehlungen, dok_leistungen=dok_leistungen, offene_frage=offene_frage,
        fragen_gestellt=min(_ganzzahl(d.get("fragen_gestellt", 0), "fragen_gestellt"), MAX_RUECKFRAGEN),
        uebersprungen=uebersprungen, dokumente=dokumente, termin_entwurf=_entwurf(d.get("termin_entwurf")),
        impfungen=impfungen, medikamente=medikamente,
    )
    for t in termine:
        s.fallakte.termine[t.id] = t
    try:
        Lotse().baue_fallakte(s, status, historie)
    except KeyError as e:
        raise _fehler(f"fallakte: unbekannter Schritt {e.args[0]!r}") from None
    s.letzte = _inhalt_aus_dict(d.get("letzte")) if d.get("letzte") is not None else None
    return s


# ---------------------------------------------------------------------------
# Dateien
# ---------------------------------------------------------------------------

def speichere(s: Sitzung) -> None:
    """Sitzung atomar schreiben (temporäre Datei + os.replace); Fehler werden protokolliert, nicht geworfen."""
    if not _ID.fullmatch(s.id):
        return
    pfad = ordner() / f"{s.id}.json"
    tmp = pfad.with_name(f".{s.id}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(zu_dict(s), ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, pfad)
    except OSError as e:
        log.warning("Sitzung konnte nicht gespeichert werden (%s).", type(e).__name__)
        tmp.unlink(missing_ok=True)


def lade(sitzung_id: str) -> Sitzung | None:
    """Gespeicherte Sitzung oder None (unbekannt, beschädigt oder ungültig – dann bleibt die Datei liegen)."""
    if not isinstance(sitzung_id, str) or not _ID.fullmatch(sitzung_id):
        return None
    pfad = ordner() / f"{sitzung_id}.json"
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        log.warning("Sitzungsdatei %s… nicht lesbar (%s).", sitzung_id[:8], type(e).__name__)
        return None
    try:
        return aus_dict(daten)
    except UngueltigeSitzung as e:
        log.warning("Sitzungsdatei %s… ungültig: %s", sitzung_id[:8], e)
        return None


def aufraeumen(max_tage: int = MAX_ALTER_TAGE, jetzt: float | None = None) -> int:
    """Löscht Sitzungsdateien (und liegengebliebene Temporärdateien), die älter als `max_tage` sind."""
    grenze = (jetzt if jetzt is not None else time.time()) - max_tage * 86400
    geloescht = 0
    verzeichnis = ordner()
    if not verzeichnis.is_dir():
        return 0
    for pfad in [*verzeichnis.glob("*.json"), *verzeichnis.glob(".*.tmp")]:
        try:
            if pfad.stat().st_mtime < grenze:
                pfad.unlink()
                geloescht += 1
        except OSError:
            continue
    return geloescht
