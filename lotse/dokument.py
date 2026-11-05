"""Dokumentfunktion: hochgeladene Befunde/Briefe lesen und nur ausdrücklich dokumentierte Aufgaben übernehmen.

Grenze: keine Interpretation. Übernommen werden nur Sätze bzw. Aufgabenzeilen mit Empfehlungs- oder
Aufgabensignal und Themenwort; Zitate mit medizinischem Inhalt werden auf den administrativen Teilsatz
gekürzt oder verworfen. Stammdaten kommen nur aus beschrifteten Feldern (Name, Geburtsdatum, Adresse …).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO

from pypdf import PdfReader

from lotse.models import THEMEN, Empfehlung, Quelle, Stammdatum


@dataclass
class Dokument:
    name: str
    seiten: list[str]  # je Seite whitespace-normalisierter Text
    zeilen: list[list[str]] = field(default_factory=list)  # je Seite die normalisierten Zeilen (optional)

    def seitenzeilen(self, index: int) -> list[str]:
        if index < len(self.zeilen) and self.zeilen[index]:
            return self.zeilen[index]
        return [self.seiten[index]] if self.seiten[index] else []


def _norm(text: str) -> str:
    return " ".join(text.split())


def _aus_texten(name: str, texte: list[str]) -> Dokument:
    zeilen = [[_norm(z) for z in t.splitlines() if z.strip()] for t in texte]
    seiten = [" ".join(z) for z in zeilen]
    if not any(seiten):
        raise ValueError(f"{name}: kein auslesbarer Text (gescanntes Dokument?)")
    return Dokument(name=name, seiten=seiten, zeilen=zeilen)


def lade_dokument(name: str, inhalt: bytes) -> Dokument:
    """PDF (Text je Seite) oder Textdatei (UTF-8 bzw. cp1252; Seitenumbruch per Form Feed)."""
    if inhalt[:5] == b"%PDF-" or name.lower().endswith(".pdf"):
        try:
            reader = PdfReader(BytesIO(inhalt))
            gesperrt = reader.is_encrypted and not reader.decrypt("")
            texte = [] if gesperrt else [seite.extract_text() or "" for seite in reader.pages]
        except Exception as fehler:  # pypdf meldet defekte Dateien mit unterschiedlichen Fehlertypen
            raise ValueError(f"{name}: PDF nicht lesbar ({fehler})") from fehler
        if gesperrt:
            raise ValueError(f"{name}: PDF ist passwortgeschützt")
        return _aus_texten(name, texte)
    try:
        text = inhalt.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = inhalt.decode("cp1252", errors="replace")
    return _aus_texten(name, text.split("\f"))


# ---------------------------------------------------------------- Muster

_THEMA = {
    "rehabilitation": r"\b(?:Rehabilitation\w*|rehabilitativ\w*|Reha\b|Reha-\w+|Rehaantrag\w*|Anschlussheilverfahren)",
    "pflegegeld": r"Pflegegeld\w*",
    "hauskrankenpflege": r"Hauskrankenpflege\w*",
    "fahrtkosten": r"\b(?:Fahrtkosten\w*|Fahrt(?:en|möglichkeit\w*|zuschuss\w*)?\b|Fahrtendienst\w*|Krankentransport\w*|Transport\w*)",
    "rezeptgebuehrenbefreiung": r"Rezeptgeb(?:ühr|uehr)\w*",
    "pflege_zu_hause": (
        r"(?:Pflege und Betreuung zu Hause|(?:Betreuung|Unterstützung|Versorgung|Pflege) zu Hause"
        r"|\bmobile[nrs]? (?:Pflege|Betreuung|Dienste?)\b|\bsoziale[nr]? Dienste?\b|Heimhilfe\w*|Alltagshilfe\w*"
        r"|24-Stunden-Betreuung|Essen auf Rädern|\bhäusliche[nr]? (?:Pflege|Betreuung)\b)"
    ),
}
_THEMA_RE = {t: re.compile(m, re.IGNORECASE) for t, m in _THEMA.items()}
assert set(_THEMA) == set(THEMEN)

# Aufgabenverben (Infinitiv am Ende einer Aufgabenzeile wie „Pflegegeldanspruch prüfen“)
_AUFGABE = (
    "vorbereiten|prüfen|überprüfen|organisieren|klären|abklären|beantragen|einleiten|veranlassen|einholen"
    "|vereinbaren|koordinieren|abstimmen|einreichen|anfordern|anmelden|kontaktieren|stellen|erledigen|beauftragen"
)
_AUFGABE_WORT = re.compile(rf"(?:{_AUFGABE})", re.IGNORECASE)
# Verbale Signale (genügen auch für gekürzte Teilsätze)
_SIGNAL_VERB = re.compile(
    r"\b(?:empfohlen|empfehlen|empfiehlt|anzuraten|angeraten|raten wir|vorzubereiten|vorbereitet|geprüft|zu prüfen"
    r"|organisiert|zu organisieren|geklärt|zu klären|abzuklären|beantragt|zu beantragen|einzuleiten|eingeleitet"
    rf"|veranlasst|zu veranlassen|einzuholen|eingeholt|{_AUFGABE})\b",
    re.IGNORECASE,
)
# Nominale Signale (nur für vollständige Sätze)
_SIGNAL_NOMEN = re.compile(
    r"\b(?:Empfehlung\w*|Antrag\w*|Antragstellung|Prüfung|Klärung|Organisation|Kontaktaufnahme|Veranlassung)\b"
)
_VERNEINUNG = re.compile(
    r"\b(?:nicht (?:empfohlen|erforderlich|notwendig|nötig|indiziert|sinnvoll|beantragen|vorbereiten|organisieren)"
    r"|kein(?:e|en)? (?:Bedarf|Indikation|Antrag)|bereits (?:beantragt|gestellt|organisiert|erfolgt|bewilligt|eingeleitet|vorhanden)"
    r"|wurden? (?:bereits|schon))\b",
    re.IGNORECASE,
)
# Medizinische Inhalte, die nie in ein Zitat oder Stammdatum gelangen
_MEDIZIN = re.compile(
    r"(?:diagnos|karzinom|tumor|krebs|onkolog|metasta|chemo|strahl|radiolog|medikament|medikation|arznei|wirkstoff"
    r"|dosis|dosier|\d\s*mg\b|tablette|infusion|hypertonie|blutdruck|insuffizienz|infarkt|fraktur|schlaganfall"
    r"|apoplex|diabet|demenz|depress|fatigue|übelkeit|erbrechen|durchfall|risiko|labor|blutbild|befund|erkrankung"
    r"|krankheit|symptom|schmerz|entzündung|infekt|operation|operativ|therapie|lymph|läsion|prognose|nebenwirkung)",
    re.IGNORECASE,
)
# Kein Satzende nach Abkürzungen und Ordnungszahlen („z. B.“, „7. Empfehlung“); nach Jahreszahlen schon
_ABKUERZUNG = re.compile(
    r"(?:\b(?:z|B|bzw|ggf|evtl|Dr|Nr|ca|usw|inkl|vgl|u|d|Mag|Prof|Abs|Z|lit|Str|St|Tel|geb)|(?<![\d.])\d{1,2})$"
)
# Zeilenende, nach dem eine Aufgabe sicher weitergeht (Präposition, Artikel, Konjunktion)
_OFFENES_ENDE = re.compile(
    r"\b(?:zu|zur|zum|für|der|die|das|des|den|dem|und|oder|mit|bei|von|nach|auf|in|im|an|am|ein|eine|einer|eines|einen)$",
    re.IGNORECASE,
)
_SATZ_MAX = 220
_TEIL_MAX = 160


def _themen(text: str) -> list[str]:
    return [t for t, r in _THEMA_RE.items() if r.search(text)]


def _medizinisch(text: str) -> bool:
    return _MEDIZIN.search(text) is not None


def _ist_kopfzeile(zeile: str, naechste: str | None) -> bool:
    """Kurze Zeile ohne Satzzeichen vor einer neuen Zeile mit Großbuchstabe/Aufzählung = Überschrift."""
    if re.search(r"[.!?:;,]$", zeile) or len(zeile.split()) > 6:
        return False
    return naechste is None or re.match(r"[A-ZÄÖÜ0-9•▪◦\-–(„]", naechste) is not None


def _saetze(block: str) -> list[tuple[str, str]]:
    """Zerlegt einen Absatz in Sätze bzw. Aufzählungspunkte → (Text, "satz" | "punkt")."""
    teile: list[tuple[str, str]] = []
    for nr, stueck in enumerate(re.split(r"\s*[•▪◦]\s*", block)):
        start = 0
        for m in re.finditer(r"[.!?](?=\s+[A-ZÄÖÜ„\"(])", stueck):
            if _ABKUERZUNG.search(stueck[start:m.start()]):
                continue
            teile.append((stueck[start:m.end()].strip(), "punkt" if nr > 0 and start == 0 else "satz"))
            start = m.end()
        rest = stueck[start:].strip()
        if rest:
            teile.append((rest, "punkt" if nr > 0 and start == 0 else "satz"))
    return [(t, a) for t, a in teile if t]


def _segmente(zeilen: list[str]) -> list[tuple[str, str]]:
    """Überschriften ("kopf"), Sätze ("satz") und Aufzählungspunkte ("punkt") einer Seite."""
    segmente: list[tuple[str, str]] = []
    block: list[str] = []
    for i, zeile in enumerate(zeilen):
        if _ist_kopfzeile(zeile, zeilen[i + 1] if i + 1 < len(zeilen) else None):
            if block:
                segmente += _saetze(" ".join(block))
                block = []
            segmente.append((zeile, "kopf"))
        else:
            block.append(zeile)
    if block:
        segmente += _saetze(" ".join(block))
    return segmente


def _aufgabenzeilen(zeilen: list[str]) -> list[str]:
    """Kurze Aufgabenzeilen „<Thema …> <Aufgabenverb>“ ab Zeilenanfang (auch über einen Zeilenumbruch)."""
    treffer = []
    for i, zeile in enumerate(zeilen):
        woerter = re.sub(r"^[•▪◦\-–*]\s*", "", zeile).split()
        kandidaten = [woerter]
        # Fortsetzung nur, wenn die Zeile offensichtlich weitergeht („Fahrtmöglichkeiten zu“ / „… Kontrolle“ + „vereinbaren“)
        if i + 1 < len(zeilen) and len(woerter) <= 5 and not re.search(r"[.!?:;]$", zeile) and (
            _OFFENES_ENDE.search(zeile) or re.match(r"[a-zäöüß]", zeilen[i + 1])
        ):
            kandidaten.append(woerter + zeilen[i + 1].split())
        for w in kandidaten:
            ende = next((j for j, wort in enumerate(w[:8]) if _AUFGABE_WORT.fullmatch(wort.strip(".,;:"))), None)
            if ende is None or ende == 0:
                continue
            phrase = " ".join(w[: ende + 1]).rstrip(".,;:")
            if re.search(r"[,:;]|\.\s", phrase) or not re.match(r"[A-ZÄÖÜ]", phrase) or _VERNEINUNG.search(phrase):
                continue
            treffer.append(phrase)
            break
    return treffer


def _kandidaten(zeilen: list[str]) -> list[tuple[str, str]]:
    """(thema, zitat) – alle sauberen Belegstellen einer Seite."""
    gefunden: list[tuple[str, str]] = []
    for phrase in _aufgabenzeilen(zeilen):
        if not _medizinisch(phrase):
            gefunden += [(t, phrase) for t in _themen(phrase)]
    kontext = False  # „Empfohlen werden:“ gilt für die folgenden Aufzählungspunkte
    for text, art in _segmente(zeilen):
        if art != "punkt":
            kontext = text.endswith(":") and bool(_SIGNAL_VERB.search(text) or _SIGNAL_NOMEN.search(text))
        # Überschriften und Tabellenreste (ohne Satzende) sind keine Empfehlungen
        if art == "kopf" or (art == "satz" and not re.search(r"[.!?]$", text)):
            continue
        themen = _themen(text)
        if not themen or _VERNEINUNG.search(text):
            continue
        if not (kontext or _SIGNAL_VERB.search(text) or _SIGNAL_NOMEN.search(text)):
            continue
        if not _medizinisch(text) and len(text) <= _SATZ_MAX:
            gefunden += [(t, text) for t in themen]
            continue
        # medizinischer oder zu langer Satz → nur administrativer Teilsatz mit eigenem Verbsignal
        for teil in (t.strip() for t in re.split(r"[,;:]|\s[–-]\s", text)):
            if len(teil) > _TEIL_MAX or _medizinisch(teil) or not (kontext or _SIGNAL_VERB.search(teil)):
                continue
            gefunden += [(t, teil) for t in _themen(teil)]
    return gefunden


def empfehlungen(dok: Dokument) -> list[Empfehlung]:
    """Je Thema die kürzeste ausdrücklich dokumentierte Empfehlung/Aufgabe (wörtlich, mit Seite)."""
    beste: dict[str, tuple[int, int, str]] = {}
    for index in range(len(dok.seiten)):
        for thema, zitat in _kandidaten(dok.seitenzeilen(index)):
            if zitat not in dok.seiten[index]:  # Sicherheitsnetz: nur wörtliche Zitate
                continue
            kandidat = (len(zitat), index, zitat)
            if thema not in beste or kandidat < beste[thema]:
                beste[thema] = kandidat
    ergebnis = [
        Empfehlung(
            thema=thema,
            zitat=zitat,
            seite=index + 1,
            quelle=Quelle(art="dokument", titel=dok.name, fundstelle=f"S. {index + 1}", zitat=zitat),
        )
        for thema, (_, index, zitat) in beste.items()
    ]
    return sorted(ergebnis, key=lambda e: (e.seite, dok.seiten[e.seite - 1].find(e.zitat), list(THEMEN).index(e.thema)))


# ---------------------------------------------------------------- Stammdaten

_MONATE = {
    "jänner": 1, "januar": 1, "jan": 1, "feber": 2, "februar": 2, "feb": 2, "märz": 3, "mär": 3, "april": 4, "apr": 4,
    "mai": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "november": 11, "nov": 11, "dezember": 12, "dez": 12,
}
_DATUM = r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})|(\d{1,2})\.\s*([A-Za-zÄÖÜäöü]{3,9})\.?\s+(\d{4})"
_GEBURT = re.compile(rf"(?:Geburtsdatum|Geb\.-?Datum|geb\.|geboren am)\s*:?\s*(?:{_DATUM})", re.IGNORECASE)
_ENTLASSUNG = re.compile(rf"(?:Entlassungsdatum|Entlassungstag|Entlassung am|entlassen am)\s*:?\s*(?:{_DATUM})", re.IGNORECASE)
_SVNR = re.compile(
    r"(?:SVNR|SV-Nr\.?|Sozialversicherungsnummer|Versicherungsnummer|VSNR)\s*:?\s*(\d[\d ]{8,14}\d)(?!\d)", re.IGNORECASE
)
_NAME_LABEL = re.compile(r"^(?:Name|Patient(?:in)?|Patient\(in\)|Patient/in|Versicherte[r]?)\s*:?(?:\s+(.+))?$")
_VORNAME = re.compile(r"\bVorname\s*:\s*([A-ZÄÖÜ][\wäöüß-]+(?: [A-ZÄÖÜ][\wäöüß-]+)?)")
_NACHNAME = re.compile(r"\b(?:Nachname|Familienname|Zuname)\s*:\s*([A-ZÄÖÜ][\wäöüß-]+(?:[ -][A-ZÄÖÜ][\wäöüß-]+)?)")
_NAMENSWORT = re.compile(r"[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)*")
_TITEL = re.compile(r"\b(?:Dr|Mag|Prof|DI|Ing|MSc|BSc|MA|BA|MBA|PhD|Dipl\.-Ing)\.?(?:\s+|$)")
_ADRESS_LABEL = re.compile(r"^(?:Wohnadresse|Adresse|Anschrift|Wohnort|Wohnhaft)\s*:?\s*(.*)$", re.IGNORECASE)
_STRASSE = re.compile(
    r"^(?P<strasse>[A-ZÄÖÜ][\wäöüß.' -]*?[a-zäöüß])\.?\s+(?P<nr>\d+[a-zA-Z]?(?:\s*/\s*\w+)*)"
    r"(?:\s*,?\s*(?P<plz>\d{4})\s+(?P<ort>[A-ZÄÖÜ][\wäöüß. -]*?))?\s*(?:,.*)?$"
)
_PLZ_ORT = re.compile(r"^(?P<plz>\d{4})\s+(?P<ort>[A-ZÄÖÜ][\wäöüß. -]*?)\s*(?:,.*)?$")
_KH_LABEL = re.compile(r"\b(?:Krankenhaus|Krankenanstalt|Klinik|Klinikum|Spital)\s*:\s*(.{3,80})$")
_KH_KOPF = re.compile(r"^(?:[A-ZÄÖÜ][a-zäöü]*)?(?:klinikum|krankenhaus|spital|klinik|krankenanstalt)(?![-\w])", re.IGNORECASE)
_REHA_FORM = re.compile(
    r"\b(ambulant|stationär)\w*\s+(?:\w+\s+)?Rehabilitation\w*|\bRehabilitation\w*\s+(?:\w+\s+){0,2}(ambulant|stationär)",
    re.IGNORECASE,
)


def _datum_aus(m: re.Match, offset: int = 1) -> str | None:
    g = m.groups()[offset - 1 : offset + 5]
    try:
        if g[0]:
            tag, monat, jahr = int(g[0]), int(g[1]), int(g[2])
        else:
            monat = _MONATE.get(g[4].lower().rstrip("."))
            if monat is None:
                return None
            tag, jahr = int(g[3]), int(g[5])
        date(jahr, monat, tag)
    except (TypeError, ValueError):
        return None
    return f"{tag:02d}.{monat:02d}.{jahr:04d}"


def _name(wert: str) -> tuple[str, str] | None:
    wert = _TITEL.sub("", wert).strip()
    komma = re.fullmatch(r"([A-ZÄÖÜ][\wäöüß-]+),\s*([A-ZÄÖÜ][\wäöüß-]+(?: [A-ZÄÖÜ][\wäöüß-]+)?)", wert)
    if komma:
        return komma.group(2), komma.group(1)
    wert = re.split(r"\s*[(,;:]|\s+(?:geb\.?|geboren|SVNR|Geburtsdatum|Alter|wohnhaft)\b", wert)[0]
    woerter = wert.split()
    if not 2 <= len(woerter) <= 4 or not all(_NAMENSWORT.fullmatch(w) for w in woerter):
        return None
    return " ".join(woerter[:-1]), woerter[-1]


def stammdaten(dok: Dokument) -> list[Stammdatum]:
    """Administrative Angaben aus beschrifteten Feldern; nie Diagnosen, Medikation oder Werte."""
    funde: dict[str, Stammdatum] = {}

    def merke(slot: str, wert: str | None, seite: int, zitat: str) -> None:
        if wert and slot not in funde and not _medizinisch(zitat):
            funde[slot] = Stammdatum(slot=slot, wert=wert, seite=seite, zitat=zitat)

    entlassbrief = any(re.search(r"entlass", s, re.IGNORECASE) for s in dok.seiten)
    for index in range(len(dok.seiten)):
        seite = index + 1
        zeilen = dok.seitenzeilen(index)
        for i, zeile in enumerate(zeilen):
            if m := _GEBURT.search(zeile):
                merke("person.geburtsdatum", _datum_aus(m), seite, m.group(0))
            if m := _SVNR.search(zeile):
                ziffern = m.group(1).replace(" ", "")
                merke("person.svnr", ziffern if len(ziffern) == 10 else None, seite, m.group(0))
            if m := _NAME_LABEL.match(zeile):
                # Wert in derselben Zeile oder (bei „Patient:“ allein) in der nächsten
                wert_zeile = zeile if m.group(1) else (zeilen[i + 1] if i + 1 < len(zeilen) else "")
                if name := _name(m.group(1) or wert_zeile):
                    merke("person.vorname", name[0], seite, wert_zeile)
                    merke("person.nachname", name[1], seite, wert_zeile)
            if m := _VORNAME.search(zeile):
                merke("person.vorname", m.group(1), seite, m.group(0))
            if m := _NACHNAME.search(zeile):
                merke("person.nachname", m.group(1), seite, m.group(0))
            if m := _ADRESS_LABEL.match(zeile):
                kandidaten = [m.group(1)] if m.group(1) else []
                kandidaten += zeilen[i + 1 : i + 3]
                if kandidaten and (s := _STRASSE.match(kandidaten[0])):
                    merke("person.strasse", s.group("strasse"), seite, kandidaten[0])
                    merke("person.hausnummer", re.sub(r"\s+", "", s.group("nr")), seite, kandidaten[0])
                    plz_ort = s if s.group("plz") else (_PLZ_ORT.match(kandidaten[1]) if len(kandidaten) > 1 else None)
                    if plz_ort:
                        zitat = kandidaten[0] if s.group("plz") else kandidaten[1]
                        merke("person.plz", plz_ort.group("plz"), seite, zitat)
                        merke("person.ort", plz_ort.group("ort").strip(), seite, zitat)
            if entlassbrief:
                if m := _ENTLASSUNG.search(zeile):
                    merke("aufenthalt.entlassungsdatum", _datum_aus(m), seite, m.group(0))
                if m := _KH_LABEL.search(zeile):
                    merke("aufenthalt.krankenhaus", m.group(1).strip(), seite, zeile)
                elif index == 0 and i < 8 and _KH_KOPF.match(zeile) and len(zeile) <= 80:
                    merke("aufenthalt.krankenhaus", zeile, seite, zeile)
        # Reha-Form nur aus einer Empfehlung ohne medizinischen Inhalt, und nur wenn eindeutig
        for text, _ in _segmente(zeilen):
            m = _REHA_FORM.search(text)
            if not m or _VERNEINUNG.search(text) or _medizinisch(text):
                continue
            if not (_SIGNAL_VERB.search(text) or _SIGNAL_NOMEN.search(text)):
                continue
            form = (m.group(1) or m.group(2)).lower()
            wert = "ambulant" if form.startswith("ambulant") else "stationaer"
            vorher = funde.get("reha.form")
            if vorher and vorher.wert != wert:
                funde["reha.form"] = Stammdatum("reha.form", "", 0, "")  # widersprüchlich → verwerfen
            else:
                merke("reha.form", wert, seite, text)
    return [s for s in funde.values() if s.wert]
