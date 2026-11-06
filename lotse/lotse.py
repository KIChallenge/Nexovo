"""Lotse-Engine: Grenzprüfung, Situationserkennung, Rückfragen, Leistungsbündel, Termine, Dokumente, Fallakte.

Ablauf je Nachricht: Grenze → Status-Befehl → Termin gemeldet → offene Terminfrage → Statusfrage → Terminwunsch →
Rückfrage-Antwort → Sonderfragen (Pflegegeldbetrag, Erstattungskodex) → Szenario → Wissensfrage. Alle Texte
entstehen zweisprachig (de/en), damit Sprache und Darstellung nachträglich umgeschaltet werden können; weitere
Sprachen übersetzt im KI-Modus das Modell aus dem Englischen (geprüft, mit Rückfall auf Englisch).
"""

from __future__ import annotations

import re
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from functools import partial

from lotse import dokument, formulare, grenzen, katalog, llm, texte, wissen
from lotse.fallakte import TERMIN_KETTE, Fallakte, Termin, ics
from lotse.models import FORMULARE, WEITERE_SPRACHEN, Empfehlung, Grenzentscheidung, Quelle, Treffer
from lotse.slots import SLOTS
from lotse.texte import SPRACHEN, STILE, beide, t

MAX_RUECKFRAGEN = 5  # je erkanntem Anliegen
PRIMAER = 3  # so viele Bündel nennt der Chat; der Rest steht als „weitere Angebote“ in der Fallakte
PASSEND_MIN = 2.5  # Stichwort-Score, ab dem eine Leistung ohne erkanntes Szenario angeboten wird
TERMIN_SLOTS = ("termin.anlass", "termin.ort", "termin.zeit")


# ---------------------------------------------------------------------------
# Sitzung und Antwort
# ---------------------------------------------------------------------------

@dataclass
class Absatz:
    text: dict[str, str]
    nur_ausfuehrlich: bool = False


@dataclass
class Inhalt:
    """Sprachneutraler Inhalt einer Antwort; wird je Sprache/Darstellung gerendert."""

    art: str = "fall"  # start | fall | wissen | grenze | status | termin | fehler
    absaetze: list[Absatz] = field(default_factory=list)
    quellen: list[Quelle] = field(default_factory=list)
    grenze: Grenzentscheidung | None = None
    fakten: list[dict] = field(default_factory=list)  # für llm.formuliere
    frage: str = ""
    ki_texte: dict[tuple[str, str], str] = field(default_factory=dict)
    ki_verstanden: bool = False

    def neu(self, key: str, nur_ausfuehrlich: bool = False, **kw: object) -> None:
        self.absaetze.append(Absatz(beide(key, **kw), nur_ausfuehrlich))

    def zeilen(self, zeilen: list[dict[str, str]], nur_ausfuehrlich: bool = False) -> None:
        if zeilen:
            self.absaetze.append(
                Absatz({sp: "\n".join(z[sp] for z in zeilen) for sp in SPRACHEN}, nur_ausfuehrlich)
            )

    def marke(self, q: Quelle) -> str:
        """Quelle aufnehmen (einmal) und ihre Nummer als „[n]“ liefern."""
        if q not in self.quellen:
            self.quellen.append(q)
        return f"[{self.quellen.index(q) + 1}]"


@dataclass
class Sitzung:
    id: str
    sprache: str = "de"
    stil: str = "einfach"
    werte: dict[str, str] = field(default_factory=dict)
    herkunft: dict[str, dict] = field(default_factory=dict)  # slot → {"art": dialog|dokument, "dokument", "seite"}
    szenarien: list[str] = field(default_factory=list)  # neueste zuerst
    leistungen: list[str] = field(default_factory=list)  # aktuelles Bündel
    fokus: list[str] = field(default_factory=list)  # Leistungen zur letzten konkreten Frage (stehen zuerst)
    dok_empfehlungen: dict[str, list[Empfehlung]] = field(default_factory=dict)
    dok_leistungen: list[str] = field(default_factory=list)  # aus Dokumenten ohne Empfehlung (z. B. Impfungen)
    offene_frage: str | None = None
    fragen_gestellt: int = 0
    uebersprungen: set[str] = field(default_factory=set)
    dokumente: list[dict] = field(default_factory=list)  # {"name", "seiten", "transkribiert"}
    fallakte: Fallakte = field(default_factory=Fallakte)
    termin_entwurf: dict | None = None  # {"anlass", "ort", "zeit", "leistung"}; None = noch nicht gefragt
    impfungen: list[dict] = field(default_factory=list)  # {"impfung", "datum", "seite", "dokument"}
    medikamente: list[dict] = field(default_factory=list)  # {"name_dokument", "seite", "dokument", "pzn"}
    verlauf: list[dict] = field(default_factory=list)
    letzte: Inhalt | None = None
    sperre: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)


@dataclass
class Antwort:
    sitzung_id: str
    text: str
    rueckfrage: dict | None
    buendel: list[dict]
    quellen: list[dict]
    grenze: dict | None
    fallakte: dict
    modus: str  # regelbasiert | ki
    sprache: str
    stil: str
    szenarien: list[dict]
    angaben: list[dict]
    dokumente: list[dict]
    richtung: str = "ltr"
    weitere_anzahl: int = 0
    termine: list[dict] = field(default_factory=list)
    impfungen: list[dict] = field(default_factory=list)
    medikamente: list[dict] = field(default_factory=list)
    status_uebersicht: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Normalisierung von Antworten und Erkennung in freiem Text
# ---------------------------------------------------------------------------

def _falte(text: str) -> str:
    """Kleinbuchstaben, Umlaute ausgeschrieben, Leerraum normalisiert."""
    text = text.casefold()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("’", "'")):
        text = text.replace(a, b)
    return " ".join(text.split())


_BUNDESLAND_NAMEN = {
    "Wien": ("wien", "vienna"),
    "Niederösterreich": ("niederoesterreich", "lower austria"),
    "Oberösterreich": ("oberoesterreich", "upper austria"),
    "Salzburg": ("salzburg",),
    "Tirol": ("tirol", "tyrol"),
    "Vorarlberg": ("vorarlberg",),
    "Kärnten": ("kaernten", "carinthia"),
    "Steiermark": ("steiermark", "styria"),
    "Burgenland": ("burgenland",),
}
_BUNDESLAND_KURZ = {"Niederösterreich": ("noe",), "Oberösterreich": ("ooe",)}
# Landeshauptstädte und große Städte → Bundesland (Geografie, kein Sachinhalt); nur wenn das Bundesland noch fehlt
_STAEDTE = {
    "Steiermark": ("Graz", "Leoben", "Kapfenberg", "Bruck an der Mur", "Weiz", "Knittelfeld"),
    "Oberösterreich": ("Linz", "Wels", "Steyr", "Leonding", "Traun", "Vöcklabruck", "Braunau"),
    "Salzburg": ("Hallein", "Saalfelden", "Bischofshofen"),
    "Tirol": ("Innsbruck", "Kufstein", "Lienz", "Schwaz", "Telfs", "Wörgl"),
    "Kärnten": ("Klagenfurt", "Villach", "Wolfsberg", "Spittal an der Drau", "St. Veit an der Glan"),
    "Niederösterreich": ("St. Pölten", "St Pölten", "Sankt Pölten", "Wiener Neustadt", "Krems", "Amstetten",
                         "Mödling", "Klosterneuburg", "Tulln", "Schwechat"),
    "Burgenland": ("Eisenstadt", "Oberwart", "Neusiedl am See", "Mattersburg"),
    "Vorarlberg": ("Bregenz", "Dornbirn", "Feldkirch", "Bludenz", "Hohenems", "Lustenau"),
}


def _stadt(f: str) -> tuple[str, str] | None:
    """(Bundesland, genannte Stadt) aus gefaltetem Text, wenn genau eine Stadt passt."""
    funde = {(land, stadt) for land, staedte in _STAEDTE.items() for stadt in staedte
             if re.search(rf"\b{re.escape(_falte(stadt))}\b", f)}
    return funde.pop() if len(funde) == 1 else None


_UEBERSPRINGEN = re.compile(
    r"weiss (ich )?nicht|keine ahnung|unbekannt|ueberspring|spaeter|\bskip\b|don'?t know|do not know|"
    r"not sure|unsure|no idea|\blater\b"
)
_EGAL = re.compile(r"\begal\b|\bflexibel\b|\bbeliebig\b|\bany\b|\banywhere\b|doesn'?t matter|no preference|flexible")
_JA_NEIN = re.compile(r"^(ja|jo|jawohl|gerne?|bitte|yes|yep|sure|nein|na|no|nope)\b[\s,.!]*(bitte|please)?[\s.!]*$")

_ZAHLWORTE = {
    "eins": 1, "ein": 1, "eine": 1, "einem": 1, "zwei": 2, "drei": 3, "vier": 4, "fuenf": 5, "sechs": 6,
    "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwoelf": 12, "one": 1, "two": 2, "three": 3,
    "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}


def _treffer(muster: str, text: str) -> bool:
    return re.search(muster, text) is not None


def _bundesland(text: str, kurzformen: bool) -> str | None:
    gefunden = set()
    for land, namen in _BUNDESLAND_NAMEN.items():
        alle = namen + (_BUNDESLAND_KURZ.get(land, ()) if kurzformen else ())
        if any(re.search(rf"\b{re.escape(n)}\b", text) for n in alle):
            gefunden.add(land)
    return gefunden.pop() if len(gefunden) == 1 else None


def _auswahl(slot_id: str, f: str) -> str | None:
    """Freitext (gefaltet) → kanonischer Auswahlwert eines Slots."""
    if slot_id == "person.bundesland":
        return _bundesland(f, kurzformen=True)
    if slot_id == "pflege.antragsart":
        if _treffer(r"weitergewaehr|continu", f):
            return "weitergewaehrung"
        if _treffer(r"erhoeh|increase", f):
            return "erhoehung"
        if _treffer(r"^(nein|no|nope)\b|noch nicht|not yet|noch kein|\bkein\w*\b|\bnot\b|\bnever\b|\bnie\b|"
                    r"erstantrag|erstmals|zuerkenn|first", f):
            return "zuerkennung"
        if _treffer(r"^(ja|jawohl|yes|yep|jep)\b|\b(schon|bereits|already)\b", f):
            return "erhoehung"
        return None
    if slot_id == "versicherung.pension":
        if _treffer(r"\bpva\b|pensionsversicherung|pension insurance", f):
            return "PVA"
        if _treffer(r"\bsvs\b|sozialversicherung der selbst", f):
            return "SVS"
        if _treffer(r"\bbvaeb\b|oeffentlich bedienstet", f):
            return "BVAEB"
        if _treffer(r"^(nein|no|none|keine?)\b|keine pension|no pension", f):
            return "keine"
        return None
    if slot_id == "versicherung.krankenversicherung":
        if _treffer(r"\boegk\b|\bogk\b|gesundheitskasse", f):
            return "ÖGK"
        if _treffer(r"\bsvs\b|sozialversicherung der selbst", f):
            return "SVS"
        if _treffer(r"\bbvaeb\b|oeffentlich bedienstet", f):
            return "BVAEB"
        return None
    if slot_id == "anliegen.fuer_wen":
        if _treffer(r"angehoerig|mutter|vater|eltern|\boma\b|\bopa\b|grossmutter|grossvater|tochter|\bsohn\b|"
                    r"partner|\bfrau\b|\bmann\b|schwester|bruder|relative|mother|father|parent|grand|daughter|"
                    r"\bson\b|wife|husband|sister|brother|family", f):
            return "angehoerige"
        if _treffer(r"\b(selbst|ich|mich|mir|myself|me|i)\b", f):
            return "selbst"
        return None
    if slot_id == "person.geschlecht":
        if _treffer(r"weiblich|female|\bfrau\b|^w$", f):
            return "weiblich"
        if _treffer(r"maennlich|\bmale\b|\bmann\b|^m$", f):
            return "männlich"
        if _treffer(r"divers", f):
            return "divers"
        return None
    if slot_id == "reha.form":
        if _treffer(r"ambulant|outpatient", f):
            return "ambulant"
        if _treffer(r"stationaer|inpatient|stationary", f):
            return "stationaer"
        if _treffer(r"nicht angegeben|not stated|keine angabe", f):
            return "nicht_angegeben"
        return None
    if slot_id == "termin.anlass":
        for wert, muster in _TERMIN_ANLASS:
            if _treffer(muster, f):
                return wert
        return None
    if slot_id == "termin.zeit":
        if _treffer(r"vormittag|morgens|in der frueh|\bfrueh\b|morning|before noon", f):
            return "vormittags"
        if _treffer(r"nachmittag|abends|afternoon|evening", f):
            return "nachmittags"
        if _EGAL.search(f) or _treffer(r"beides|jederzeit|immer|either|both|any ?time", f):
            return "egal"
    return None


# Anlass eines Termins aus freiem Text (Reihenfolge = Vorrang)
_TERMIN_ANLASS = (
    ("zahn", r"zahn|dentist|dental|teeth|tooth"),
    ("impfung", r"impf|vaccin|\bjab\b|booster"),
    ("kind", r"kinderarzt|kinderaerzt|paediat|pediat|\bkind|\bbaby|\bchild"),
    ("kontrolle", r"kontroll|nachsorge|nachuntersuch|follow-?up|check on my results|befundbesprech"),
    ("vorsorge", r"vorsorge|gesundenunters|check-?up|screening|praevent|prevent|mammograf|koloskop"),
    ("beschwerden", r"beschwerd|schmerz|\bweh\b|tut weh|\bkrank\b|fieber|husten|symptom|complaint|\bpain|\bsick\b|"
                    r"\bill\b|unwell|fever|cough"),
    ("beratung", r"berat|advice|consult|counsel"),
)

_TERMIN_WORT = re.compile(
    r"\b(?:arzt|zahnarzt|fach(?:arzt|aerzt\w*)|kinderarzt|haus(?:arzt|aerztin)|kontroll|vorsorge|impf|untersuchungs|"
    r"nachsorge)?termin\w*|\bappointment"
)
_TERMIN_WUNSCH = re.compile(
    r"moechte|brauche|braucht|\bwill\b|wuensche|haett?e gerne?|suche|vereinbar|ausmach|bekomm|kriegen|organisier|"
    r"vorbereit|buchen|\bneed|\bwant|would like|like to|\bbook|\bmake\b|schedule|arrange|\bget\b|prepare|looking for|"
    r"help me"
)
# Fahrt, Kosten oder Zuschuss zu einem Termin sind ein Leistungsthema, keine Terminvorbereitung
_TERMIN_KOSTEN = re.compile(r"fahrt|transport|taxi|kosten|zahlt|bezahl|zuschuss|\bpay|\bcost|\bride\b|refund")
_TERMIN_ERLEDIGT = re.compile(
    r"wahrgenommen|\bwar (heute |gestern |schon )?(beim|bei der|dort|da)\b|erledigt|hinter mir|attended|\bdone\b|"
    r"\bwent\b|\bwas at\b|had my"
)
# Uhrzeit in absteigender Genauigkeit: „10:30“ / „10.30 Uhr“, dann „um 10“, dann „14 Uhr“ / „3 pm“
_UHRZEIT = (
    re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\s*(uhr|h|am|pm)?\b"),
    re.compile(r"\b(?:um|at|gegen)\s+([01]?\d|2[0-3])()\s*(uhr|h|am|pm|o'?clock)?\b"),
    re.compile(r"\b([01]?\d|2[0-3])()\s*(uhr|am|pm)\b"),
)
_DATUM_MUSTER = re.compile(
    r"\d{1,2}\.\s?\d{1,2}\.\s?\d{4}|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{4}|\b\d{1,2}\.\s?\d{1,2}\."
)

# Sach- und Vergleichsfragen zu Leistungen des Katalogs („Was ist der Unterschied zwischen Kur und Reha?“)
_VERGLEICH = re.compile(r"unterschied|vergleich|\boder\b|\bvs\b|versus|difference|compare|\bor\b")
_DEFINITION = re.compile(
    r"^(was|wie) (ist|sind|bedeutet|bedeuten|heisst|funktioniert)\b|^what (is|are|does)\b|^(erklaer|explain)"
)

_STATUS_FRAGE = re.compile(
    r"\bwie weit\b|was ist (denn )?(noch |jetzt )?offen|\bnoch offen\b|was fehlt( denn)? noch|"
    r"was (muss|soll) ich (denn )?noch\b|wo stehe? ich|\bstand (meine|meiner|meines|des|der|von)\b|"
    r"\bstatus (meine|meiner|meines|des|der|von)\b|ueberblick (ueber )?meine|"
    r"what('s| is) (still )?(open|left|pending|missing)|\bstill (open|to do|pending)\b|\bhow far\b|"
    r"where do i stand|status of my|my progress|what do i still"
)


def _termin_wunsch(f: str) -> bool:
    if not _TERMIN_WORT.search(f) or _TERMIN_KOSTEN.search(f):
        return False
    return bool(_TERMIN_WUNSCH.search(f)) or len(f.split()) <= 4


def _datum(text: str) -> str | None:
    for muster, reihenfolge in (
        (r"(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})", "tmj"),
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", "jmt"),
        (r"(\d{1,2})/(\d{1,2})/(\d{4})", "tmj"),
    ):
        m = re.search(muster, text)
        if not m:
            continue
        teile = dict(zip(reihenfolge, (int(g) for g in m.groups())))
        try:
            d = date(teile["j"], teile["m"], teile["t"])
        except ValueError:
            return None
        return f"{d.day:02d}.{d.month:02d}.{d.year:04d}"
    return None


def _termin_datum(text: str, heute: date | None = None) -> str | None:
    """Datum eines gemeldeten Termins; „12.11.“ ohne Jahr = nächster solcher Tag."""
    if d := _datum(text):
        return d
    m = re.search(r"\b(\d{1,2})\.\s?(\d{1,2})\.(?!\s?\d)", text)
    if not m:
        return None
    heute = heute or date.today()
    for jahr in (heute.year, heute.year + 1):
        try:
            d = date(jahr, int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
        if d >= heute:
            return f"{d.day:02d}.{d.month:02d}.{d.year:04d}"
    return None


def _uhrzeit(text: str) -> str:
    """Uhrzeit HH:MM aus freiem Text (Datumsangaben werden vorher entfernt); "" wenn keine."""
    rest = _DATUM_MUSTER.sub(" ", text.casefold())
    m = next((m for muster in _UHRZEIT if (m := muster.search(rest))), None)
    if not m:
        return ""
    stunde, minute, zusatz = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if zusatz == "pm" and stunde < 12:
        stunde += 12
    return f"{stunde:02d}:{minute:02d}"


def _zahl(f: str) -> str | None:
    m = re.search(r"\b(\d{1,2})\b", f)
    if m:
        return str(int(m.group(1)))
    for wort in re.findall(r"[a-z]+", f):
        if wort in _ZAHLWORTE:
            return str(_ZAHLWORTE[wort])
    return None


def normalisiere(slot_id: str, text: str) -> str | None:
    """Antwort auf eine Rückfrage → gültiger Slot-Wert oder None (de + en)."""
    slot = SLOTS.get(slot_id)
    roh = text.strip().strip(".!?").strip()
    if slot is None or not roh:
        return None
    if slot.typ == "auswahl":
        f = _falte(roh)
        wert = next((o for o in slot.optionen if _falte(o) == f), None)
        if wert is None:
            labels = [*texte.OPTION_LABEL.get(slot_id, {}).items(), *texte.KNOPF_LABEL.get(slot_id, {}).items()]
            wert = next((o for o, lab in labels if f in (_falte(lab["de"]), _falte(lab["en"]))), None)
        if wert is None:
            wert = _auswahl(slot_id, f)
    elif slot.typ == "datum":
        wert = _datum(roh)
    elif slot.typ == "zahl":
        wert = _zahl(_falte(roh))
    elif slot_id == "termin.uhrzeit":
        wert = _uhrzeit(roh) or None
    else:
        wert = " ".join(roh.split())
    return wert if wert is not None and slot.gueltig(wert) else None


def extrahiere(text: str, szenarien: list[str] | None = None) -> dict[str, str]:
    """Angaben, die nebenbei in freiem Text stehen (Bundesland, Träger, für wen, Antragsart, Alter des Kindes)."""
    f = _falte(text)
    werte: dict[str, str] = {}
    if land := _bundesland(f, kurzformen=False):
        werte["person.bundesland"] = land
    if _treffer(r"\bpva\b|pensionsversicherung", f):
        werte["versicherung.pension"] = "PVA"
    elif m := re.search(r"pension\w*\W+(?:\w+\W+){0,4}?(svs|bvaeb)\b|\b(svs|bvaeb)\W+(?:\w+\W+){0,4}?pension", f):
        werte["versicherung.pension"] = (m.group(1) or m.group(2)).upper()
    if _treffer(r"\boegk\b|gesundheitskasse", f):
        werte["versicherung.krankenversicherung"] = "ÖGK"
    elif m := re.search(r"versichert\w*\W+(?:\w+\W+){0,4}?(svs|bvaeb)\b|\b(svs|bvaeb)\W+(?:\w+\W+){0,4}?"
                        r"(?:versichert|insured)|insured\W+(?:\w+\W+){0,4}?(svs|bvaeb)\b", f):
        werte["versicherung.krankenversicherung"] = next(g for g in m.groups() if g).upper()
    if _treffer(r"\b(meine?n?|my) (mutter|vater|eltern|oma|opa|grossmutter|grossvater|frau|mann|partner\w*|"
                r"schwester|bruder|mother|father|parents?|grandmother|grandfather|grandma|grandpa|wife|husband|"
                r"sister|brother)\b|angehoerig|\ba relative\b", f):
        werte["anliegen.fuer_wen"] = "angehoerige"
    elif _treffer(r"\bfuer mich( selbst)?\b|\bfor myself\b|\bich selbst\b", f):
        werte["anliegen.fuer_wen"] = "selbst"
    if _treffer(r"\b(bezieht|bekommt|erhaelt|hat) (schon|bereits) pflegegeld|"
                r"already (gets|receives|has|get|receive) (care|attendance) allowance", f):
        werte["pflege.antragsart"] = "erhoehung"
    elif _treffer(r"\b(bezieht|bekommt|erhaelt|hat) (noch )?kein pflegegeld|no (care|attendance) allowance|"
                  r"(does not|doesn't) (yet )?(get|receive|have) (any )?(care|attendance) allowance", f):
        werte["pflege.antragsart"] = "zuerkennung"
    if "kind" in (szenarien or []) or _treffer(r"\bkind|\bsohn\b|tochter|baby|child|\bson\b|daughter", f):
        if m := re.search(r"\b(\d{1,2})\s?-?\s?(?:jahre alt|jahre\b|jaehrig|years? old|year-old)", f):
            werte["kind.alter"] = str(int(m.group(1)))
    return {k: v for k, v in werte.items() if SLOTS[k].gueltig(v)}


_PFLEGEGELD_BETRAG = re.compile(
    r"(pflegegeld|care allowance|attendance allowance).*(wie ?viel|hoehe|\bhoch\b|betrag|betraege|euro|€|"
    r"how much|amount)|(wie ?viel|hoehe|\bhoch\b|betrag|betraege|how much|amount).*(pflegegeld|care allowance)"
)
_EKODEX_STARK = re.compile(r"\bpzn\b|\b\d{7}\b|erstattungskodex|\beko\b|\bbox\b")
_EKODEX_SCHWACH = re.compile(r"bewillig|chefarzt|chefaerzt|approv|pre-?authori|reimburs")
_MEDIKAMENT = re.compile(r"medikament|arznei|tablette|praeparat|medicine|medication|\bdrug|\bpill")
_STOPPWOERTER = set(
    "muss mein meine meinen meiner mein das der die dem den ein eine einen ist sind wird werden wurde braucht "
    "brauche ich man bei fuer von vom zum zur mit und oder auch noch schon wie was wer wann welche welcher "
    "welches kann koennen darf soll sollte bitte medikament medikamente arznei arzneimittel tablette tabletten "
    "praeparat bewilligt bewilligung bewilligungspflichtig chefarzt chefaerztlich chefaerztliche box gelb gelbe "
    "gelben gruen gruene gruenen erstattungskodex eko kasse krankenkasse rezept pzn reha kur pflegegeld antrag "
    "does need needs must my the this that is are be approved approval reimbursed reimbursement medicine "
    "medication drug drugs pill pills prior authorisation authorization yellow green covered insurance "
    "for of a an to it do i".split()
)

_STATUS_BEFEHLE = (
    ("antrag_einreichen", r"eingereicht|abgeschickt|abgegeben|eingeschickt|submitted|sent off|handed in"),
    ("antrag_unterschreiben", r"unterschrieben|\bsigned\b"),
    ("antrag_ausfuellen", r"ausgefuellt|filled (in|out)"),
)


def _suchwoerter(text: str) -> list[str]:
    """Mögliche Medikamentennamen (ursprüngliche Schreibweise) aus einer Frage."""
    woerter = []
    for w in re.findall(r"[A-Za-zÄÖÜäöüß][\wÄÖÜäöüß-]{2,}", text):
        if _falte(w) not in _STOPPWOERTER and w not in woerter:
            woerter.append(w)
    return woerter


def _euro(betrag: float, sprache: str) -> str:
    s = f"{betrag:,.2f}"
    if sprache == "de":
        return s.replace(",", " ").replace(".", ",").replace(" ", ".") + " €"
    return f"€{s}"


def _kuerzen(text: str, max_len: int = 300) -> str:
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rsplit(" ", 1)[0] + " …"


def _basis(sprache: str) -> str:
    """Sprache der Textbausteine: de/en direkt, weitere Sprachen werden aus dem Englischen übersetzt."""
    return sprache if sprache in SPRACHEN else "en"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class Lotse:
    """Zustandslose Engine; der Zustand liegt in `Sitzung`."""

    def neue_sitzung(self, sprache: str = "de", stil: str = "einfach") -> Sitzung:
        _pruefe_einstellung(sprache, stil)
        s = Sitzung(id=uuid.uuid4().hex, sprache=sprache, stil=stil)
        inhalt = Inhalt(art="start")
        inhalt.neu("begruessung")
        inhalt.neu("begruessung_details", nur_ausfuehrlich=True)
        s.letzte = inhalt
        return s

    def aktuell(self, s: Sitzung) -> Antwort:
        """Aktueller Stand der Sitzung (letzte Antwort, neu gerendert)."""
        return self._antwort(s, s.letzte or Inhalt(art="start"), protokoll=False)

    def einstellungen(self, s: Sitzung, sprache: str | None = None, stil: str | None = None) -> Antwort:
        sprache = sprache or s.sprache
        stil = stil or s.stil
        _pruefe_einstellung(sprache, stil)
        s.sprache, s.stil = sprache, stil
        return self._antwort(s, s.letzte or Inhalt(art="start"))

    def wiederhergestellt(self, s: Sitzung) -> Antwort:
        """Antwort nach Import bzw. Laden eines Falls: Stand der Fallakte."""
        inhalt = self._status(s, "")
        inhalt.absaetze.insert(0, Absatz(beide("wiederhergestellt")))
        return self._antwort(s, inhalt)

    # -- Nachricht ----------------------------------------------------------

    def nachricht(self, s: Sitzung, text: str) -> Antwort:
        text = " ".join((text or "").split())[:2000]
        if not text:
            inhalt = Inhalt(art="fehler")
            inhalt.neu("leer")
            return self._antwort(s, inhalt)
        s.verlauf.append({"rolle": "nutzer", "text": text})

        f = _falte(text)
        entscheidung = grenzen.pruefe_anfrage(text)
        durch_ki = False
        # Erkannte Terminwünsche und Antworten auf Terminfragen sind organisatorisch („eine Impfung“, „Beschwerden“);
        # die Regeln der ersten Stufe gelten trotzdem.
        termin_kontext = "?" not in text and (_termin_wunsch(f) or (
            s.offene_frage in TERMIN_SLOTS and normalisiere(s.offene_frage, text) is not None))
        if entscheidung.erlaubt and llm.aktiv() and not termin_kontext:
            # Zweite Stufe für Formulierungen, die die Regeln nicht kennen (Dialekt, andere Sprachen)
            entscheidung = grenzen.ablehnung(llm.grenzkategorie(text))
            durch_ki = not entscheidung.erlaubt
        if not entscheidung.erlaubt:
            inhalt = self._grenze(entscheidung)
            inhalt.ki_verstanden = durch_ki
            return self._antwort(s, inhalt)

        if schritt_id := self._statusbefehl(s, text):
            return self.setze_status(s, schritt_id, "erledigt")

        if (antwort := self._termin_meldung(s, text, f)) is not None:
            return antwort
        if s.offene_frage in TERMIN_SLOTS and (antwort := self._termin_antwort(s, text, f)) is not None:
            return antwort
        if _STATUS_FRAGE.search(f):
            return self._antwort(s, self._status(s, text))
        if _termin_wunsch(f):
            return self._antwort(s, self._termin_start(s, _auswahl("termin.anlass", f)))
        if (leistungsfrage := self._leistungsfrage(text, f)) is not None:
            return self._antwort(s, leistungsfrage)

        szenarien = list(katalog.erkenne_szenarien(text))
        spezial = self._spezialfrage(f, text)
        inhalt = Inhalt(art="fall")
        geantwortet = False

        extrahiert = extrahiere(text, szenarien or s.szenarien)
        if extrahiert.get("anliegen.fuer_wen") == "angehoerige" and katalog.vorsorge_hinweise(text):
            del extrahiert["anliegen.fuer_wen"]  # „Mein Vater hatte Darmkrebs“: Vorsorge für die fragende Person
        neu_genannt = any(s.werte.get(k) != v for k, v in extrahiert.items())

        if s.offene_frage and not spezial:
            slot_id = s.offene_frage
            wert = normalisiere(slot_id, text)
            if wert is None and _UEBERSPRINGEN.search(f):
                if "unbekannt" in SLOTS[slot_id].optionen:
                    wert = "unbekannt"
                else:
                    s.uebersprungen.add(slot_id)
                    s.offene_frage = None
                    inhalt.neu("uebersprungen")
                    geantwortet = True
            if wert is None and not geantwortet and slot_id == "person.bundesland" \
                    and self._bundesland_aus_ort(s, f, inhalt):
                s.offene_frage = None  # „Graz“ beantwortet die Frage nach dem Bundesland
                geantwortet = True
            if wert is None and not geantwortet and SLOTS[slot_id].typ == "auswahl" and llm.aktiv():
                wert = llm.verstehe(text, s.sprache)["slots"].get(slot_id)  # Antwort in anderer Sprache
                inhalt.ki_verstanden = wert is not None
            if wert is not None:
                self._setze_wert(s, slot_id, wert, inhalt)
                s.offene_frage = None
                geantwortet = True
            elif not (geantwortet or szenarien or neu_genannt or "?" in text or len(text.split()) >= 5):
                return self._frage_erneut(s, slot_id)

        neu_erkannt = self._uebernimm(s, extrahiert, inhalt)
        neu_erkannt = self._bundesland_aus_ort(s, f, inhalt) or neu_erkannt

        if spezial:
            return self._antwort(s, self._mit_quelldaten(spezial))

        suchtext = ""
        if not szenarien and not geantwortet and not neu_erkannt and llm.aktiv():
            ki = llm.verstehe(text, s.sprache)
            if ki.get("art") == "termin":
                # Termin mit Datum in anderer Sprache gemeldet („Randevum 20.11.2026 saat 09:15“) → eintragen
                if _termin_datum(text) and (antwort := self._termin_meldung(s, text, f, termin_erkannt=True)):
                    antwort.modus = "ki"
                    return antwort
                inhalt = self._termin_start(s, ki["slots"].get("termin.anlass"))
                inhalt.ki_verstanden = True
                return self._antwort(s, inhalt)
            if ki.get("art") == "status":
                inhalt = self._status(s, text)
                inhalt.ki_verstanden = True
                return self._antwort(s, inhalt)
            suchtext = ki.get("suche", "")
            if ki.get("art") == "frage" and suchtext:
                # Sachfrage, z. B. auf Türkisch: Sonderfragen und Suche über die deutschen Stichworte;
                # genannte Werte („Stufe 3“) sind Teil der Frage, keine Angabe zur Person
                if spezial := self._spezialfrage(_falte(suchtext), suchtext):
                    inhalt = self._mit_quelldaten(spezial)
                    inhalt.ki_verstanden = True
                    return self._antwort(s, inhalt)
                inhalt.ki_verstanden = True
            else:
                szenarien = ki["szenarien"]
                slots = {k: v for k, v in ki["slots"].items() if k not in TERMIN_SLOTS}
                neu_erkannt = self._uebernimm(s, slots, inhalt)
                inhalt.ki_verstanden = bool(szenarien or neu_erkannt or suchtext)

        if szenarien:
            s.fokus = self._fokus(text)
            self._neue_szenarien(s, szenarien)
            return self._antwort(s, self._fall(s, inhalt, neue_szenarien=szenarien,
                                               vorsorge=katalog.vorsorge_hinweise(text)))
        if geantwortet or (neu_erkannt and s.szenarien):
            return self._antwort(s, self._fall(s, inhalt))
        if neu_erkannt:
            inhalt.neu("wissen_tipp", beispiel={sp: texte.BEISPIELE["pflege"][sp] for sp in SPRACHEN})
            return self._antwort(s, inhalt)

        try:
            treffer = self._relevante(text, suchtext)
        except FileNotFoundError:
            fehlt = Inhalt(art="wissen")
            fehlt.neu("quellen_fehlen")
            return self._antwort(s, fehlt)
        passend = [l for l, p in katalog.passende_leistungen(f"{text} {suchtext}".strip()) if p >= PASSEND_MIN]
        if not treffer and passend:
            # Keine belastbare Fundstelle, aber eine konkret passende Leistung: als Anliegen anbieten
            s.fokus = [l.id for l in passend]
            neue = [passend[0].szenarien[0]]
            self._neue_szenarien(s, neue)
            return self._antwort(s, self._fall(s, inhalt, neue_szenarien=neue))
        wissen_inhalt = self._wissen(text, treffer)
        wissen_inhalt.ki_verstanden = inhalt.ki_verstanden
        return self._antwort(s, wissen_inhalt)

    @staticmethod
    def _mit_quelldaten(erzeuge) -> Inhalt:
        """Wissensabfragen brauchen die SV-Box-Daten; fehlen sie, sagt der Lotse das, statt abzubrechen."""
        try:
            return erzeuge()
        except FileNotFoundError:
            inhalt = Inhalt(art="wissen")
            inhalt.neu("quellen_fehlen")
            return inhalt

    # -- Dokument -----------------------------------------------------------

    def dokument(self, s: Sitzung, name: str, inhalt_bytes: bytes) -> Antwort:
        try:
            dok = dokument.lade_dokument(name, inhalt_bytes)
        except dokument.BildNichtLesbar as e:
            fehler = Inhalt(art="fehler")
            fehler.neu(f"bild_{e.grund}" if e.grund in ("ki_inaktiv", "format", "unlesbar") else "dokument_fehler")
            return self._antwort(s, fehler)
        except ValueError:
            dok = None
        if dok is None or not any(seite.strip() for seite in dok.seiten):
            fehler = Inhalt(art="fehler")
            fehler.neu("dokument_fehler")
            return self._antwort(s, fehler)
        empfehlungen = dokument.empfehlungen(dok)
        stammdaten = dokument.stammdaten(dok)
        impfungen = dokument.impfeintraege(dok)
        medikamente = dokument.medikamente(dok)
        s.dokumente.append({"name": dok.name, "seiten": len(dok.seiten), "transkribiert": dok.transkribiert})
        s.verlauf.append({"rolle": "nutzer", "text": f"[{dok.name}]"})

        inhalt = Inhalt(art="fall", ki_verstanden=dok.transkribiert)
        n = len(dok.seiten)
        inhalt.neu("dokument_gelesen", name=dok.name, seiten={
            "de": f"{n} Seite" if n == 1 else f"{n} Seiten", "en": f"{n} page" if n == 1 else f"{n} pages",
        })
        if dok.transkribiert:
            inhalt.neu("dokument_transkribiert")
        zeilen = []
        for e in empfehlungen:
            if not _katalog_hat(e.thema):
                continue
            liste = s.dok_empfehlungen.setdefault(e.thema, [])
            if all(x.zitat != e.zitat for x in liste):
                liste.append(e)
            zeilen.append(beide("dokument_steht", zitat=e.zitat, seite=e.seite))
            inhalt.marke(e.quelle)
        if zeilen:
            inhalt.zeilen(zeilen)
        elif not impfungen:
            inhalt.neu("dokument_keine_empfehlung")
        if any(e.thema == "kontrolltermine" for e in empfehlungen) and _katalog_hat("kontrolltermine"):
            inhalt.neu("termin_angebot")

        if impfungen:
            self._impfungen_uebernehmen(s, dok, impfungen, inhalt)
        if medikamente:
            self._medikamente_uebernehmen(s, dok, medikamente, inhalt)

        uebernommen: list[str] = []
        for sd in stammdaten:
            slot = SLOTS.get(sd.slot)
            if slot is None or not slot.gueltig(sd.wert):
                continue
            if s.herkunft.get(sd.slot, {}).get("art") == "dialog":
                continue  # Angaben aus dem Gespräch haben Vorrang
            s.werte[sd.slot] = sd.wert
            s.herkunft[sd.slot] = {"art": "dokument", "dokument": dok.name, "seite": sd.seite}
            if sd.slot not in uebernommen:
                uebernommen.append(sd.slot)
            # Wien ist Gemeinde und Bundesland zugleich; große Städte ergeben ihr Bundesland
            if sd.slot == "person.ort" and "person.bundesland" not in s.werte:
                land = "Wien" if _falte(sd.wert) == "wien" else (_stadt(_falte(sd.wert)) or (None,))[0]
                if land:
                    s.werte["person.bundesland"] = land
                    s.herkunft["person.bundesland"] = {"art": "dokument", "dokument": dok.name, "seite": sd.seite}
                    uebernommen.append("person.bundesland")
        if uebernommen:
            inhalt.neu("dokument_stammdaten", labels={
                sp: ", ".join(texte.slot_label(x, sp) for x in uebernommen) for sp in SPRACHEN
            })
        if s.offene_frage in s.werte:
            s.offene_frage = None

        neue = ["entlassung"] if empfehlungen and s.dok_empfehlungen else []
        if neue:
            s.fokus = []  # Empfehlungen aus dem Dokument stehen jetzt vorn
            self._neue_szenarien(s, neue)
        return self._antwort(s, self._fall(s, inhalt, neue_szenarien=neue))

    def _impfungen_uebernehmen(self, s: Sitzung, dok, impfungen: list, inhalt: Inhalt) -> None:
        """Dokumentierte Impfeinträge wörtlich auflisten – ohne Bewertung, ohne „fällig“."""
        vorhanden = {(i["impfung"], i["datum"], i["dokument"]) for i in s.impfungen}
        for e in impfungen:
            if (e.impfung, e.datum, dok.name) not in vorhanden:
                s.impfungen.append({"impfung": e.impfung, "datum": e.datum, "seite": e.seite, "dokument": dok.name})
        impfpass = re.search(r"impf(pass|ausweis|nachweis|karte|buch|dokumentation|zertifikat)",
                             f"{dok.name} {' '.join(dok.seiten)[:3000]}", re.IGNORECASE)
        inhalt.neu("impfungen_einleitung_impfpass" if impfpass else "impfungen_einleitung")
        inhalt.zeilen([beide("impfung_zeile", impfung=e.impfung, datum=e.datum, seite=e.seite) for e in impfungen])
        inhalt.neu("impfungen_arzt")
        if _katalog_hat("impfungen") and "impfungen" not in s.dok_leistungen:
            s.dok_leistungen.append("impfungen")

    def _medikamente_uebernehmen(self, s: Sitzung, dok, medikamente: list, inhalt: Inhalt) -> None:
        """Genannte Medikamente → Erstattungsstatus aller EKO-Einträge zum Namen (administrativ, keine Empfehlung).
        Der Brief nennt meist keine Packung; darum zählen alle Einträge, nicht ein willkürlich gewählter."""
        zeilen = []
        vorhanden = {(m["name_dokument"], m["dokument"]) for m in s.medikamente}
        for m in medikamente:
            suchname, eintraege = _eko_eintraege(m.name)
            if (m.name, dok.name) not in vorhanden:
                vorhanden.add((m.name, dok.name))
                s.medikamente.append({"name_dokument": m.name, "seite": m.seite, "dokument": dok.name,
                                      "eko_suche": suchname if eintraege else None})
            if not eintraege:
                zeilen.append(beide("medikament_nicht_gefunden", name=m.name, seite=m.seite))
                continue
            varianten = _eko_varianten(eintraege)
            marken = "".join(inhalt.marke(g[0].quelle) for g in varianten.values())
            if len(varianten) == 1:
                box = eintraege[0].box
                key = "medikament_zeile_alle" if len(eintraege) > 1 else "medikament_zeile_eins"
                zeilen.append({sp: t(key, sp, name=m.name, seite=m.seite, n=len(eintraege),
                                     box=texte.BOX_LABEL[box][sp], marken=marken) for sp in SPRACHEN})
            else:
                zeilen.append({sp: t("medikament_zeile_varianten", sp, name=m.name, seite=m.seite, marken=marken,
                                     varianten=_varianten_text(varianten, sp, beispiel=False)) for sp in SPRACHEN})
        inhalt.neu("medikamente_einleitung")
        inhalt.zeilen(zeilen)

    # -- Fallakte und Formular ---------------------------------------------

    def setze_status(self, s: Sitzung, schritt_id: str, status: str) -> Antwort:
        schritt = s.fallakte.setze(schritt_id, status)
        eintrag = s.fallakte.eintraege[schritt.leistung_id]
        inhalt = Inhalt(art="status")
        inhalt.neu("status_gesetzt", titel=eintrag.titel, schritt={sp: schritt.text[sp].rstrip(".") for sp in SPRACHEN},
                   status=texte.STATUS_LABEL[status])
        self._naechster(s, inhalt, schritt.leistung_id)
        return self._antwort(s, inhalt)

    def formular_pdf(self, s: Sitzung, form_id: str, leistung: str | None = None) -> bytes:
        """Vorausgefüllter Entwurf; `leistung` wählt die Vorauswahl (Standard: erste Leistung mit diesem Formular)."""
        if form_id not in FORMULARE:
            raise KeyError(form_id)
        mit_formular = [lid for lid in s.leistungen if katalog.leistung(lid).formular == form_id]
        if leistung is None and mit_formular:
            leistung = mit_formular[0]
        pdf = formulare.ausfuellen(form_id, dict(s.werte), leistung=leistung).pdf
        # Entwurf heruntergeladen → Ausfüllen ist „in Arbeit“
        if leistung in mit_formular:
            try:
                schritt = s.fallakte.schritt(f"{leistung}.antrag_ausfuellen")
            except KeyError:
                schritt = None
            if schritt is not None and schritt.status == "offen":
                s.fallakte.setze(schritt.id, "in_arbeit")
        return pdf

    # -- Termine (Vorbereitung, nie Buchung) ---------------------------------

    def termin_starten(self, s: Sitzung, anlass: str | None = None, leistung: str | None = None) -> Antwort:
        """Terminvorbereitung beginnen, optional mit Anlass oder aus einer Leistung (deren `termin_anlass`)."""
        if anlass is not None and anlass not in SLOTS["termin.anlass"].optionen:
            raise ValueError(f"Unbekannter Anlass: {anlass}")
        if leistung is not None:
            l = katalog.leistung(leistung)  # KeyError bei unbekannter Leistung
            anlass = anlass or l.termin_anlass
        return self._antwort(s, self._termin_start(s, anlass, leistung))

    def termin_aktualisieren(
        self, s: Sitzung, termin_id: str, datum: str | None = None, uhrzeit: str | None = None,
        status: str | None = None,
    ) -> Antwort:
        """Vereinbartes Datum/Uhrzeit eintragen oder Termin als erledigt markieren (KeyError, ValueError)."""
        termin = s.fallakte.termine[termin_id]
        if datum:
            datum = normalisiere("termin.datum", datum)
            if datum is None:
                raise ValueError("Datum bitte als TT.MM.JJJJ")
        if uhrzeit:
            uhrzeit = normalisiere("termin.uhrzeit", uhrzeit)
            if uhrzeit is None:
                raise ValueError("Uhrzeit bitte als HH:MM")
        if status not in (None, "vereinbart", "erledigt"):
            raise ValueError(f"Unbekannter Terminstatus: {status}")
        neues_datum = datum or termin.datum
        if (uhrzeit or status == "vereinbart") and not neues_datum:
            raise ValueError("Es fehlt das Datum des Termins")
        inhalt = Inhalt(art="termin")
        if datum or uhrzeit or status == "vereinbart":
            self._termin_eintragen(s, termin, neues_datum, uhrzeit or termin.uhrzeit, inhalt)
        if status == "erledigt":
            s.fallakte.setze(f"{termin.id}.wahrnehmen", "erledigt")
            inhalt.neu("termin_erledigt", titel=s.fallakte.eintraege[termin.id].titel)
        if not inhalt.absaetze:
            raise ValueError("Nichts zu ändern: datum, uhrzeit oder status angeben")
        self._naechster(s, inhalt)
        return self._antwort(s, inhalt)

    def termin_ics(self, s: Sitzung, termin_id: str) -> str:
        """Kalendereintrag (RFC 5545) eines vereinbarten Termins; KeyError/ValueError ohne Termin bzw. Datum."""
        termin = s.fallakte.termine[termin_id]
        sp = "de" if s.sprache == "de" else "en"
        info = _termin_info(termin)
        zeilen = [info.wo[sp]] if info and info.wo.get(sp) else []
        zeilen += [h[sp] for h in info.hinweise] if info else []
        zeilen.append(t("termin_beschreibung", sp))
        return ics(termin, s.fallakte.eintraege[termin.id].titel[sp], "\n".join(zeilen))

    def _termin_start(self, s: Sitzung, anlass: str | None, leistung: str | None = None) -> Inhalt:
        s.termin_entwurf = {"anlass": anlass or "", "ort": None, "zeit": None, "leistung": leistung}
        inhalt = Inhalt(art="termin")
        inhalt.neu("termin_start")
        return self._termin_weiter(s, inhalt)

    def _termin_weiter(self, s: Sitzung, inhalt: Inhalt) -> Inhalt:
        """Hintergrund → Nähe → Tageszeit (Use Case 3.3); danach der fertige Terminauftrag."""
        e = s.termin_entwurf or {}
        for slot_id, key in zip(TERMIN_SLOTS, ("anlass", "ort", "zeit")):
            if e.get(key) is None or (key == "anlass" and not e.get(key)):
                s.offene_frage = slot_id
                return inhalt
        s.offene_frage = None
        return self._termin_anlegen(s, inhalt)

    def _termin_antwort(self, s: Sitzung, text: str, f: str) -> Antwort | None:
        """Antwort auf eine Terminfrage; None, wenn die Nachricht ein neues Anliegen ist (Entwurf verfällt)."""
        slot_id = s.offene_frage
        slot = SLOTS[slot_id]
        if s.termin_entwurf is None:
            s.offene_frage = None
            return None
        if slot_id == "termin.ort" and (_UEBERSPRINGEN.search(f) or _EGAL.search(f)):
            wert = ""
        elif slot_id == "termin.ort" and _JA_NEIN.match(f):
            wert = s.werte.get("person.ort", "")  # „Ja, in meiner Nähe“ ohne Ortsangabe
        else:
            wert = normalisiere(slot_id, text)
            if wert is None and slot_id == "termin.zeit" and _UEBERSPRINGEN.search(f):
                wert = "egal"
        # Fragen, Statusfragen und längere Sätze mit erkennbarem Anliegen sind keine Antwort auf die Terminfrage;
        # kurze Antworten wie „Ich glaub, ich brauch eine Impfung“ schon.
        woerter = len(text.split())
        szenario = woerter >= 4 and bool(katalog.erkenne_szenarien(text))
        if "?" in text or _STATUS_FRAGE.search(f) or (szenario and (wert is None or woerter > 6)):
            s.termin_entwurf = None
            s.offene_frage = None
            return None
        inhalt = Inhalt(art="termin")
        if wert is None and slot.typ == "auswahl" and llm.aktiv():
            wert = llm.verstehe(text, s.sprache)["slots"].get(slot_id)  # Antwort in anderer Sprache
            inhalt.ki_verstanden = wert is not None
        if wert is None:
            if woerter >= 5:
                s.termin_entwurf = None
                s.offene_frage = None
                return None
            return self._frage_erneut(s, slot_id)
        s.termin_entwurf[slot_id.removeprefix("termin.")] = wert
        if wert:
            inhalt.neu("notiert", label=slot.label, wert={sp: texte.wert_anzeige(slot_id, wert, sp) for sp in SPRACHEN})
        if slot_id == "termin.ort" and "person.bundesland" not in s.werte:
            if land := _bundesland(_falte(wert), kurzformen=True):
                self._setze_wert(s, "person.bundesland", land, inhalt)
            else:
                self._bundesland_aus_ort(s, _falte(wert), inhalt)
        return self._antwort(s, self._termin_weiter(s, inhalt))

    def _termin_anlegen(self, s: Sitzung, inhalt: Inhalt) -> Inhalt:
        e = s.termin_entwurf or {}
        s.termin_entwurf = None
        termin = Termin(
            id=s.fallakte.neue_termin_id(),
            anlass=e.get("anlass") or "",
            ort=e.get("ort") or "",
            zeit=e.get("zeit") or "",
            bundesland=s.werte.get("person.bundesland", ""),
            leistung_id=e.get("leistung"),
            erstellt=datetime.now().isoformat(timespec="seconds"),
        )
        self._termin_in_akte(s, termin)
        return self._termin_auftrag(s, termin, inhalt)

    def _termin_in_akte(self, s: Sitzung, termin: Termin) -> None:
        anlass = _termin_anlass(termin)
        schritte = [{"id": k, "de": t(f"termin_schritt_{k}", "de"), "en": t(f"termin_schritt_{k}", "en")}
                    for k in TERMIN_KETTE]
        s.fallakte.neuer_termin(termin, beide("termin_titel", anlass=anlass), schritte)

    def _termin_auftrag(self, s: Sitzung, termin: Termin, inhalt: Inhalt) -> Inhalt:
        """Fertiger Terminauftrag: wohin (mit Quelle), Hinweise, Suchdienste, Anfragetext, nächster Schritt."""
        info = _termin_info(termin)
        if info and info.beschwerden_hinweis.get("de"):
            inhalt.absaetze.append(Absatz(dict(info.beschwerden_hinweis)))
        details = {}
        for sp in SPRACHEN:
            teile = [_termin_anlass(termin)[sp]]
            if termin.zeit:
                teile.append(texte.wert_anzeige("termin.zeit", termin.zeit, sp))
            if termin.ort:
                # „in der Nähe vom Westbahnhof“ nicht doppelt einleiten
                eigen = re.match(r"(in|im|bei|beim|nahe|naehe|near|close|around|um)\b", _falte(termin.ort))
                teile.append(termin.ort if eigen else t("termin_nahe", sp, ort=termin.ort))
            details[sp] = ", ".join(teile)
        inhalt.neu("termin_fertig", details=details)
        if info:
            marken = "".join(inhalt.marke(q) for q in info.quellen)
            if info.wo.get("de"):
                inhalt.absaetze.append(Absatz({sp: f"{t('termin_wo', sp, wo=info.wo[sp])} {marken}".strip()
                                               for sp in SPRACHEN}))
            inhalt.zeilen([{sp: f"• {h[sp]}" for sp in SPRACHEN} for h in info.hinweise])
            if info.suche:
                inhalt.neu("termin_suche", namen={sp: ", ".join(x["name"][sp] for x in info.suche) for sp in SPRACHEN})
        inhalt.neu("termin_anfrage")
        if s.sprache in WEITERE_SPRACHEN:
            inhalt.neu("termin_sprache_de")
        inhalt.neu("termin_datum_tipp")
        self._naechster(s, inhalt, termin.id)
        return inhalt

    def _termin_meldung(self, s: Sitzung, text: str, f: str, termin_erkannt: bool = False) -> Antwort | None:
        """„Termin am 12.11.2026 um 10:30“ → eintragen; „Termin wahrgenommen“ → erledigt. Sonst None."""
        if not termin_erkannt and not _TERMIN_WORT.search(f):
            return None
        datum = _termin_datum(text)
        offen = [tm for tid, tm in reversed(s.fallakte.termine.items()) if s.fallakte.termin_status(tid) != "erledigt"]
        if datum:
            inhalt = Inhalt(art="termin")
            vorbereitet = [tm for tm in offen if s.fallakte.termin_status(tm.id) == "vorbereitet"]
            termin = (vorbereitet or offen or [None])[0]
            if termin is None:
                # Termin ohne (fertige) Vorbereitung gemeldet: trotzdem notieren, damit es einen Kalendereintrag gibt
                e = s.termin_entwurf or {}
                termin = Termin(id=s.fallakte.neue_termin_id(),
                                anlass=_auswahl("termin.anlass", f) or e.get("anlass") or "",
                                ort=e.get("ort") or "", zeit=e.get("zeit") or "", leistung_id=e.get("leistung"),
                                bundesland=s.werte.get("person.bundesland", ""),
                                erstellt=datetime.now().isoformat(timespec="seconds"))
                self._termin_in_akte(s, termin)
            if s.offene_frage in TERMIN_SLOTS:
                s.offene_frage = None
            s.termin_entwurf = None
            self._termin_eintragen(s, termin, datum, _uhrzeit(text), inhalt)
            self._naechster(s, inhalt)
            return self._antwort(s, inhalt)
        if _TERMIN_ERLEDIGT.search(f) and "?" not in text and not _termin_wunsch(f):
            inhalt = Inhalt(art="termin")
            vereinbart = [tm for tm in offen if s.fallakte.termin_status(tm.id) == "vereinbart"]
            termin = (vereinbart or offen or [None])[0]
            if termin is None:
                inhalt.neu("termin_unbekannt")
                return self._antwort(s, inhalt)
            s.fallakte.setze(f"{termin.id}.wahrnehmen", "erledigt")
            inhalt.neu("termin_erledigt", titel=s.fallakte.eintraege[termin.id].titel)
            self._naechster(s, inhalt)
            return self._antwort(s, inhalt)
        return None

    def _termin_eintragen(self, s: Sitzung, termin: Termin, datum: str, uhrzeit: str, inhalt: Inhalt) -> None:
        termin.datum, termin.uhrzeit = datum, uhrzeit
        s.fallakte.setze(f"{termin.id}.eintragen", "erledigt")
        um = beide("uhrzeit_um", uhrzeit=uhrzeit) if uhrzeit else {sp: "" for sp in SPRACHEN}
        inhalt.neu("termin_vereinbart", titel=s.fallakte.eintraege[termin.id].titel, datum=datum, uhrzeit=um)

    def _anfrage_text(self, s: Sitzung, termin: Termin, sp: str) -> str:
        """Kopierfertiger Text für Telefon oder E-Mail (Formulierung der Person, keine Sachaussage)."""
        anlass = texte.ANFRAGE_ANLASS.get(termin.anlass, {}).get(sp, "")
        if termin.leistung_id and _katalog_hat(termin.leistung_id):
            titel = katalog.leistung(termin.leistung_id).titel[sp]
            anlass = f"{anlass} ({titel})".strip() if anlass else {"de": "für", "en": "for"}[sp] + f" {titel}"
        zeit = texte.ANFRAGE_ZEIT.get(termin.zeit, {}).get(sp, "")
        kv = s.werte.get("versicherung.krankenversicherung")
        versicherung = t("anfrage_versichert", sp, kv=kv) if kv and kv != "unbekannt" else t("anfrage_ecard", sp)
        return " ".join(t("anfrage_text", sp, anlass=anlass, zeit=zeit, versicherung=versicherung).split())

    # -- Sach- und Vergleichsfragen zu Leistungen ---------------------------

    def _leistungsfrage(self, text: str, f: str) -> Inhalt | None:
        """„Unterschied zwischen Kur und Reha?“ bzw. „Was ist die Ausgleichszulage?“ → kuratierte Kurztexte der
        klar passenden Leistungen samt Quellen, ohne neues Szenario; bei einer Leistung ergänzt um relevante
        Fundstellen. None, wenn die Frage dafür nicht passt (dann übliche Verarbeitung)."""
        try:
            if self._spezialfrage(f, text):
                return None  # Pflegegeldbetrag und Erstattungsstatus haben eigene, genauere Antworten
        except FileNotFoundError:
            pass
        klar = [l for l, p in katalog.passende_leistungen(text) if p >= PASSEND_MIN]
        vergleich = len(klar) >= 2 and _VERGLEICH.search(f) and ("?" in text or _treffer(r"unterschied|differen", f))
        definition = bool(klar) and _DEFINITION.search(f) and len(text.split()) <= 10
        if not (vergleich or definition):
            return None
        inhalt = Inhalt(art="wissen")
        inhalt.neu("leistung_erklaerung")
        for l in klar[:3]:
            marken = "".join(inhalt.marke(q) for q in l.quellen[:3])
            inhalt.absaetze.append(Absatz({sp: f"• {l.titel[sp]}: {l.kurz[sp]} {marken}".rstrip() for sp in SPRACHEN}))
            if l.details.get("de"):
                inhalt.absaetze.append(Absatz(dict(l.details), nur_ausfuehrlich=True))
            inhalt.zeilen([{sp: f"– {v[sp]}" for sp in SPRACHEN} for v in l.voraussetzungen], nur_ausfuehrlich=True)
        if len(klar) == 1:
            try:
                treffer = self._relevante(text)
            except FileNotFoundError:
                treffer = []
            if treffer:
                inhalt.neu("leistung_erklaerung_recht")
                zeilen = []
                for tr in treffer:
                    q = tr.quelle
                    n = inhalt.marke(q).strip("[]")
                    zeilen.append(beide("wissen_zeile", zitat=q.zitat or _kuerzen(tr.text), titel=q.titel,
                                        fundstelle=q.fundstelle or "–", n=n))
                inhalt.zeilen(zeilen)
        inhalt.neu("leistung_erklaerung_angebot")
        return inhalt

    # -- Weiterverfolgen ----------------------------------------------------

    def _status(self, s: Sitzung, text: str) -> Inhalt:
        """Stand der Fallakte: erledigt/offen je Leistung und Termin, nächster Schritt (statt neuem Fall)."""
        inhalt = Inhalt(art="status")
        fa = s.fallakte
        if not fa.eintraege:
            inhalt.neu("status_leer")
            inhalt.neu("wissen_tipp", beispiel={sp: texte.BEISPIELE["pflege"][sp] for sp in SPRACHEN})
            return inhalt
        f = _falte(text)
        leistungen = [e for e in fa.eintraege.values() if e.art == "leistung"]
        genannt = [e for e in leistungen if _titel_genannt(e, f)] or [e for e in leistungen if _stichwort_genannt(e, f)]
        wichtig = fa.relevante(s.leistungen[:PRIMAER])
        schritte = [x for e in wichtig for x in e.schritte]
        inhalt.neu("status_einleitung", erledigt=sum(x.status == "erledigt" for x in schritte), gesamt=len(schritte))
        zeilen = []
        for e in genannt or wichtig:
            if e.art == "termin":
                termin = fa.termine[e.termin_id]
                status = fa.termin_status(termin.id)
                um = beide("uhrzeit_um", uhrzeit=termin.uhrzeit) if termin.uhrzeit else {sp: "" for sp in SPRACHEN}
                zeilen.append(beide(f"status_termin_{status}", titel=e.titel, datum=termin.datum, uhrzeit=um))
                continue
            ns = e.naechster_schritt()
            erledigt = sum(x.status == "erledigt" for x in e.schritte)
            if ns is None:
                zeilen.append(beide("status_zeile_fertig", titel=e.titel))
            else:
                zeilen.append(beide("status_zeile", titel=e.titel, erledigt=erledigt, gesamt=len(e.schritte),
                                    schritt={sp: ns.text[sp].rstrip(".") for sp in SPRACHEN}))
        inhalt.zeilen(zeilen)
        if not genannt and (rest := len(fa.eintraege) - len(wichtig)):
            inhalt.neu("gefunden_weitere", n=rest)
        self._naechster(s, inhalt, genannt[0].leistung_id if genannt else None)
        return inhalt

    # -- intern: Ablauf -----------------------------------------------------

    def _spezialfrage(self, f: str, text: str) -> Callable[[], Inhalt] | None:
        """Pflegegeldbetrag oder Erstattungsstatus eines Medikaments?"""
        if _PFLEGEGELD_BETRAG.search(f):
            return partial(self._pflegegeld, text)
        if _EKODEX_STARK.search(f) or (_EKODEX_SCHWACH.search(f) and _MEDIKAMENT.search(f)):
            return partial(self._ekodex, text)
        if _EKODEX_SCHWACH.search(f) and (eintraege := self._ekodex_suche(text)):
            return partial(self._ekodex, text, eintraege)
        return None

    def _statusbefehl(self, s: Sitzung, text: str) -> str | None:
        f = _falte(text)
        if not _treffer(r"antrag|formular|application|\bform\b", f) or _treffer(r"\b(nicht|not|kein|noch)\b", f):
            return None
        for schritt_id, muster in _STATUS_BEFEHLE:
            if not _treffer(muster, f):
                continue
            kandidaten = [
                e for e in s.fallakte.eintraege.values()
                if any(x.kurz_id == schritt_id and x.status != "erledigt" for x in e.schritte)
            ]
            genannt = [e for e in kandidaten if any(_falte(e.titel[sp]) in f for sp in SPRACHEN)]
            if genannt or kandidaten:
                return f"{(genannt or kandidaten)[0].leistung_id}.{schritt_id}"
        return None

    def _fokus(self, text: str) -> list[str]:
        """Leistungen zur konkreten Frage: Vorsorgeprogramme bei familiärer Vorbelastung, dann Stichworttreffer."""
        ids = katalog.vorsorge_hinweise(text) + [l.id for l, _ in katalog.passende_leistungen(text)]
        return list(dict.fromkeys(ids))

    def _neue_szenarien(self, s: Sitzung, szenarien: list[str]) -> None:
        neu = [sz for sz in szenarien if sz not in s.szenarien]
        s.szenarien = list(dict.fromkeys(list(szenarien) + s.szenarien))
        if neu:
            s.fragen_gestellt = 0
            s.offene_frage = None  # Rückfrage für das neue Anliegen neu bestimmen
            s.termin_entwurf = None

    def _setze_wert(self, s: Sitzung, slot_id: str, wert: str, inhalt: Inhalt) -> None:
        s.werte[slot_id] = wert
        s.herkunft[slot_id] = {"art": "dialog"}
        s.uebersprungen.discard(slot_id)
        slot = SLOTS[slot_id]
        if slot.sensibel:
            inhalt.neu("notiert_sensibel", label=slot.label)
        else:
            inhalt.neu("notiert", label=slot.label,
                       wert={sp: texte.wert_anzeige(slot_id, wert, sp) for sp in SPRACHEN})

    def _bundesland_aus_ort(self, s: Sitzung, f: str, inhalt: Inhalt) -> bool:
        """Bundesland aus einer genannten Stadt („Graz“ → Steiermark), nur solange es noch fehlt."""
        if "person.bundesland" in s.werte or not (treffer := _stadt(f)):
            return False
        land, stadt = treffer
        s.werte["person.bundesland"] = land
        s.herkunft["person.bundesland"] = {"art": "ort", "ort": stadt}
        s.uebersprungen.discard("person.bundesland")
        if s.offene_frage == "person.bundesland":
            s.offene_frage = None
        inhalt.neu("notiert_ort", label=SLOTS["person.bundesland"].label, ort=stadt,
                   wert={sp: texte.wert_anzeige("person.bundesland", land, sp) for sp in SPRACHEN})
        return True

    def _uebernimm(self, s: Sitzung, werte: dict[str, str], inhalt: Inhalt) -> bool:
        neu = False
        for slot_id, wert in werte.items():
            if s.werte.get(slot_id) != wert:
                self._setze_wert(s, slot_id, wert, inhalt)
                if s.offene_frage == slot_id:
                    s.offene_frage = None
                neu = True
        return neu

    def _fall(self, s: Sitzung, inhalt: Inhalt, neue_szenarien: list[str] | None = None,
              vorsorge: list[str] | None = None) -> Inhalt:
        vorher = list(s.leistungen)
        self._aktualisiere_buendel(s)
        if neue_szenarien:
            labels = {sp: ", ".join(texte.SZENARIO_LABEL[x][sp] for x in neue_szenarien) for sp in SPRACHEN}
            inhalt.absaetze.insert(0, Absatz(beide("verstanden", szenarien=labels)))
        if neue_szenarien or set(s.leistungen) != set(vorher):
            n = len(s.leistungen)
            primaer = [katalog.leistung(lid) for lid in s.leistungen[:PRIMAER]]
            if n > 1:
                inhalt.neu("gefunden", n=n, wichtigste={sp: ", ".join(l.titel[sp] for l in primaer) for sp in SPRACHEN})
                if n > PRIMAER:
                    inhalt.neu("gefunden_weitere", n=n - PRIMAER)
            else:
                inhalt.neu("gefunden_eine" if n == 1 else "gefunden_keine")
            programme = [katalog.leistung(lid) for lid in (vorsorge or []) if lid in s.leistungen]
            if programme:
                inhalt.neu("vorsorge_einleitung")
                inhalt.zeilen(self._nutzen_zeilen(inhalt, programme))
            inhalt.zeilen([beide("leistung_zeile", titel=l.titel, kurz=l.kurz) for l in primaer],
                          nur_ausfuehrlich=True)
            inhalt.zeilen(self._nutzen_zeilen(inhalt, [l for l in primaer if l not in programme]),
                          nur_ausfuehrlich=True)
            inhalt.neu("anspruch_hinweis", nur_ausfuehrlich=True)
        self._naechster(s, inhalt, s.leistungen[0] if s.fokus and s.leistungen else None)
        if "entlassung" in s.szenarien and not s.dokumente:
            inhalt.neu("dokument_tipp")
        if s.offene_frage is None:
            s.offene_frage = self._naechste_frage(s)
            if s.offene_frage:
                s.fragen_gestellt += 1
            elif any(_formular_sichtbar(katalog.leistung(lid), s.werte.get("person.bundesland"))
                     for lid in s.leistungen):
                inhalt.neu("keine_fragen")
                inhalt.neu("formular_hinweis", nur_ausfuehrlich=True)
        return inhalt

    @staticmethod
    def _nutzen_zeilen(inhalt: Inhalt, leistungen: list) -> list[dict[str, str]]:
        """„Warum das hilft“ je Leistung – nur mit Beleg."""
        zeilen = []
        for l in leistungen:
            if l.nutzen.get("de") and l.nutzen_quelle is not None:
                n = inhalt.marke(l.nutzen_quelle).strip("[]")
                zeilen.append(beide("nutzen_zeile", titel=l.titel, nutzen=l.nutzen, n=n))
        return zeilen

    def _naechster(self, s: Sitzung, inhalt: Inhalt, leistung_id: str | None = None) -> None:
        schritt = s.fallakte.naechster_schritt(leistung_id) or s.fallakte.naechster_schritt()
        if schritt is not None:
            titel = s.fallakte.eintraege[schritt.leistung_id].titel
            inhalt.neu("naechster", titel=titel, schritt={sp: schritt.text[sp].rstrip(".") for sp in SPRACHEN})
        elif s.fallakte.eintraege:
            inhalt.neu("alles_erledigt")

    def _aktualisiere_buendel(self, s: Sitzung) -> None:
        land = s.werte.get("person.bundesland")
        # Leistungen zur konkreten Frage zuerst, dann die aus Dokumenten (Relevanzreihenfolge für „entlassung“)
        ids = [lid for lid in s.fokus if _katalog_hat(lid) and _in_region(katalog.leistung(lid), land)]
        rang = {l.id: i for i, l in enumerate(katalog.fuer_szenario("entlassung", land))}
        aus_dokument = [lid for lid in [*s.dok_empfehlungen, *s.dok_leistungen] if _katalog_hat(lid)]
        ids += sorted(dict.fromkeys(aus_dokument), key=lambda x: rang.get(x, len(rang)))
        for sz in s.szenarien:
            ids += [l.id for l in katalog.fuer_szenario(sz, land)]
        ids += [lid for lid, e in s.fallakte.eintraege.items() if e.art == "leistung" and e.hat_fortschritt()]
        s.leistungen = list(dict.fromkeys(ids))
        s.fallakte.behalte(s.leistungen)
        for lid in s.leistungen:
            self._ergaenze_eintrag(s, katalog.leistung(lid))
        s.fallakte.ordne(s.leistungen)

    def _ergaenze_eintrag(self, s: Sitzung, l) -> None:
        """Fallakten-Eintrag einer Leistung mit Schritten und Unterlagen. Unterlagen, die nur zum Formular gehören,
        stehen nur dort, wo das Formular gilt; wechselt das Bundesland, fallen noch offene wieder weg."""
        unterlagen: list[tuple[dict[str, str], Quelle | None]] = [(dict(u), None) for u in l.unterlagen]
        zum_formular = _formular_unterlagen(l)
        if _formular_sichtbar(l, s.werte.get("person.bundesland")):
            unterlagen += zum_formular
        elif l.id in s.fallakte.eintraege:
            s.fallakte.entferne_offene_unterlagen(l.id, [text for text, _ in zum_formular])
        s.fallakte.ergaenze(l.id, l.titel, l.schritte, unterlagen)
        self._zustaendigkeit_vermerken(s, l)

    def baue_fallakte(self, s: Sitzung, status: dict[str, str], historie: list[dict]) -> None:
        """Fallakte aus gespeicherten Status wiederherstellen; Texte kommen aus Katalog und Formularen.
        Unbekannte Schritte → KeyError."""
        for tid, termin in s.fallakte.termine.items():
            if tid not in s.fallakte.eintraege:
                self._termin_in_akte(s, termin)
        for lid in dict.fromkeys(x.split(".", 1)[0] for x in status):
            if lid not in s.fallakte.eintraege:
                self._ergaenze_eintrag(s, katalog.leistung(lid))
        for schritt_id, wert in status.items():
            s.fallakte.schritt(schritt_id).status = wert
        s.fallakte.historie = list(historie)
        self._aktualisiere_buendel(s)

    def _zustaendigkeit_vermerken(self, s: Sitzung, l) -> None:
        """Ist die zuständige Stelle durch eine Angabe geklärt, ist der Katalogschritt „zustaendigkeit_klaeren“ erledigt."""
        if not any(s.werte.get(sid) in zuordnung and s.werte.get(sid) != "unbekannt"
                   for sid, zuordnung in l.stelle_nach.items()):
            return
        try:
            schritt = s.fallakte.schritt(f"{l.id}.zustaendigkeit_klaeren")
        except KeyError:
            return
        if schritt.status == "offen":
            s.fallakte.setze(schritt.id, "erledigt")

    def _regional(self, s: Sitzung) -> bool:
        """Gibt es für die Anliegen regionale Angebote oder Formulare (dann zuerst nach dem Bundesland fragen)?"""
        leistungen = [katalog.leistung(lid) for lid in s.dok_empfehlungen if _katalog_hat(lid)]
        for sz in s.szenarien:
            leistungen += katalog.fuer_szenario(sz, None)
        return any(l.regionen or l.formular_regionen or l.regional for l in leistungen)

    def _naechste_frage(self, s: Sitzung) -> str | None:
        """Genau eine Rückfrage: Region → Zuständigkeit → Antragsart → Rest; nie Bekanntes oder Sensibles."""
        if s.fragen_gestellt >= MAX_RUECKFRAGEN:
            return None
        regional = "person.bundesland" not in s.werte and self._regional(s)
        kandidaten = ["person.bundesland"] if regional else []
        for lid in s.leistungen:
            kandidaten += katalog.leistung(lid).rueckfragen

        def rang(slot_id: str) -> int:
            if slot_id == "person.bundesland" and regional:
                return 0
            if slot_id.startswith("versicherung."):
                return 1
            return 2 if slot_id == "pflege.antragsart" else 3

        for slot_id in sorted(dict.fromkeys(kandidaten), key=rang):
            slot = SLOTS.get(slot_id)
            if (slot and not slot.sensibel and slot_id not in s.werte and slot_id not in s.uebersprungen
                    and not _ohne_bedeutung(slot_id, s.werte)):
                return slot_id
        return None

    def _frage_erneut(self, s: Sitzung, slot_id: str) -> Antwort:
        inhalt = Inhalt(art="fall")
        inhalt.neu("nicht_verstanden")
        slot = SLOTS[slot_id]
        if slot.optionen:
            inhalt.neu("moegliche_antworten", optionen={
                sp: ", ".join(texte.knopf_label(slot_id, o, sp) for o in slot.optionen) for sp in SPRACHEN
            })
        elif slot.typ == "datum":
            inhalt.neu("format_datum")
        return self._antwort(s, inhalt)

    # -- intern: Wissen -----------------------------------------------------

    def _grenze(self, entscheidung: Grenzentscheidung) -> Inhalt:
        """Begründete Ablehnung; offizielle Angebote (mit Quelle) statt medizinischer Beurteilung."""
        inhalt = Inhalt(art="grenze", grenze=entscheidung)
        inhalt.absaetze.append(Absatz({sp: entscheidung.antwort.get(sp, "") for sp in SPRACHEN}))
        zeilen = []
        for lid in grenzen.ALTERNATIVEN.get(entscheidung.kategorie or "", []):
            if not _katalog_hat(lid):
                continue
            l = katalog.leistung(lid)
            belege = l.quellen[:2]  # die ersten zwei Belege der Leistung genügen als Verweis
            nummern = ", ".join(inhalt.marke(q) for q in belege)
            zeilen.append({sp: f"{t('leistung_zeile', sp, titel=l.titel[sp], kurz=l.kurz[sp])} {nummern}".rstrip()
                           for sp in SPRACHEN})
        if zeilen:
            inhalt.neu("grenze_alternativen")
            inhalt.zeilen(zeilen)
        return inhalt

    def _pflegegeld(self, text: str) -> Inhalt:
        auskunft = wissen.wissensbasis().pflegegeld(2026)
        inhalt = Inhalt(art="wissen", quellen=list(auskunft.quellen))
        if not auskunft.betraege:
            inhalt.neu("pflegegeld_fehlt")
            return inhalt
        m = re.search(r"(?:stufe|level)\s*([1-7])\b", _falte(text))
        stufen = [int(m.group(1))] if m else sorted(auskunft.betraege)
        inhalt.neu("pflegegeld_einleitung", jahr=auskunft.jahr)
        inhalt.zeilen([
            {sp: t("pflegegeld_zeile", sp, stufe=st, betrag=_euro(auskunft.betraege[st], sp), n=1) for sp in SPRACHEN}
            for st in stufen if st in auskunft.betraege
        ])
        if auskunft.hinweis:
            marken = "".join(f"[{n}]" for n in range(1, len(auskunft.quellen) + 1))
            inhalt.absaetze.append(Absatz({sp: f"{auskunft.hinweis.get(sp, '')} {marken}".strip() for sp in SPRACHEN}))
        return inhalt

    def _ekodex_suche(self, text: str) -> list:
        wb = wissen.wissensbasis()
        pzn = re.search(r"\b\d{7}\b", text)
        for begriff in [pzn.group(0)] if pzn else _suchwoerter(text):
            if eintraege := wb.ekodex(begriff, k=3):
                return eintraege
        return []

    def _ekodex(self, text: str, eintraege: list | None = None) -> Inhalt:
        eintraege = eintraege if eintraege is not None else self._ekodex_suche(text)
        inhalt = Inhalt(art="wissen")
        if not eintraege:
            inhalt.neu("ekodex_nichts")
            return inhalt
        inhalt.neu("ekodex_einleitung")
        for e in eintraege:
            for q in e.quellen():
                inhalt.marke(q)
            n = inhalt.quellen.index(e.quelle) + 1
            inhalt.absaetze.append(Absatz({
                sp: t("ekodex_zeile", sp, name=e.name, pzn=e.pzn, erklaerung=e.erklaerung(sp), n=n) for sp in SPRACHEN
            }))
        return inhalt

    @staticmethod
    def _relevante(text: str, suchtext: str = "") -> list[Treffer]:
        """Belege, die die Frage abdecken (wissen.relevante): zuerst mit dem Originaltext, sonst mit den deutschen
        KI-Stichworten (Fragen in anderen Sprachen)."""
        wb = wissen.wissensbasis()
        treffer = wb.relevante(text, k=3)
        return treffer or (wb.relevante(suchtext, k=3) if suchtext and suchtext != text else [])

    def _wissen(self, text: str, treffer: list[Treffer]) -> Inhalt:
        """Wörtliche Zitate nur aus relevanten Treffern; sonst ehrlich „nichts Belastbares“ plus Angebote."""
        inhalt = Inhalt(art="wissen", frage=text)
        if not treffer:
            inhalt.neu("wissen_nichts")
            inhalt.neu("wissen_angebot", szenarien={
                sp: ", ".join(texte.SZENARIO_LABEL[x][sp] for x in katalog.SZENARIEN) for sp in SPRACHEN
            })
            return inhalt
        inhalt.neu("wissen_einleitung")
        zeilen = []
        for n, tr in enumerate(treffer, 1):
            q = tr.quelle
            inhalt.quellen.append(q)
            zitat = q.zitat or _kuerzen(tr.text)
            zeilen.append(beide("wissen_zeile", zitat=zitat, titel=q.titel, fundstelle=q.fundstelle or "–", n=n))
            inhalt.fakten.append({"n": n, "text": _kuerzen(tr.text, 1200), "quelle": f"{q.titel}, {q.fundstelle}"})
        inhalt.absaetze.append(Absatz({sp: "\n\n".join(z[sp] for z in zeilen) for sp in SPRACHEN}))
        return inhalt

    # -- intern: Ausgabe ----------------------------------------------------

    def _antwort(self, s: Sitzung, inhalt: Inhalt, protokoll: bool = True) -> Antwort:
        if inhalt.art not in ("grenze", "fehler"):
            s.letzte = inhalt  # Umschalten von Sprache/Darstellung rendert den letzten Fallstand neu
        sp, stil = _basis(s.sprache), s.stil
        ki_text = inhalt.ki_texte.get((sp, stil))
        if ki_text is None and inhalt.fakten and llm.aktiv():
            ki_text = inhalt.ki_texte[(sp, stil)] = llm.formuliere(inhalt.fakten, sp, stil, frage=inhalt.frage)
        text = ki_text or "\n\n".join(
            a.text[sp] for a in inhalt.absaetze if a.text.get(sp) and (stil == "ausfuehrlich" or not a.nur_ausfuehrlich)
        )
        rueckfrage = None
        if s.offene_frage:
            slot = SLOTS[s.offene_frage]
            grund = t(_grund(s.offene_frage) if inhalt.art in ("fall", "termin") else "zurueck_zur_frage", sp)
            rueckfrage = {
                "slot": slot.id,
                "frage": slot.frage[sp],
                "grund": grund,
                "typ": slot.typ,
                "optionen": [{"wert": o, "label": texte.knopf_label(slot.id, o, sp)} for o in slot.optionen],
            }
            text = f"{text}\n\n{grund} {slot.frage[sp]}".strip()
        buendel = [] if inhalt.grenze else [self._buendel_eintrag(s, lid, i) for i, lid in enumerate(s.leistungen)]
        antwort = Antwort(
            sitzung_id=s.id,
            text=text,
            rueckfrage=rueckfrage,
            buendel=buendel,
            quellen=[q.to_dict() for q in inhalt.quellen],
            grenze=inhalt.grenze.to_dict() if inhalt.grenze else None,
            fallakte=s.fallakte.to_dict(sp),
            modus="ki" if (ki_text or inhalt.ki_verstanden) else "regelbasiert",
            sprache=s.sprache,
            stil=stil,
            szenarien=[{"id": x, "label": texte.SZENARIO_LABEL[x][sp]} for x in s.szenarien],
            angaben=self._angaben(s),
            dokumente=[{"name": d["name"], "seiten": d["seiten"], "transkribiert": bool(d.get("transkribiert"))}
                       for d in s.dokumente],
            richtung=texte.richtung(s.sprache),
            weitere_anzahl=max(0, len(buendel) - PRIMAER),
            termine=[self._termin_eintrag(s, tm) for tm in s.fallakte.termine.values()],
            impfungen=[dict(i) for i in s.impfungen],
            medikamente=self._medikamente(s, sp),
            status_uebersicht=s.fallakte.uebersicht(sp, s.leistungen[:PRIMAER]),
        )
        if s.sprache in WEITERE_SPRACHEN:
            self._uebersetze(antwort, s.sprache)
        if protokoll:
            s.verlauf.append({"rolle": "lotse", "text": antwort.text})
        return antwort

    @staticmethod
    def _uebersetze(antwort: Antwort, sprache: str) -> None:
        """Text, Bündel, Termine, Fallakte und Beschriftungen in einem geprüften Modellaufruf übersetzen.
        Zitate, [n] und Zahlen bleiben unverändert; was scheitert, bleibt Englisch (mit Hinweis)."""
        felder: list[tuple[object, object]] = []  # (Container, Schlüssel bzw. Index)

        def feld(obj: dict | None, *keys: str) -> None:
            for k in keys:
                if obj is not None and isinstance(obj.get(k), str) and obj[k].strip():
                    felder.append((obj, k))

        def liste(werte: list) -> None:
            felder.extend((werte, i) for i, w in enumerate(werte) if isinstance(w, str) and w.strip())

        if antwort.rueckfrage:
            feld(antwort.rueckfrage, "frage", "grund")
            for o in antwort.rueckfrage["optionen"]:
                feld(o, "label")
        for b in antwort.buendel:
            feld(b, "titel", "kurz", "details", "nutzen")
            liste(b["voraussetzungen"])
            feld(b["stelle"], "name", "hinweis")
            feld(b["stelle"]["abhaengig_von"], "label")
            feld(b["formular"], "titel", "vorauswahl", "stelle", "hinweis", "ohne_unterlagen", "region_hinweis")
            for x in b["fehlende_angaben"]:
                feld(x, "label")
            for x in b["unterlagen"]:
                feld(x, "text", "region_hinweis")
            for x in b["einrichtungen"]:
                feld(x, "name")
            feld(b["regional"], "stelle")
            for x in b["dokument"]:
                feld(x, "text")
        for tm in antwort.termine:
            feld(tm, "anlass_label", "zeit", "wo")
            liste(tm["hinweise"])
            for x in tm["suche"]:
                feld(x, "name")
        fa = antwort.fallakte
        for e in fa["eintraege"]:
            feld(e, "titel")
            for x in e["schritte"] + e["unterlagen"]:
                feld(x, "text")
        feld(fa["naechster_schritt"], "titel", "text")
        for h in fa["historie"]:
            feld(h, "text", "titel")
        for x in antwort.szenarien:
            feld(x, "label")
        for x in antwort.angaben:
            feld(x, "label", "herkunft")
            if not x["sensibel"] and SLOTS[x["slot"]].typ == "auswahl":
                feld(x, "wert")
        for m in antwort.medikamente:
            feld(m["eko"], "erklaerung")
        feld(antwort.status_uebersicht, "naechster")

        # Titel, Labels und Werte im Fließtext genau so übersetzen wie auf Karten und in der Fallakte:
        # im Text durch ⟦Tn⟧ ersetzen und danach mit der Übersetzung des Einzelbegriffs füllen
        kandidaten = [b["titel"] for b in antwort.buendel] + [e["titel"] for e in fa["eintraege"]]
        kandidaten += [x["label"] for x in antwort.szenarien] + [tm["anlass_label"] for tm in antwort.termine]
        kandidaten += [x["label"] for x in antwort.angaben]
        kandidaten += [x["wert"] for x in antwort.angaben if not x["sensibel"] and SLOTS[x["slot"]].typ == "auswahl"]
        if fa["naechster_schritt"]:
            kandidaten.append(fa["naechster_schritt"]["text"].rstrip("."))
        text = antwort.text
        begriffe = sorted({b for b in kandidaten if len(b) >= 4 and b in text}, key=lambda b: (-len(b), b))
        for i, b in enumerate(begriffe):
            text = re.sub(rf"(?<!\w){re.escape(b)}(?!\w)", f"⟦T{i}⟧", text)

        quellen = [text] + [c[k] for c, k in felder] + begriffe
        uebersetzt = llm.uebersetze(quellen, sprache)
        fest = uebersetzt[1 + len(felder):]
        if uebersetzt[0] is not None:
            antwort.text = re.sub(r"⟦T(\d+)⟧", lambda m: fest[int(m.group(1))] or begriffe[int(m.group(1))],
                                  uebersetzt[0])
        for (c, k), u in zip(felder, uebersetzt[1:]):
            if u is not None:
                c[k] = u
        if any(u is not None for u in uebersetzt):
            antwort.modus = "ki"
        if any(u is None for u in uebersetzt):
            antwort.text = f"{t('uebersetzung_fehlt', 'en')}\n\n{antwort.text}"

    def _buendel_eintrag(self, s: Sitzung, lid: str, index: int = 0) -> dict:
        sp, ausf = _basis(s.sprache), s.stil == "ausfuehrlich"
        l = katalog.leistung(lid)
        land = s.werte.get("person.bundesland")
        formular = None
        fehlend: list[dict] = []
        form_quellen: list[Quelle] = []
        if _formular_sichtbar(l, land):
            f = formulare.formular(l.formular)
            adresse = f.adressen.get(land or "")
            regionen = [texte.wert_anzeige("person.bundesland", r, sp) for r in l.formular_regionen]
            formular = {
                "id": f.id,
                "titel": f.titel[sp],
                "vorauswahl": f.vorauswahl.get(lid, {}).get(sp, ""),
                "url": f"/api/sitzung/{s.id}/formular/{f.id}?leistung={lid}",
                "stelle": f.stelle[sp],
                "adresse": adresse["text"] if adresse else "",
                "hinweis": f.hinweise[sp],
                "ohne_unterlagen": f.ohne_unterlagen.get(sp, ""),
                "regionen": list(l.formular_regionen),
                "region_hinweis": t("formular_region_hinweis", sp, regionen=", ".join(regionen))
                if regionen and not land else "",
            }
            fehlend = [{"slot": x, "label": texte.slot_label(x, sp)}
                       for x in formulare.fehlende_pflichtangaben(f.id, dict(s.werte), leistung=lid)]
            form_quellen = [f.quelle, f.stelle_quelle, *f.hinweis_quellen, *([adresse["quelle"]] if adresse else [])]
        eintrag = s.fallakte.eintraege.get(lid)
        dok = [
            {"text": t("dokument_steht", sp, zitat=e.zitat, seite=e.seite), "zitat": e.zitat, "seite": e.seite,
             "quelle": e.quelle.to_dict()}
            for e in s.dok_empfehlungen.get(lid, [])
        ]
        stelle = _stelle(l, s.werte, sp)
        einrichtungen = [
            {"name": e["name"][sp], "regionen": list(e["regionen"]), "kontakt": e.get("kontakt", ""),
             "url": e.get("url", ""), "beleg": _beleg(e["quelle"]), "quelle": _quelle_dict(e["quelle"])}
            for e in l.einrichtungen_fuer(land)
        ]
        regional = None
        if (r := l.regional_fuer(land)) is not None:
            regional = {"bundesland": land, "stelle": r["stelle"][sp], "kontakt": r.get("kontakt", ""),
                        "url": r.get("url", ""), "beleg": _beleg(r["quelle"]), "quelle": _quelle_dict(r["quelle"])}
        quellen: list[dict] = []
        for q in [*l.quellen, *([stelle["quelle"]] if stelle["quelle"] else []),
                  *([l.nutzen_quelle] if l.nutzen_quelle and l.nutzen.get(sp) else []),
                  *form_quellen, *(e.quelle for e in s.dok_empfehlungen.get(lid, []))]:
            if (d := _quelle_dict(q)) not in quellen:
                quellen.append(d)
        for d in [*(e["quelle"] for e in einrichtungen), *([regional["quelle"]] if regional else [])]:
            if d not in quellen:
                quellen.append(d)
        return {
            "leistung_id": lid,
            "titel": l.titel[sp],
            "kurz": l.kurz[sp],
            "details": l.details[sp] if ausf else "",
            "voraussetzungen": [v[sp] for v in l.voraussetzungen] if ausf else [],
            "stelle": {**stelle, "quelle": _quelle_dict(stelle["quelle"]) if stelle["quelle"] else None},
            "formular": formular,
            "fehlende_angaben": fehlend,
            "unterlagen": self._unterlagen(l, eintrag, land, sp),
            "dokument": dok,
            "quellen": quellen,
            "beleg": l.beleg,
            "regionen": list(l.regionen),
            "regionen_anzeige": [texte.wert_anzeige("person.bundesland", r, sp) for r in l.regionen],
            "naechster_schritt": (ns.id if (ns := s.fallakte.naechster_schritt(lid)) else None),
            "primaer": index < PRIMAER,
            "nutzen": l.nutzen.get(sp, "") if l.nutzen_quelle is not None else "",
            "nutzen_quelle": _quelle_dict(l.nutzen_quelle) if l.nutzen_quelle and l.nutzen.get(sp) else None,
            "einrichtungen": einrichtungen,
            "regional": regional,
            "termin_anlass": l.termin_anlass,
        }

    @staticmethod
    def _unterlagen(l, eintrag, land: str | None, sp: str) -> list[dict]:
        """Unterlagen der Fallakte; ohne Bundesland tragen die zum regionalen Formular einen Hinweis auf die Region."""
        if eintrag is None:
            return []
        hinweis = ""
        if l.formular and l.formular_regionen and not land:
            regionen = ", ".join(texte.wert_anzeige("person.bundesland", r, sp) for r in l.formular_regionen)
            hinweis = t("formular_region_hinweis", sp, regionen=regionen)
        zum_formular = {" ".join(text["de"].lower().split()) for text, _ in _formular_unterlagen(l)} if hinweis else set()
        return [{**u.to_dict(sp), "region_hinweis": hinweis if " ".join(u.text["de"].lower().split()) in zum_formular
                 else ""} for u in eintrag.unterlagen]

    def _termin_eintrag(self, s: Sitzung, termin: Termin) -> dict:
        sp = _basis(s.sprache)
        info = _termin_info(termin)
        hinweise = [h[sp] for h in info.hinweise] if info else []
        if info and info.beschwerden_hinweis.get(sp):
            hinweise.insert(0, info.beschwerden_hinweis[sp])
        return {
            "id": termin.id,
            "anlass": termin.anlass,
            "anlass_label": _termin_anlass(termin)[sp],
            "ort": termin.ort,
            "zeit": texte.wert_anzeige("termin.zeit", termin.zeit, sp) if termin.zeit else "",
            "wo": info.wo.get(sp, "") if info else "",
            "hinweise": hinweise,
            "suche": [{"name": x["name"][sp], "url": x["url"], "beleg": _beleg(x["quelle"])} for x in info.suche]
            if info else [],
            # Für die Ordination: bei weiteren Sprachen auf Deutsch
            "anfrage_text": self._anfrage_text(s, termin, "de" if s.sprache in WEITERE_SPRACHEN else sp),
            "datum": termin.datum,
            "uhrzeit": termin.uhrzeit,
            "ics_url": f"/api/sitzung/{s.id}/termin/{termin.id}.ics" if termin.datum else "",
            "status": s.fallakte.termin_status(termin.id),
            "quellen": [q.to_dict() for q in info.quellen] if info else [],
        }

    @staticmethod
    def _medikamente(s: Sitzung, sp: str) -> list[dict]:
        """Genannte Medikamente mit Erstattungsstatus aller EKO-Einträge zum Namen (None ohne Treffer oder Daten)."""
        ergebnis = []
        for m in s.medikamente:
            eko = None
            if m.get("eko_suche"):
                suchname, eintraege = _eko_eintraege(m["eko_suche"])
                if eintraege:
                    eko = _eko_zusammenfassung(suchname, eintraege, sp, ausfuehrlich=s.stil == "ausfuehrlich")
            ergebnis.append({"name_dokument": m["name_dokument"], "seite": m["seite"], "dokument": m["dokument"],
                             "eko": eko})
        return ergebnis

    def _angaben(self, s: Sitzung) -> list[dict]:
        sp = _basis(s.sprache)
        angaben = []
        for slot_id, wert in s.werte.items():
            slot = SLOTS[slot_id]
            h = s.herkunft.get(slot_id, {})
            if h.get("art") == "dokument":
                herkunft = f"{texte.UI['aus_dokument'][sp]} {h['dokument']}, {texte.UI['seite'][sp]} {h['seite']}"
            elif h.get("art") == "ort":
                herkunft = f"{texte.UI['aus_ortsangabe'][sp]} {h['ort']}"
            else:
                herkunft = texte.UI["aus_gespraech"][sp]
            angaben.append({
                "slot": slot_id,
                "label": slot.label[sp],
                "wert": texte.UI["angabe_hinterlegt"][sp] if slot.sensibel else texte.wert_anzeige(slot_id, wert, sp),
                "sensibel": slot.sensibel,
                "herkunft": herkunft,
            })
        return angaben


def _stelle(l, werte: dict[str, str], sprache: str) -> dict:
    """Zuständige Stelle; `stelle_nach` löst sie über bekannte Angaben auf (mit Beleg, wenn vorhanden)."""
    hinweis = l.stelle.get("hinweis") or {}
    offen = [sid for sid, zuordnung in l.stelle_nach.items() if werte.get(sid) not in zuordnung]
    aufgeloest = not l.stelle_nach or len(offen) < len(l.stelle_nach)
    quelle = l.stelle_beleg_fuer(werte)
    return {
        "name": l.stelle_fuer(werte)[sprache],
        "kontakt": l.kontakt_fuer(werte),
        "hinweis": hinweis.get(sprache, ""),
        "aufgeloest": aufgeloest,
        "abhaengig_von": None if aufgeloest else {"slot": offen[0], "label": texte.slot_label(offen[0], sprache)},
        "quelle": quelle,
        "beleg": _beleg(quelle) if quelle else "",
    }


def _quelle_dict(q) -> dict:
    return q.to_dict() if isinstance(q, Quelle) else dict(q)


def _beleg(q) -> str:
    art = q.art if isinstance(q, Quelle) else q.get("art")
    return "extern" if art == "extern" else "lokal"


def _in_region(l, land: str | None) -> bool:
    return not l.regionen or land is None or land in l.regionen


def _formular_sichtbar(l, land: str | None) -> bool:
    """Formular nur, wo es gilt; ohne bekanntes Bundesland mit Hinweis auf die Region."""
    return bool(l.formular) and (not l.formular_regionen or land is None or land in l.formular_regionen)


def _formular_unterlagen(l) -> list[tuple[dict[str, str], Quelle | None]]:
    """Unterlagen, die nur zum Formular der Leistung gehören (Katalog und Formular-Registry)."""
    if not l.formular:
        return []
    return [(dict(u), None) for u in l.unterlagen_formular] + [
        (dict(u.text), u.quelle) for u in formulare.formular(l.formular).unterlagen_fuer(l.id)]


def _termin_anlass(termin: Termin) -> dict[str, str]:
    """Anzeige des Anlasses: Titel der Leistung (Termin aus einem Bündel), sonst Label des Anlasses."""
    if termin.leistung_id and _katalog_hat(termin.leistung_id):
        return dict(katalog.leistung(termin.leistung_id).titel)
    if termin.anlass in texte.OPTION_LABEL["termin.anlass"]:
        return dict(texte.OPTION_LABEL["termin.anlass"][termin.anlass])
    return {"de": "Arzttermin", "en": "Doctor's appointment"}


def _termin_info(termin: Termin):
    """Katalogangaben zum Anlass (wo, Hinweise, Suchdienste, Quellen); None ohne bekannten Anlass."""
    if termin.anlass not in SLOTS["termin.anlass"].optionen:
        return None
    return katalog.termin_info(termin.anlass, termin.bundesland or None)


def _titel_genannt(eintrag, f: str) -> bool:
    """Nennt der (gefaltete) Text den Titel dieser Leistung?"""
    return any(_falte(eintrag.titel[sp]) in f for sp in SPRACHEN)


def _stichwort_genannt(eintrag, f: str) -> bool:
    """Nennt der Text ein spezifisches Katalog-Stichwort (ab 5 Zeichen, Wortanfang) dieser Leistung?"""
    if not _katalog_hat(eintrag.leistung_id):
        return False
    return any(re.search(rf"\b{re.escape(_falte(w))}", f) for w in katalog.leistung(eintrag.leistung_id).stichworte
               if len(w) >= 5)


_EKO_MAX = 2000  # Einträge je Namenssuche (Namensanfang)
_EKO_VARIANTEN_TEXT = 4  # so viele Varianten nennt der Text; alle stehen in `varianten`


def _eko_eintraege(name: str) -> tuple[str, list]:
    """Alle EKO-Einträge, deren Name mit dem Medikamentennamen als ganzem Wort beginnt (sonst mit seinem ersten
    Wort); ("", []) ohne Treffer oder ohne Daten. Ein Brief nennt meist keine Packung – darum alle Einträge."""
    try:
        wb = wissen.wissensbasis()
    except FileNotFoundError:
        return "", []
    woerter = name.split()
    for n in range(len(woerter), 0, -1):
        begriff = " ".join(woerter[:n])
        if len(begriff) < 3:
            break
        muster = re.compile(rf"{re.escape(begriff.casefold())}(?![a-zäöüß])")
        if treffer := [e for e in wb.ekodex(begriff, k=_EKO_MAX) if muster.match(e.name.casefold())]:
            return begriff, treffer
    return "", []


def _eko_varianten(eintraege: list) -> dict[tuple[str, tuple[str, ...]], list]:
    """Einträge nach (Box, Kennzeichen) gruppiert, häufigste Variante zuerst."""
    gruppen: dict[tuple[str, tuple[str, ...]], list] = {}
    for e in eintraege:
        gruppen.setdefault((e.box, tuple(e.kennzeichen)), []).append(e)
    return dict(sorted(gruppen.items(), key=lambda kv: -len(kv[1])))


def _varianten_text(varianten: dict, sp: str, beispiel: bool = True) -> str:
    teile = []
    for (box, kz), liste in list(varianten.items())[:_EKO_VARIANTEN_TEXT]:
        kennz = t("eko_mit_kennzeichen", sp, kennzeichen=", ".join(kz)) if kz else ""
        anzahl = t("eko_anzahl", sp, n=len(liste)) if len(liste) != 1 else t("eko_anzahl_eins", sp)
        if beispiel:
            teile.append(t("eko_variante", sp, box=texte.BOX_LABEL[box][sp], kennzeichen=kennz, anzahl=anzahl,
                           beispiel=f"{liste[0].name}, PZN {liste[0].pzn}"))
        else:
            teile.append(f"{texte.BOX_LABEL[box][sp]}{kennz} ({anzahl})")
    if len(varianten) > _EKO_VARIANTEN_TEXT:
        teile.append("…")
    return "; ".join(teile)


def _eko_zusammenfassung(suchname: str, eintraege: list, sp: str, ausfuehrlich: bool = False) -> dict:
    """Erstattungsstatus über alle Einträge zu einem Namen: einheitlich (eine Box, gleiche Kennzeichen) oder Varianten.
    Erklärung: Satz plus Legende der Box(en) laut Zeichenerklärung, ausführlich mit Kennzeichen und Rechtsgrundlage."""
    varianten = _eko_varianten(eintraege)
    einheitlich = len(varianten) == 1
    beispiel = next(iter(varianten.values()))[0]
    if einheitlich:
        satz = t("eko_einheitlich" if len(eintraege) > 1 else "eko_einheitlich_eins", sp, n=len(eintraege),
                 name=suchname, box=texte.BOX_LABEL[beispiel.box][sp], beispiel=f"{beispiel.name}, PZN {beispiel.pzn}")
    else:
        satz = t("eko_varianten", sp, n=len(eintraege), name=suchname, varianten=_varianten_text(varianten, sp))
    zeilen = [satz]
    quellen: list[dict] = []
    for liste in varianten.values():
        erklaerung = liste[0].erklaerung(sp).split("\n")
        zeilen += [z for z in (erklaerung if ausfuehrlich else erklaerung[:1]) if z not in zeilen]
        quellen += [d for q in liste[0].quellen() if (d := q.to_dict()) not in quellen]
    boxen = {e.box for e in eintraege}
    return {
        "suchname": suchname,
        "anzahl": len(eintraege),
        "einheitlich": einheitlich,
        "box": beispiel.box if len(boxen) == 1 else "",
        "kennzeichen": list(beispiel.kennzeichen) if einheitlich else [],
        "varianten": [{"box": box, "kennzeichen": list(kz), "anzahl": len(liste),
                       "beispiel": {"name": liste[0].name, "pzn": liste[0].pzn}}
                      for (box, kz), liste in varianten.items()],
        "pzn": beispiel.pzn,
        "name": beispiel.name,
        "erklaerung": "\n".join(zeilen),
        "quellen": quellen,
    }


def _ohne_bedeutung(slot_id: str, werte: dict[str, str]) -> bool:
    """Angaben, die nach bisherigen Antworten nichts mehr ändern (Stufe nur bei bestehendem Pflegegeld)."""
    return slot_id == "pflege.stufe" and werte.get("pflege.antragsart") == "zuerkennung"


def _grund(slot_id: str) -> str:
    if slot_id == "person.bundesland":
        return "grund_region"
    if slot_id.startswith("versicherung."):
        return "grund_stelle"
    if slot_id == "pflege.antragsart":
        return "grund_antrag"
    if slot_id.startswith("termin."):
        return "grund_termin"
    return "grund_sonst"


def _katalog_hat(leistung_id: str) -> bool:
    try:
        katalog.leistung(leistung_id)
    except KeyError:
        return False
    return True


def _pruefe_einstellung(sprache: str, stil: str) -> None:
    if sprache in WEITERE_SPRACHEN:
        if not llm.aktiv():
            raise ValueError(f"Sprache {sprache} gibt es nur im KI-Modus")
    elif sprache not in SPRACHEN:
        raise ValueError(f"Unbekannte Sprache: {sprache}")
    if stil not in STILE:
        raise ValueError(f"Unbekannter Stil: {stil}")
