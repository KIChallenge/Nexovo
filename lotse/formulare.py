"""Formular-Registry und Vorausfüllen der Original-PDFs (AcroForm) über pypdf.

Registry: `lotse/data/formulare/<ID>.json`. Jede Regel in `felder` beschreibt genau ein PDF-Feld:
- `{"feld", "slot"}`: Slot-Wert als Text (optional `"teil"`: hausnummer | stiege | tuer)
- `{"feld", "slot", "werte"}`: Auswahl → Exportwert (`/01`) oder Text
- `{"feld", "teile"}`: Text aus mehreren Slots, Teile mit ", " verbunden
- `{"feld", "wenn", "wert"}`: fester Wert, wenn alle Slots in `wenn` vorhanden sind
Unterschriftsfelder und gesperrte Seiten (ärztlicher Teil) werden nie beschrieben.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject

from lotse import config
from lotse.models import FORMULARE, Quelle
from lotse.slots import SLOTS

_REGISTRY = config.PAKET_DATEN / "formulare"
_PLATZHALTER = re.compile(r"\{([a-z_]+\.[a-z_]+)\}")


@dataclass(frozen=True)
class Unterlage:
    text: dict[str, str]
    quelle: Quelle
    leistungen: tuple[str, ...] = ()  # nur für diese Vorauswahl(en); leer = immer

    def to_dict(self) -> dict:
        return {"text": dict(self.text), "quelle": self.quelle.to_dict(), "leistungen": list(self.leistungen)}


@dataclass(frozen=True)
class Formular:
    id: str
    titel: dict[str, str]
    datei: str
    stelle: dict[str, str]
    slots: list[str]  # alle Slots, die das Formular füllen kann
    pflicht: list[str]
    unterlagen: list[Unterlage]
    hinweise: dict[str, str]
    quelle: Quelle  # das Formular selbst
    stelle_quelle: Quelle
    hinweis_quellen: list[Quelle] = field(default_factory=list)
    vorauswahl: dict[str, dict[str, str]] = field(default_factory=dict)  # Leistungs-ID → Bezeichnung {de,en}
    ohne_unterlagen: dict[str, str] = field(default_factory=dict)  # Begründung, falls keine Unterlagen
    adressen: dict[str, dict] = field(default_factory=dict)  # Bundesland → {"text", "quelle"}
    gesperrte_seiten: tuple[int, ...] = ()  # 1-basiert, z. B. ärztlicher Teil
    _regeln: tuple[dict, ...] = field(default=(), repr=False)
    _vorauswahl_regeln: dict[str, tuple[dict, ...]] = field(default_factory=dict, repr=False)
    _vorauswahl_pflicht: dict[str, tuple[str, ...]] = field(default_factory=dict, repr=False)

    def unterlagen_fuer(self, leistung: str | None = None) -> list[Unterlage]:
        return [u for u in self.unterlagen if not u.leistungen or leistung in u.leistungen]

    def pflicht_fuer(self, leistung: str | None = None) -> list[str]:
        extra = [s for s in self._vorauswahl_pflicht.get(leistung or "", ()) if s not in self.pflicht]
        return [*self.pflicht, *extra]

    def regeln(self, leistung: str | None = None) -> tuple[dict, ...]:
        return self._regeln + self._vorauswahl_regeln.get(leistung or "", ())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "titel": dict(self.titel),
            "datei": self.datei,
            "stelle": dict(self.stelle),
            "slots": list(self.slots),
            "pflicht": list(self.pflicht),
            "unterlagen": [u.to_dict() for u in self.unterlagen],
            "hinweise": dict(self.hinweise),
            "quelle": self.quelle.to_dict(),
            "stelle_quelle": self.stelle_quelle.to_dict(),
            "hinweis_quellen": [q.to_dict() for q in self.hinweis_quellen],
            "vorauswahl": {k: dict(v) for k, v in self.vorauswahl.items()},
            "ohne_unterlagen": dict(self.ohne_unterlagen),
            "adressen": {k: {"text": v["text"], "quelle": v["quelle"].to_dict()} for k, v in self.adressen.items()},
        }


@dataclass(frozen=True)
class AusfuellErgebnis:
    pdf: bytes
    befuellt: list[str]  # Slots, die mindestens ein Feld gefüllt haben
    fehlend_pflicht: list[str]  # Pflicht-Slots ohne gültigen Wert
    ungueltig: list[str] = field(default_factory=list)  # angegeben, aber Format ungültig → nicht eingetragen


# ---------------------------------------------------------------- Registry


def _regel_slots(regel: dict) -> list[str]:
    if "slot" in regel:
        return [regel["slot"]]
    if "teile" in regel:
        return [s for teil in regel["teile"] for s in _PLATZHALTER.findall(teil)]
    return list(regel.get("wenn", []))


def _pruefe_regeln(fid: str, regeln: list[dict]) -> None:
    for r in regeln:
        arten = [k for k in ("slot", "teile", "wenn") if k in r]
        if "feld" not in r or len(arten) != 1 or ("wenn" in r) != ("wert" in r):
            raise ValueError(f"{fid}: ungültige Regel {r}")
        unbekannt = [s for s in _regel_slots(r) if s not in SLOTS]
        if unbekannt:
            raise ValueError(f"{fid}: unbekannte Slots {unbekannt} in Regel {r}")
        if "werte" in r:
            optionen = SLOTS[r["slot"]].optionen
            falsch = [w for w in r["werte"] if w not in optionen]
            if falsch:
                raise ValueError(f"{fid}: Werte {falsch} nicht in Optionen von {r['slot']}")


def _formular_quelle(titel: str, datei: str, eintrag: dict) -> Quelle:
    return Quelle(art="formular", titel=titel, fundstelle=eintrag["fundstelle"], datei=datei, zitat=eintrag["zitat"])


def _lade(fid: str) -> Formular:
    pfad = _REGISTRY / f"{fid}.json"
    roh = json.loads(pfad.read_text(encoding="utf-8"))
    if roh["id"] != fid:
        raise ValueError(f"{pfad}: id {roh['id']!r} passt nicht zu {fid!r}")
    datei = FORMULARE[fid]
    qtitel = roh["quelle"]["titel"]
    regeln = roh["felder"]
    _pruefe_regeln(fid, regeln)
    vorauswahl, v_regeln, v_pflicht = {}, {}, {}
    for vid, v in roh.get("vorauswahl", {}).items():
        _pruefe_regeln(fid, v["felder"])
        vorauswahl[vid] = dict(v["titel"])
        v_regeln[vid] = tuple(v["felder"])
        v_pflicht[vid] = tuple(v.get("pflicht", []))
    slots: list[str] = []
    for r in [*regeln, *(r for rs in v_regeln.values() for r in rs)]:
        if "wenn" in r:  # Bedingungen füllen keinen Slot-Wert ein
            continue
        for s in _regel_slots(r):
            if s not in slots:
                slots.append(s)
    pflicht = list(roh["pflicht"])
    if not set(pflicht) <= set(slots):
        raise ValueError(f"{fid}: Pflicht-Slots {sorted(set(pflicht) - set(slots))} werden nicht gemappt")
    unterlagen = [
        Unterlage(text={"de": u["de"], "en": u["en"]}, quelle=_formular_quelle(qtitel, datei, u),
                  leistungen=tuple(u.get("leistungen", [])))
        for u in roh["unterlagen"]
    ]
    hinweis_quellen = [
        Quelle(**({"datei": datei} | q)) if q["art"] == "formular" else Quelle(**q) for q in roh.get("hinweis_quellen", [])
    ]
    adressen = {
        land: {"text": a["text"], "quelle": _formular_quelle(qtitel, datei, a)} for land, a in roh.get("adressen", {}).items()
    }
    return Formular(
        id=fid,
        titel=dict(roh["titel"]),
        datei=datei,
        stelle={"de": roh["stelle"]["de"], "en": roh["stelle"]["en"]},
        slots=slots,
        pflicht=pflicht,
        unterlagen=unterlagen,
        hinweise=dict(roh["hinweise"]),
        quelle=_formular_quelle(qtitel, datei, roh["quelle"]),
        stelle_quelle=_formular_quelle(qtitel, datei, roh["stelle"]),
        hinweis_quellen=hinweis_quellen,
        vorauswahl=vorauswahl,
        ohne_unterlagen=dict(roh.get("ohne_unterlagen", {})),
        adressen=adressen,
        gesperrte_seiten=tuple(roh.get("gesperrte_seiten", [])),
        _regeln=tuple(regeln),
        _vorauswahl_regeln=v_regeln,
        _vorauswahl_pflicht=v_pflicht,
    )


@cache
def alle_formulare() -> dict[str, Formular]:
    return {fid: _lade(fid) for fid in FORMULARE}


def formular(id: str) -> Formular:
    try:
        return alle_formulare()[id]
    except KeyError:
        raise KeyError(f"Unbekanntes Formular: {id!r}") from None


# ---------------------------------------------------------------- Werte


def _datum(wert: str) -> str:
    """TT.MM.JJJJ aus T.M.JJJJ, TT.MM.JJJJ oder JJJJ-MM-TT; sonst unverändert (→ ungültig)."""
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", wert) or re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", wert)
    if not m:
        return wert
    a, b, c = (int(x) for x in m.groups())
    tag, monat, jahr = (c, b, a) if a > 31 else (a, b, c)
    try:
        date(jahr, monat, tag)
    except ValueError:
        return wert
    return f"{tag:02d}.{monat:02d}.{jahr:04d}"


def normalisiere(slot_id: str, wert: str) -> str:
    """Bringt Eingaben in das Format der Formulare (SVNR/IBAN ohne Leerzeichen, Datum TT.MM.JJJJ)."""
    wert = " ".join(str(wert).split())
    if slot_id in ("person.svnr", "bank.iban"):
        wert = re.sub(r"[\s/.-]", "", wert).upper()
    elif SLOTS[slot_id].typ == "datum":
        wert = _datum(wert)
    return wert


def bereinige(werte: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Nur bekannte Slots mit gültigem Wert; ungültige Angaben werden gesondert gemeldet."""
    gut, schlecht = {}, []
    for slot_id, wert in werte.items():
        if slot_id not in SLOTS or wert is None or not str(wert).strip():
            continue
        w = normalisiere(slot_id, wert)
        if SLOTS[slot_id].gueltig(w):
            gut[slot_id] = w
        else:
            schlecht.append(slot_id)
    return gut, schlecht


def hausnummer_teile(wert: str) -> dict[str, str]:
    """Zerlegt „12/3/4“ (Haus/Stiege/Tür), „12/4“ (Haus/Tür) oder „12, Stiege 3, Tür 4“."""
    w = " ".join(wert.split())
    stiege = re.search(r"(?i)\b(?:Stiege|Stg\.?)\s*(\w+)", w)
    tuer = re.search(r"(?i)\b(?:Tür|Tuer|Top)\s*(\w+)", w)
    if stiege or tuer:
        haus = re.split(r"(?i)[,/]|\b(?:Stiege|Stg\.?|Tür|Tuer|Top)\b", w)[0].strip(" ,/")
        return {"hausnummer": haus, "stiege": stiege.group(1) if stiege else "", "tuer": tuer.group(1) if tuer else ""}
    teile = [t.strip() for t in w.split("/") if t.strip()]
    if len(teile) <= 1:
        return {"hausnummer": w, "stiege": "", "tuer": ""}
    if len(teile) == 2:
        return {"hausnummer": teile[0], "stiege": "", "tuer": teile[1]}
    return {"hausnummer": teile[0], "stiege": teile[1], "tuer": "/".join(teile[2:])}


def _feldwert(regel: dict, werte: dict[str, str]) -> tuple[str | None, list[str]]:
    """Wert für ein PDF-Feld und die dafür genutzten Slots."""
    if "wenn" in regel:
        return (regel["wert"], []) if all(s in werte for s in regel["wenn"]) else (None, [])
    if "teile" in regel:
        stuecke, genutzt = [], []
        for teil in regel["teile"]:
            namen = _PLATZHALTER.findall(teil)
            if not any(n in werte for n in namen):
                continue
            stuecke.append(" ".join(_PLATZHALTER.sub(lambda m: werte.get(m.group(1), ""), teil).split()))
            genutzt += [n for n in namen if n in werte]
        return (", ".join(stuecke), genutzt) if stuecke else (None, [])
    slot_id = regel["slot"]
    if slot_id not in werte:
        return None, []
    wert = werte[slot_id]
    if "werte" in regel:
        wert = regel["werte"].get(wert)
    elif "teil" in regel:
        wert = hausnummer_teile(wert)[regel["teil"]] or None
    return (wert, [slot_id]) if wert else (None, [])


# ---------------------------------------------------------------- PDF


def _feldname(obj: DictionaryObject) -> str:
    teile = []
    while obj is not None:
        if "/T" in obj:
            teile.append(str(obj["/T"]))
        obj = obj.get("/Parent")
        obj = obj.get_object() if obj is not None else None
    return ".".join(reversed(teile))


def _feldtyp(obj: DictionaryObject) -> str | None:
    while obj is not None:
        if "/FT" in obj:
            return str(obj["/FT"])
        obj = obj.get("/Parent")
        obj = obj.get_object() if obj is not None else None
    return None


def feldkarte(pdf: PdfReader | PdfWriter) -> dict[str, dict]:
    """Feldname → {"typ", "seiten" (1-basiert), "widgets", "feld"} über alle Widget-Annotationen."""
    karte: dict[str, dict] = {}
    for nr, seite in enumerate(pdf.pages, 1):
        for ref in seite.get("/Annots") or []:
            w = ref.get_object()
            if w.get("/Subtype") != "/Widget":
                continue
            feld = w if "/T" in w else w["/Parent"].get_object()
            eintrag = karte.setdefault(_feldname(feld), {"typ": _feldtyp(w), "seiten": set(), "widgets": [], "feld": feld})
            eintrag["seiten"].add(nr)
            eintrag["widgets"].append(w)
    return karte


def exportwerte(eintrag: dict) -> set[str]:
    """Mögliche Exportwerte eines Knopf-Felds (Schlüssel von /AP /N ohne /Off)."""
    werte: set[str] = set()
    for w in eintrag["widgets"]:
        ap = w.get("/AP")
        if ap and "/N" in ap:
            werte |= {str(k) for k in ap["/N"].get_object().keys() if k != "/Off"}
    return werte


def _setze_knopf(eintrag: dict, wert: str) -> None:
    name = NameObject(wert)
    eintrag["feld"][NameObject("/V")] = name
    for w in eintrag["widgets"]:
        zustaende = w["/AP"]["/N"].get_object().keys()
        w[NameObject("/AS")] = name if name in zustaende else NameObject("/Off")


def fehlende_pflichtangaben(id: str, werte: dict[str, str], leistung: str | None = None) -> list[str]:
    gut, _ = bereinige(werte)
    return [s for s in formular(id).pflicht_fuer(leistung) if s not in gut]


def ausfuellen(id: str, werte: dict[str, str], leistung: str | None = None) -> AusfuellErgebnis:
    """Füllt die Bürger:innen-Felder des Original-PDFs; `leistung` wählt eine Vorauswahl (z. B. pflege_zu_hause)."""
    f = formular(id)
    gut, ungueltig = bereinige(werte)
    writer = PdfWriter(clone_from=PdfReader(config.datei(f.datei)))
    karte = feldkarte(writer)
    texte: dict[str, str] = {}
    knoepfe: dict[str, str] = {}
    befuellt: list[str] = []
    for regel in f.regeln(leistung):
        wert, genutzt = _feldwert(regel, gut)
        if wert is None:
            continue
        eintrag = karte.get(regel["feld"])
        if eintrag is None:
            raise ValueError(f"{id}: Feld {regel['feld']!r} fehlt im PDF")
        if eintrag["typ"] == "/Sig" or eintrag["seiten"] <= set(f.gesperrte_seiten):
            raise ValueError(f"{id}: Feld {regel['feld']!r} ist Unterschrift oder gesperrter Teil")
        if eintrag["typ"] == "/Btn":
            if wert not in exportwerte(eintrag):
                raise ValueError(f"{id}: Exportwert {wert!r} fehlt in {regel['feld']!r}")
            knoepfe[regel["feld"]] = wert
        else:
            texte[regel["feld"]] = wert
        befuellt += [s for s in genutzt if s not in befuellt]
    if texte:
        writer.update_page_form_field_values(None, texte, auto_regenerate=False)
    for name, wert in knoepfe.items():
        _setze_knopf(karte[name], wert)
    writer.set_need_appearances_writer(True)
    puffer = BytesIO()
    writer.write(puffer)
    return AusfuellErgebnis(
        pdf=puffer.getvalue(),
        befuellt=befuellt,
        fehlend_pflicht=[s for s in f.pflicht_fuer(leistung) if s not in gut],
        ungueltig=ungueltig,
    )
