"""Lotse-Engine: Grenzprüfung, Situationserkennung, Rückfragen, Leistungsbündel, Dokumente, Fallakte.

Ablauf je Nachricht: Grenze → Status-Befehl → Rückfrage-Antwort → Sonderfragen (Pflegegeldbetrag,
Erstattungskodex) → Szenario → Wissensfrage. Alle Texte entstehen zweisprachig, damit Sprache und
Darstellung nachträglich umgeschaltet werden können.
"""

from __future__ import annotations

import re
import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date
from functools import partial

from lotse import dokument, formulare, grenzen, katalog, llm, texte, wissen
from lotse.fallakte import Fallakte
from lotse.models import FORMULARE, Empfehlung, Grenzentscheidung, Quelle
from lotse.slots import SLOTS
from lotse.texte import SPRACHEN, STILE, beide, t

MAX_RUECKFRAGEN = 5  # je erkanntem Anliegen


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

    art: str = "fall"  # start | fall | wissen | grenze | status | fehler
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


@dataclass
class Sitzung:
    id: str
    sprache: str = "de"
    stil: str = "einfach"
    werte: dict[str, str] = field(default_factory=dict)
    herkunft: dict[str, dict] = field(default_factory=dict)  # slot → {"art": dialog|dokument, "dokument", "seite"}
    szenarien: list[str] = field(default_factory=list)  # neueste zuerst
    leistungen: list[str] = field(default_factory=list)  # aktuelles Bündel
    dok_empfehlungen: dict[str, list[Empfehlung]] = field(default_factory=dict)
    offene_frage: str | None = None
    fragen_gestellt: int = 0
    uebersprungen: set[str] = field(default_factory=set)
    dokumente: list[dict] = field(default_factory=list)  # {"name", "seiten"}
    fallakte: Fallakte = field(default_factory=Fallakte)
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

_UEBERSPRINGEN = re.compile(
    r"weiss (ich )?nicht|keine ahnung|unbekannt|ueberspring|spaeter|\bskip\b|don'?t know|do not know|"
    r"not sure|unsure|no idea|\blater\b"
)

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

    # -- Nachricht ----------------------------------------------------------

    def nachricht(self, s: Sitzung, text: str) -> Antwort:
        text = " ".join((text or "").split())[:2000]
        if not text:
            inhalt = Inhalt(art="fehler")
            inhalt.neu("leer")
            return self._antwort(s, inhalt)
        s.verlauf.append({"rolle": "nutzer", "text": text})

        entscheidung = grenzen.pruefe_anfrage(text)
        durch_ki = False
        if entscheidung.erlaubt and llm.aktiv():
            # Zweite Stufe für Formulierungen, die die Regeln nicht kennen (Dialekt, andere Sprachen)
            entscheidung = grenzen.ablehnung(llm.grenzkategorie(text))
            durch_ki = not entscheidung.erlaubt
        if not entscheidung.erlaubt:
            inhalt = self._grenze(entscheidung)
            inhalt.ki_verstanden = durch_ki
            return self._antwort(s, inhalt)

        if schritt_id := self._statusbefehl(s, text):
            return self.setze_status(s, schritt_id, "erledigt")

        f = _falte(text)
        szenarien = list(katalog.erkenne_szenarien(text))
        spezial = self._spezialfrage(f, text)
        inhalt = Inhalt(art="fall")
        geantwortet = False

        extrahiert = extrahiere(text, szenarien or s.szenarien)
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
            if wert is not None:
                self._setze_wert(s, slot_id, wert, inhalt)
                s.offene_frage = None
                geantwortet = True
            elif not (geantwortet or szenarien or neu_genannt or "?" in text or len(text.split()) >= 5):
                return self._frage_erneut(s, slot_id)

        neu_erkannt = self._uebernimm(s, extrahiert, inhalt)

        if spezial:
            return self._antwort(s, self._mit_quelldaten(spezial))

        if not szenarien and not geantwortet and not neu_erkannt and llm.aktiv():
            ki = llm.verstehe(text, s.sprache)
            szenarien = ki["szenarien"]
            neu_erkannt = self._uebernimm(s, ki["slots"], inhalt)
            inhalt.ki_verstanden = bool(szenarien or neu_erkannt)

        if szenarien:
            self._neue_szenarien(s, szenarien)
            return self._antwort(s, self._fall(s, inhalt, neue_szenarien=szenarien))
        if geantwortet or (neu_erkannt and s.szenarien):
            return self._antwort(s, self._fall(s, inhalt))
        if neu_erkannt:
            inhalt.neu("wissen_tipp", beispiel={sp: texte.BEISPIELE["pflege"][sp] for sp in SPRACHEN})
            return self._antwort(s, inhalt)
        return self._antwort(s, self._mit_quelldaten(lambda: self._wissen(text)))

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
        except ValueError:
            dok = None
        if dok is None or not any(seite.strip() for seite in dok.seiten):
            fehler = Inhalt(art="fehler")
            fehler.neu("dokument_fehler")
            return self._antwort(s, fehler)
        empfehlungen = dokument.empfehlungen(dok)
        stammdaten = dokument.stammdaten(dok)
        s.dokumente.append({"name": dok.name, "seiten": len(dok.seiten)})
        s.verlauf.append({"rolle": "nutzer", "text": f"[{dok.name}]"})

        inhalt = Inhalt(art="fall")
        n = len(dok.seiten)
        inhalt.neu("dokument_gelesen", name=dok.name, seiten={
            "de": f"{n} Seite" if n == 1 else f"{n} Seiten", "en": f"{n} page" if n == 1 else f"{n} pages",
        })
        zeilen = []
        for e in empfehlungen:
            if not _katalog_hat(e.thema):
                continue
            liste = s.dok_empfehlungen.setdefault(e.thema, [])
            if all(x.zitat != e.zitat for x in liste):
                liste.append(e)
            zeilen.append(beide("dokument_steht", zitat=e.zitat, seite=e.seite))
            if e.quelle not in inhalt.quellen:
                inhalt.quellen.append(e.quelle)
        if zeilen:
            inhalt.zeilen(zeilen)
        else:
            inhalt.neu("dokument_keine_empfehlung")

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
            # Wien ist Gemeinde und Bundesland zugleich
            if sd.slot == "person.ort" and _falte(sd.wert) == "wien" and "person.bundesland" not in s.werte:
                s.werte["person.bundesland"] = "Wien"
                s.herkunft["person.bundesland"] = {"art": "dokument", "dokument": dok.name, "seite": sd.seite}
                uebernommen.append("person.bundesland")
        if uebernommen:
            inhalt.neu("dokument_stammdaten", labels={
                sp: ", ".join(texte.slot_label(x, sp) for x in uebernommen) for sp in SPRACHEN
            })
        if s.offene_frage in s.werte:
            s.offene_frage = None

        neue = ["entlassung"] if s.dok_empfehlungen else []
        if neue:
            self._neue_szenarien(s, neue)
        return self._antwort(s, self._fall(s, inhalt, neue_szenarien=neue))

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

    def _neue_szenarien(self, s: Sitzung, szenarien: list[str]) -> None:
        neu = [sz for sz in szenarien if sz not in s.szenarien]
        s.szenarien = list(dict.fromkeys(list(szenarien) + s.szenarien))
        if neu:
            s.fragen_gestellt = 0
            s.offene_frage = None  # Rückfrage für das neue Anliegen neu bestimmen

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

    def _uebernimm(self, s: Sitzung, werte: dict[str, str], inhalt: Inhalt) -> bool:
        neu = False
        for slot_id, wert in werte.items():
            if s.werte.get(slot_id) != wert:
                self._setze_wert(s, slot_id, wert, inhalt)
                if s.offene_frage == slot_id:
                    s.offene_frage = None
                neu = True
        return neu

    def _fall(self, s: Sitzung, inhalt: Inhalt, neue_szenarien: list[str] | None = None) -> Inhalt:
        vorher = list(s.leistungen)
        self._aktualisiere_buendel(s)
        if neue_szenarien:
            labels = {sp: ", ".join(texte.SZENARIO_LABEL[x][sp] for x in neue_szenarien) for sp in SPRACHEN}
            inhalt.absaetze.insert(0, Absatz(beide("verstanden", szenarien=labels)))
        if neue_szenarien or set(s.leistungen) != set(vorher):
            n = len(s.leistungen)
            inhalt.neu("gefunden" if n > 1 else "gefunden_eine" if n == 1 else "gefunden_keine", n=n)
            zeilen = []
            for lid in s.leistungen:
                l = katalog.leistung(lid)
                zeilen.append(beide("leistung_zeile", titel=l.titel, kurz=l.kurz))
            inhalt.zeilen(zeilen, nur_ausfuehrlich=True)
            inhalt.neu("anspruch_hinweis", nur_ausfuehrlich=True)
        self._naechster(s, inhalt)
        if "entlassung" in s.szenarien and not s.dokumente:
            inhalt.neu("dokument_tipp")
        if s.offene_frage is None:
            s.offene_frage = self._naechste_frage(s)
            if s.offene_frage:
                s.fragen_gestellt += 1
            elif any(katalog.leistung(lid).formular for lid in s.leistungen):
                inhalt.neu("keine_fragen")
                inhalt.neu("formular_hinweis", nur_ausfuehrlich=True)
        return inhalt

    def _naechster(self, s: Sitzung, inhalt: Inhalt, leistung_id: str | None = None) -> None:
        schritt = s.fallakte.naechster_schritt(leistung_id) or s.fallakte.naechster_schritt()
        if schritt is not None:
            titel = s.fallakte.eintraege[schritt.leistung_id].titel
            inhalt.neu("naechster", titel=titel, schritt={sp: schritt.text[sp].rstrip(".") for sp in SPRACHEN})
        elif s.fallakte.eintraege:
            inhalt.neu("alles_erledigt")

    def _aktualisiere_buendel(self, s: Sitzung) -> None:
        land = s.werte.get("person.bundesland")
        # Leistungen aus dem Dokument zuerst, in der Relevanzreihenfolge des Katalogs für „entlassung“
        rang = {l.id: i for i, l in enumerate(katalog.fuer_szenario("entlassung", land))}
        ids = sorted((lid for lid in s.dok_empfehlungen if _katalog_hat(lid)), key=lambda x: rang.get(x, len(rang)))
        for sz in s.szenarien:
            ids += [l.id for l in katalog.fuer_szenario(sz, land)]
        ids += [lid for lid, e in s.fallakte.eintraege.items() if e.hat_fortschritt()]
        s.leistungen = list(dict.fromkeys(ids))
        s.fallakte.behalte(s.leistungen)
        for lid in s.leistungen:
            l = katalog.leistung(lid)
            unterlagen: list[tuple[dict[str, str], Quelle | None]] = [(dict(u), None) for u in l.unterlagen]
            if l.formular:
                unterlagen += [(dict(u.text), u.quelle) for u in formulare.formular(l.formular).unterlagen_fuer(lid)]
            s.fallakte.ergaenze(lid, l.titel, l.schritte, unterlagen)
            self._zustaendigkeit_vermerken(s, l)
        s.fallakte.ordne(s.leistungen)

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
        """Gibt es für die Anliegen regionale Angebote (dann zuerst nach dem Bundesland fragen)?"""
        leistungen = [katalog.leistung(lid) for lid in s.dok_empfehlungen if _katalog_hat(lid)]
        for sz in s.szenarien:
            leistungen += katalog.fuer_szenario(sz, None)
        return any(l.regionen for l in leistungen)

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
            for q in belege:
                if q not in inhalt.quellen:
                    inhalt.quellen.append(q)
            nummern = ", ".join(f"[{inhalt.quellen.index(q) + 1}]" for q in belege)
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
                if q not in inhalt.quellen:
                    inhalt.quellen.append(q)
            n = inhalt.quellen.index(e.quelle) + 1
            inhalt.absaetze.append(Absatz({
                sp: t("ekodex_zeile", sp, name=e.name, pzn=e.pzn, erklaerung=e.erklaerung(sp), n=n) for sp in SPRACHEN
            }))
        return inhalt

    def _wissen(self, text: str) -> Inhalt:
        treffer = [tr for tr in wissen.wissensbasis().suche(text, k=5) if tr.score > 0][:3]
        inhalt = Inhalt(art="wissen", frage=text)
        if not treffer:
            inhalt.neu("wissen_nichts")
            inhalt.neu("wissen_tipp", beispiel={sp: texte.BEISPIELE["pflege"][sp] for sp in SPRACHEN})
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
        sp, stil = s.sprache, s.stil
        ki_text = inhalt.ki_texte.get((sp, stil))
        if ki_text is None and inhalt.fakten and llm.aktiv():
            ki_text = inhalt.ki_texte[(sp, stil)] = llm.formuliere(inhalt.fakten, sp, stil, frage=inhalt.frage)
        text = ki_text or "\n\n".join(
            a.text[sp] for a in inhalt.absaetze if a.text.get(sp) and (stil == "ausfuehrlich" or not a.nur_ausfuehrlich)
        )
        rueckfrage = None
        if s.offene_frage:
            slot = SLOTS[s.offene_frage]
            grund = t(_grund(s.offene_frage) if inhalt.art == "fall" else "zurueck_zur_frage", sp)
            rueckfrage = {
                "slot": slot.id,
                "frage": slot.frage[sp],
                "grund": grund,
                "typ": slot.typ,
                "optionen": [{"wert": o, "label": texte.knopf_label(slot.id, o, sp)} for o in slot.optionen],
            }
            text = f"{text}\n\n{grund} {slot.frage[sp]}".strip()
        if protokoll:
            s.verlauf.append({"rolle": "lotse", "text": text})
        return Antwort(
            sitzung_id=s.id,
            text=text,
            rueckfrage=rueckfrage,
            buendel=[] if inhalt.grenze else [self._buendel_eintrag(s, lid) for lid in s.leistungen],
            quellen=[q.to_dict() for q in inhalt.quellen],
            grenze=inhalt.grenze.to_dict() if inhalt.grenze else None,
            fallakte=s.fallakte.to_dict(sp),
            modus="ki" if (ki_text or inhalt.ki_verstanden) else "regelbasiert",
            sprache=sp,
            stil=stil,
            szenarien=[{"id": x, "label": texte.SZENARIO_LABEL[x][sp]} for x in s.szenarien],
            angaben=self._angaben(s),
            dokumente=list(s.dokumente),
        )

    def _buendel_eintrag(self, s: Sitzung, lid: str) -> dict:
        sp, ausf = s.sprache, s.stil == "ausfuehrlich"
        l = katalog.leistung(lid)
        formular = None
        fehlend: list[dict] = []
        if l.formular:
            f = formulare.formular(l.formular)
            adresse = f.adressen.get(s.werte.get("person.bundesland", ""))
            formular = {
                "id": f.id,
                "titel": f.titel[sp],
                "vorauswahl": f.vorauswahl.get(lid, {}).get(sp, ""),
                "url": f"/api/sitzung/{s.id}/formular/{f.id}?leistung={lid}",
                "stelle": f.stelle[sp],
                "adresse": adresse["text"] if adresse else "",
                "hinweis": f.hinweise[sp],
                "ohne_unterlagen": f.ohne_unterlagen.get(sp, ""),
            }
            fehlend = [{"slot": x, "label": texte.slot_label(x, sp)}
                       for x in formulare.fehlende_pflichtangaben(f.id, dict(s.werte), leistung=lid)]
            form_quellen = [f.quelle, f.stelle_quelle, *f.hinweis_quellen, *([adresse["quelle"]] if adresse else [])]
        else:
            form_quellen = []
        eintrag = s.fallakte.eintraege.get(lid)
        dok = [
            {"text": t("dokument_steht", sp, zitat=e.zitat, seite=e.seite), "zitat": e.zitat, "seite": e.seite,
             "quelle": e.quelle.to_dict()}
            for e in s.dok_empfehlungen.get(lid, [])
        ]
        quellen = []
        for q in [*l.quellen, *form_quellen, *(e.quelle for e in s.dok_empfehlungen.get(lid, []))]:
            if (d := q.to_dict()) not in quellen:
                quellen.append(d)
        return {
            "leistung_id": lid,
            "titel": l.titel[sp],
            "kurz": l.kurz[sp],
            "details": l.details[sp] if ausf else "",
            "voraussetzungen": [v[sp] for v in l.voraussetzungen] if ausf else [],
            "stelle": _stelle(l, s.werte, sp),
            "formular": formular,
            "fehlende_angaben": fehlend,
            "unterlagen": [u.to_dict(sp) for u in eintrag.unterlagen] if eintrag else [],
            "dokument": dok,
            "quellen": quellen,
            "beleg": l.beleg,
            "regionen": list(l.regionen),
            "regionen_anzeige": [texte.wert_anzeige("person.bundesland", r, sp) for r in l.regionen],
            "naechster_schritt": (ns.id if (ns := s.fallakte.naechster_schritt(lid)) else None),
        }

    def _angaben(self, s: Sitzung) -> list[dict]:
        sp = s.sprache
        angaben = []
        for slot_id, wert in s.werte.items():
            slot = SLOTS[slot_id]
            h = s.herkunft.get(slot_id, {})
            if h.get("art") == "dokument":
                herkunft = f"{texte.UI['aus_dokument'][sp]} {h['dokument']}, {texte.UI['seite'][sp]} {h['seite']}"
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
    """Zuständige Stelle; `stelle_nach` löst sie über bekannte Angaben auf."""
    hinweis = l.stelle.get("hinweis") or {}
    offen = [sid for sid, zuordnung in l.stelle_nach.items() if werte.get(sid) not in zuordnung]
    aufgeloest = not l.stelle_nach or len(offen) < len(l.stelle_nach)
    return {
        "name": l.stelle_fuer(werte)[sprache],
        "kontakt": l.stelle.get("kontakt", ""),
        "hinweis": hinweis.get(sprache, ""),
        "aufgeloest": aufgeloest,
        "abhaengig_von": None if aufgeloest else {"slot": offen[0], "label": texte.slot_label(offen[0], sprache)},
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
    return "grund_sonst"


def _katalog_hat(leistung_id: str) -> bool:
    try:
        katalog.leistung(leistung_id)
    except KeyError:
        return False
    return True


def _pruefe_einstellung(sprache: str, stil: str) -> None:
    if sprache not in SPRACHEN:
        raise ValueError(f"Unbekannte Sprache: {sprache}")
    if stil not in STILE:
        raise ValueError(f"Unbekannter Stil: {stil}")
