"""Leistungskatalog: lädt `lotse/data/leistungen.json`, filtert nach Szenario und Region, erkennt Szenarien im Freitext.

Jede Leistung trägt ihre Quellen. `beleg="extern"` heißt: nicht lokal geprüft (z. B. „Bewegt im Park“).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import get_args

from lotse import config
from lotse.models import FORMULARE, QuellenArt, Quelle
from lotse.slots import BUNDESLAENDER, SLOTS

SZENARIEN: tuple[str, ...] = ("pflege", "gesundheit", "entlassung", "kind")
BEREICHE: tuple[str, ...] = ("A", "B", "C", "D", "E", "F")  # Bereiche laut Use Case
# Leistungen mit Formular führen diese Schritt-IDs in dieser Reihenfolge (Fallakte baut darauf auf).
ANTRAGSSCHRITTE: tuple[str, ...] = ("antrag_ausfuellen", "antrag_unterschreiben", "antrag_einreichen")
DATEI = config.PAKET_DATEN / "leistungen.json"
_SPRACHEN = ("de", "en")
_QUELLEN_ARTEN = set(get_args(QuellenArt))


class KatalogFehler(ValueError):
    """Ungültiger Eintrag in leistungen.json."""


@dataclass(frozen=True)
class Leistung:
    id: str
    titel: dict[str, str]
    kurz: dict[str, str]  # einfache Sprache, höchstens zwei Sätze
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
    beleg: str  # "lokal" | "extern"

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


def _quelle(q: dict, wo: str) -> Quelle:
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
    elif not (quelle.datei and quelle.fundstelle and quelle.zitat):
        raise KatalogFehler(f"{wo}: lokale Quelle braucht datei, fundstelle und zitat")
    return quelle


def _slot_id(slot_id: str, wo: str) -> str:
    if slot_id not in SLOTS:
        raise KatalogFehler(f"{wo}: unbekannte Slot-ID „{slot_id}“")
    return slot_id


def _leistung(roh: dict, szenarien: list[str]) -> Leistung:
    lid = roh.get("id")
    if not isinstance(lid, str) or not re.fullmatch(r"[a-z0-9_]+", lid):
        raise KatalogFehler(f"ungültige Leistungs-ID: {lid!r}")
    wo = f"Leistung {lid}"

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
    for slot_id, je_wert in (roh.get("stelle_nach") or {}).items():
        slot = SLOTS[_slot_id(slot_id, f"{wo}: stelle_nach")]
        if slot.typ != "auswahl":
            raise KatalogFehler(f"{wo}: stelle_nach nur für Auswahl-Slots, nicht „{slot_id}“")
        stelle_nach[slot_id] = {}
        for wert, text in je_wert.items():
            if wert not in slot.optionen:
                raise KatalogFehler(f"{wo}: „{wert}“ ist keine Option von {slot_id}")
            stelle_nach[slot_id][wert] = _text(text, f"{wo}: stelle_nach.{slot_id}.{wert}")

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

    return Leistung(
        id=lid,
        titel=_text(roh.get("titel"), f"{wo}: titel"),
        kurz=_text(roh.get("kurz"), f"{wo}: kurz"),
        details=_text(roh.get("details"), f"{wo}: details"),
        bereiche=list(bereiche),
        szenarien=szenarien,
        stelle=stelle,
        stelle_nach=stelle_nach,
        regionen=list(regionen),
        formular=formular,
        rueckfragen=rueckfragen,
        unterlagen=_texte(roh.get("unterlagen") or [], f"{wo}: unterlagen"),
        voraussetzungen=_texte(roh.get("voraussetzungen") or [], f"{wo}: voraussetzungen"),
        schritte=schritte,
        quellen=quellen,
        beleg=beleg,
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


# --- Szenario-Erkennung (Schlagworte, de + en) ------------------------------------------------

_ANGEHOERIGE_DE = r"(mutter|mama|vater|papa|oma|opa|großmutter|großvater|eltern|schwiegermutter|schwiegervater|tante|onkel|angehörige\w*)"
_ANGEHOERIGE_EN = r"(mother|mum|mom|father|dad|parents|grandmother|grandfather|grandma|grandpa|mother-in-law|father-in-law|aunt|uncle)"

# (Muster, Gewicht); ein Szenario zählt ab Gewicht 2. „Tochter“/„Sohn“ zählt für Kind nur mit Altersangabe,
# weil die helfende Person oft „die Tochter“ ist.
_MUSTER: dict[str, list[tuple[str, int]]] = {
    "pflege": [
        (r"\bpflege\w*", 3),
        (r"\bbetreu\w*", 2),
        (r"\bnicht mehr\b[^.?!]{0,25}\b(allein|alleine|zurecht)", 3),
        (r"\b(allein|alleine)\b[^.?!]{0,25}\bnicht mehr\b", 3),
        (r"\b(braucht|brauchen|benötigt|benötigen)\b[^.?!]{0,25}\b(hilfe|unterstützung)\b", 2),
        (rf"\b(meine[nmrs]?|unsere[nmrs]?|um meine[nmrs]?)\s+{_ANGEHOERIGE_DE}\b", 1),
        (r"\b(chronisch krank\w*|demenz\w*|alzheimer|bettlägerig\w*|gebrechlich\w*|24-stunden|24 stunden|essen auf rädern|heimhilfe|mobile dienste|altenheim|seniorenheim|senior\w*)", 2),
        (r"(?<!child )(?<!health )(?<!self-)(?<!day )\bcar(e|er|ers|ing)\b", 3),
        (r"\b(nursing home|care home|home help|look(ing)? after|looks after)\b", 3),
        (r"\b(can't|cannot|can no longer|no longer able to|unable to)\b[^.?!]{0,20}\b(cope|manage)\b", 3),
        (r"\b(needs?|needing)\b[^.?!]{0,20}\b(help|support|assistance)\b", 2),
        (rf"\bmy\s+{_ANGEHOERIGE_EN}\b", 1),
        (r"\b(dementia|alzheimer\w*|chronically ill|bedridden|frail|24-hour)\b", 2),
    ],
    "entlassung": [
        (r"\bentlass\w*", 3),
        (r"\b(befund\w*|arztbrief\w*)", 2),
        (r"\b(krankenhaus\w*|spital\w*|klinik\w*)", 2),
        (r"\b(reha|rehabilitation\w*|anschlussheilverfahren|nachsorge|hauskrankenpflege)\b", 2),
        (r"\b(bestrahlung\w*|chemo\w*|strahlentherapie|dialyse)", 2),
        (r"\b(operation|operiert|krankenstand)\b", 1),
        (r"\bdischarg\w*", 3),
        (r"\b(hospital|clinic|medical report|doctor's letter|rehab\w*|aftercare|follow-up care|home nursing)\b", 2),
        (r"\b(radiotherapy|radiation therapy|chemotherapy|chemo|dialysis)\b", 2),
        (r"\b(surgery|operation|sick leave)\b", 1),
    ],
    "kind": [
        (r"\bkind\w*", 3),
        (r"\b(baby\w*|säugling\w*|neugeboren\w*|kleinkind\w*|schwanger\w*|geburt(?!sdatum|stag)\w*|entbindung\w*|stillzeit|wochengeld"
         r"|familienbeihilfe|eltern-kind-pass|mutter-kind-pass|zahnspange\w*|jugendlich\w*|teenager)", 3),
        (r"\b(meine?|unsere?)\s+(kleine[rn]?\s+|neugeborene[rn]?\s+)?(tochter|sohn)\s+(ist|wird)\s+\d{1,2}\b", 3),
        (r"\b(tochter|sohn)\b[^.?!]{0,15}\b\d{1,2}\s*(jahre|monate|wochen)\b", 3),
        (r"\b(meine?|unsere?)\s+(kleine[rn]?|neugeborene[rn]?)\s+(tochter|sohn)\b", 3),
        (r"\b(child|children|childcare|kid|kids|baby|babies|toddler|infant|newborn|pregnan\w*|maternity|braces|teenager)\b", 3),
        (r"\b(my|our)\s+(little\s+|baby\s+|newborn\s+)?(son|daughter)\s+is\s+\d{1,2}\b", 3),
        (r"\b(my|our)\s+(little|baby|newborn)\s+(son|daughter)\b", 3),
    ],
    "gesundheit": [
        (r"\bgesundheit\b", 3),
        (r"\b(gesund|gesünder|fit|fitter)\b", 2),
        (r"\b(vorsorge\w*|gesundenuntersuchung|früherkennung|prävention|impf\w*|bewegung\w*|sport\w*|abnehmen|ernährung\w*"
         r"|rauchen|rauchstopp|nichtraucher\w*|stress\w*|entspann\w*|rücken\w*|mammografie|gesundheits-?check|bewegt im park)", 2),
        (r"\b(my|your|our)\s+health\b", 3),
        (r"\b(healthy|healthier|fitness|exercise|check-?up|screening|prevention|vaccin\w*|immunis\w*|quit smoking|smoking|diet|nutrition"
         r"|stress|back pain|wellbeing|well-being)\b", 2),
    ],
}
_KOMPILIERT = {s: [(re.compile(m), g) for m, g in liste] for s, liste in _MUSTER.items()}
_RANG = ("entlassung", "pflege", "kind", "gesundheit")  # Gleichstand: spezifischeres Szenario zuerst
_SCHWELLE = 2


def erkenne_szenarien(text: str) -> list[str]:
    """Szenario-IDs, die zum Freitext passen, absteigend nach Trefferstärke."""
    t = " ".join(text.lower().replace("’", "'").split())
    punkte = {s: sum(g for muster, g in liste if muster.search(t)) for s, liste in _KOMPILIERT.items()}
    treffer = [s for s in _RANG if punkte[s] >= _SCHWELLE]
    return sorted(treffer, key=lambda s: -punkte[s])
