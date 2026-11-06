"""Fallakte: Schritte und Unterlagen je Leistung bzw. Termin, Status, nächster Schritt und Kalendereintrag."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from lotse.models import Quelle

STATUS = ("offen", "in_arbeit", "erledigt")

# Antragskette: Ein späterer Schritt setzt die früheren voraus (unterschrieben ⇒ ausgefüllt).
ANTRAG_KETTE = ("antrag_ausfuellen", "antrag_unterschreiben", "antrag_einreichen")
# Terminkette: angefragt → eingetragen (vereinbart) → wahrgenommen.
TERMIN_KETTE = ("anfragen", "eintragen", "wahrnehmen")
TERMIN_STATUS = ("vorbereitet", "vereinbart", "erledigt")

# Unterlagen, die nur in bestimmten Fällen nötig sind („Nur bei …“, „Ohne …“, „…, falls vorhanden“, „(bei …)“)
_BEDINGT = re.compile(r"^(nur|bei|ohne|falls|wenn|je nach)\b|, falls vorhanden\b|\((bei|nur|falls|wenn) ",
                      re.IGNORECASE)


def bedingt(text_de: str) -> bool:
    """Ist die Unterlage nur nötig, wenn ein bestimmter Fall zutrifft?"""
    return _BEDINGT.search(text_de.strip()) is not None


@dataclass
class Schritt:
    id: str  # global eindeutig: "<leistung_id>.<schritt_id>"
    leistung_id: str
    text: dict[str, str]
    art: str = "schritt"  # schritt | unterlage
    status: str = "offen"
    quelle: Quelle | None = None

    @property
    def kurz_id(self) -> str:
        return self.id.split(".", 1)[1]

    def to_dict(self, sprache: str) -> dict:
        d = {
            "id": self.id,
            "schritt_id": self.kurz_id,
            "text": self.text.get(sprache) or self.text.get("de", ""),
            "art": self.art,
            "status": self.status,
            "quelle": self.quelle.to_dict() if self.quelle else None,
        }
        if self.art == "unterlage":
            d["bedingt"] = bedingt(self.text.get("de", ""))
        return d


@dataclass
class Eintrag:
    """Eine Leistung (oder ein Termin) in der Fallakte."""

    leistung_id: str
    titel: dict[str, str]
    schritte: list[Schritt] = field(default_factory=list)
    unterlagen: list[Schritt] = field(default_factory=list)
    art: str = "leistung"  # leistung | termin
    termin_id: str | None = None

    def naechster_schritt(self) -> Schritt | None:
        """Schritt „in Arbeit“, sonst der erste offene nach dem zuletzt erledigten, sonst der erste offene."""
        if aktiv := next((s for s in self.schritte if s.status == "in_arbeit"), None):
            return aktiv
        letzter = max((i for i, s in enumerate(self.schritte) if s.status == "erledigt"), default=-1)
        danach = next((s for s in self.schritte[letzter + 1:] if s.status != "erledigt"), None)
        return danach or next((s for s in self.schritte if s.status != "erledigt"), None)

    def hat_fortschritt(self) -> bool:
        return any(s.status != "offen" for s in self.schritte + self.unterlagen)


@dataclass
class Termin:
    """Vorbereiteter Termin. Gebucht wird nie durch den Lotsen; Datum/Uhrzeit trägt die Person selbst ein."""

    id: str  # "termin_<n>", zugleich Eintrag in der Fallakte
    anlass: str  # Wert von termin.anlass
    ort: str = ""  # wie angegeben (termin.ort)
    zeit: str = ""  # Wert von termin.zeit oder ""
    bundesland: str = ""
    leistung_id: str | None = None
    datum: str = ""  # TT.MM.JJJJ
    uhrzeit: str = ""  # HH:MM
    erstellt: str = ""
    uid: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass
class Fallakte:
    eintraege: dict[str, Eintrag] = field(default_factory=dict)
    historie: list[dict] = field(default_factory=list)
    termine: dict[str, Termin] = field(default_factory=dict)
    # ersetzte Unterlagen → Unterlage, die sie vertritt (gespeicherte Haken älterer Fälle bleiben gültig)
    aliase: dict[str, str] = field(default_factory=dict)

    def ergaenze(
        self,
        leistung_id: str,
        titel: dict[str, str],
        schritte: list[dict],
        unterlagen: list[tuple[dict[str, str], Quelle | None]],
        nummern: list[int] | None = None,
    ) -> Eintrag:
        """Legt eine Leistung an bzw. ergänzt fehlende Schritte/Unterlagen (idempotent). `nummern` gibt jeder
        Unterlage eine feste Nummer (stabile IDs, gleich in welcher Reihenfolge sie dazukommen); ohne sie wird
        fortlaufend nummeriert."""
        eintrag = self.eintraege.get(leistung_id)
        if eintrag is None:
            eintrag = self.eintraege[leistung_id] = Eintrag(leistung_id, dict(titel))
        vorhanden = {s.kurz_id for s in eintrag.schritte}
        for s in schritte:
            if s["id"] not in vorhanden:
                vorhanden.add(s["id"])
                eintrag.schritte.append(
                    Schritt(f"{leistung_id}.{s['id']}", leistung_id, {"de": s["de"], "en": s["en"]})
                )
        texte = {_norm(u.text["de"]) for u in eintrag.unterlagen}
        ids = {u.id for u in eintrag.unterlagen}
        for i, (text, quelle) in enumerate(unterlagen):
            if nummern is not None:
                nr = nummern[i]
            else:  # fortlaufende Nummer auch nach entfernten Unterlagen eindeutig
                nr = max((int(u.kurz_id.removeprefix("unterlage_")) for u in eintrag.unterlagen), default=0) + 1
            uid = f"{leistung_id}.unterlage_{nr}"
            if _norm(text["de"]) in texte or uid in ids:
                continue
            texte.add(_norm(text["de"]))
            ids.add(uid)
            eintrag.unterlagen.append(Schritt(uid, leistung_id, dict(text), art="unterlage", quelle=quelle))
        if nummern is not None:
            eintrag.unterlagen.sort(key=lambda u: int(u.kurz_id.removeprefix("unterlage_")))
        return eintrag

    def ersetze_unterlagen(self, leistung_id: str, ersetzungen: dict[str, str]) -> None:
        """Unterlagen, die eine andere inhaltlich doppelt (`kurz_id` → `kurz_id`), entfernen; ihr Status geht auf die
        vertretende Unterlage über, solange diese noch offen ist. Die alten IDs bleiben als Alias erreichbar.
        Die Aliase der Leistung entsprechen danach genau `ersetzungen`."""
        praefix = f"{leistung_id}."
        self.aliase = {a: z for a, z in self.aliase.items() if not a.startswith(praefix)}
        eintrag = self.eintraege.get(leistung_id)
        for alt, neu in ersetzungen.items():
            alt_id, neu_id = praefix + alt, praefix + neu
            self.aliase[alt_id] = neu_id
            if eintrag is None:
                continue
            alte = next((u for u in eintrag.unterlagen if u.id == alt_id), None)
            ziel = next((u for u in eintrag.unterlagen if u.id == neu_id), None)
            if alte is None or ziel is None:
                continue
            if ziel.status == "offen":
                ziel.status = alte.status
            eintrag.unterlagen.remove(alte)

    def entferne_offene_unterlagen(self, leistung_id: str, texte: list[dict[str, str]]) -> None:
        """Unterlagen mit diesen Texten entfernen, solange sie noch offen sind (z. B. Formular gilt nicht mehr)."""
        eintrag = self.eintraege.get(leistung_id)
        if eintrag is None:
            return
        weg = {_norm(t["de"]) for t in texte}
        eintrag.unterlagen = [u for u in eintrag.unterlagen if u.status != "offen" or _norm(u.text["de"]) not in weg]

    def behalte(self, leistung_ids: list[str]) -> None:
        """Entfernt Leistungen, die nicht mehr im Bündel sind – außer sie haben schon Fortschritt. Termine bleiben."""
        for lid in list(self.eintraege):
            e = self.eintraege[lid]
            if e.art == "leistung" and lid not in leistung_ids and not e.hat_fortschritt():
                del self.eintraege[lid]

    def ordne(self, leistung_ids: list[str]) -> None:
        """Reihenfolge der Akte wie im Bündel (bestimmt den nächsten Schritt der ganzen Akte); Termine danach."""
        rang = {lid: i for i, lid in enumerate(leistung_ids)}
        self.eintraege = dict(sorted(self.eintraege.items(), key=lambda kv: rang.get(kv[0], len(rang))))

    # -- Termine -------------------------------------------------------------------------------------------

    def neue_termin_id(self) -> str:
        nummern = [int(tid.removeprefix("termin_")) for tid in self.termine]
        return f"termin_{max(nummern, default=0) + 1}"

    def neuer_termin(self, termin: Termin, titel: dict[str, str], schritte: list[dict]) -> Eintrag:
        """Legt Termin und zugehörigen Fallakten-Eintrag an (Schritte laut TERMIN_KETTE)."""
        if [s["id"] for s in schritte] != list(TERMIN_KETTE):
            raise ValueError(f"Terminschritte müssen {TERMIN_KETTE} sein")
        self.termine[termin.id] = termin
        eintrag = self.ergaenze(termin.id, titel, schritte, [])
        eintrag.art, eintrag.termin_id = "termin", termin.id
        return eintrag

    def termin_status(self, termin_id: str) -> str:
        """vorbereitet → vereinbart (Datum eingetragen) → erledigt (wahrgenommen)."""
        termin = self.termine[termin_id]
        eintrag = self.eintraege.get(termin_id)
        status = {s.kurz_id: s.status for s in eintrag.schritte} if eintrag else {}
        if status.get("wahrnehmen") == "erledigt":
            return "erledigt"
        if termin.datum or status.get("eintragen") == "erledigt":
            return "vereinbart"
        return "vorbereitet"

    # -- Status ----------------------------------------------------------------------------------------------

    def schritt(self, schritt_id: str) -> Schritt:
        schritt_id = self.aliase.get(schritt_id, schritt_id)
        lid = schritt_id.split(".", 1)[0]
        eintrag = self.eintraege.get(lid)
        if eintrag:
            for s in eintrag.schritte + eintrag.unterlagen:
                if s.id == schritt_id:
                    return s
        raise KeyError(schritt_id)

    def setze(self, schritt_id: str, status: str, zeit: datetime | None = None) -> Schritt:
        """Setzt den Status; „erledigt“ in der Antrags- bzw. Terminkette erledigt auch die Vorstufen."""
        if status not in STATUS:
            raise ValueError(f"Unbekannter Status: {status}")
        ziel = self.schritt(schritt_id)
        zeit = zeit or datetime.now()
        eintrag = self.eintraege[ziel.leistung_id]
        kette = TERMIN_KETTE if eintrag.art == "termin" else ANTRAG_KETTE
        betroffen = [ziel]
        if status == "erledigt" and ziel.art == "schritt" and ziel.kurz_id in kette:
            vorstufen = kette[: kette.index(ziel.kurz_id)]
            betroffen = [s for s in eintrag.schritte if s.kurz_id in vorstufen and s.status != "erledigt"] + betroffen
        for s in betroffen:
            if s.status != status:
                self.historie.append({
                    "zeit": zeit.isoformat(timespec="seconds"),
                    "schritt_id": s.id,
                    "leistung_id": s.leistung_id,
                    "von": s.status,
                    "nach": status,
                })
                s.status = status
        return ziel

    def naechster_schritt(self, leistung_id: str | None = None) -> Schritt | None:
        """Nächster offener Schritt einer Leistung bzw. der ganzen Akte (zuerst „in Arbeit“)."""
        if leistung_id is not None:
            eintrag = self.eintraege.get(leistung_id)
            return eintrag.naechster_schritt() if eintrag else None
        kandidaten = [s for e in self.eintraege.values() if (s := e.naechster_schritt())]
        return next((s for s in kandidaten if s.status == "in_arbeit"), kandidaten[0] if kandidaten else None)

    def relevante(self, primaer: list[str] | None = None) -> list[Eintrag]:
        """Wichtigste Einträge: die primären Leistungen, begonnene Leistungen und Termine (None = alle)."""
        if primaer is None:
            return list(self.eintraege.values())
        return [e for e in self.eintraege.values()
                if e.art == "termin" or e.leistung_id in primaer or e.hat_fortschritt()]

    def uebersicht(self, sprache: str, primaer: list[str] | None = None) -> dict:
        """Erledigte und offene Schritte der wichtigsten Einträge (siehe `relevante`) plus nächster Schritt."""
        schritte = [s for e in self.relevante(primaer) for s in e.schritte]
        naechster = self.naechster_schritt()
        text = ""
        if naechster is not None:
            titel = self.eintraege[naechster.leistung_id].titel
            text = f"{titel.get(sprache) or titel.get('de', '')} – " \
                   f"{(naechster.text.get(sprache) or naechster.text.get('de', '')).rstrip('.')}"
        return {
            "erledigt": sum(s.status == "erledigt" for s in schritte),
            "offen": sum(s.status != "erledigt" for s in schritte),
            "naechster": text,
        }

    def to_dict(self, sprache: str) -> dict:
        naechster = self.naechster_schritt()
        eintraege = []
        for e in self.eintraege.values():
            ns = e.naechster_schritt()
            eintraege.append({
                "leistung_id": e.leistung_id,
                "art": e.art,
                "termin_id": e.termin_id,
                "titel": e.titel.get(sprache) or e.titel.get("de", ""),
                "schritte": [s.to_dict(sprache) for s in e.schritte],
                "unterlagen": [u.to_dict(sprache) for u in e.unterlagen],
                "naechster_schritt": ns.id if ns else None,
                "erledigt": sum(s.status == "erledigt" for s in e.schritte),
                "gesamt": len(e.schritte),
            })
        historie = []
        for h in self.historie:
            try:
                s = self.schritt(h["schritt_id"])
            except KeyError:
                continue
            historie.append({**h, "text": s.text.get(sprache, ""), "titel": self.eintraege[s.leistung_id].titel.get(sprache, "")})
        return {
            "eintraege": eintraege,
            "naechster_schritt": None if naechster is None else {
                "id": naechster.id,
                "leistung_id": naechster.leistung_id,
                "titel": self.eintraege[naechster.leistung_id].titel.get(sprache, ""),
                "text": naechster.text.get(sprache, ""),
                "status": naechster.status,
            },
            "historie": historie,
        }


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


# ---------------------------------------------------------------------------
# Kalendereintrag (RFC 5545)
# ---------------------------------------------------------------------------

_VTIMEZONE_WIEN = (
    "BEGIN:VTIMEZONE",
    "TZID:Europe/Vienna",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0200",
    "TZNAME:CEST",
    "DTSTART:19700329T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0100",
    "TZNAME:CET",
    "DTSTART:19701025T030000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
)


def _ics_text(text: str) -> str:
    """TEXT-Wert nach RFC 5545 § 3.3.11 maskieren."""
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _falte_zeile(zeile: str) -> str:
    """Zeilen über 75 Oktette falten (RFC 5545 § 3.1), ohne UTF-8-Zeichen zu teilen."""
    teile, aktuell, laenge = [], "", 0
    for zeichen in zeile:
        n = len(zeichen.encode("utf-8"))
        if laenge + n > (75 if not teile else 74):
            teile.append(aktuell)
            aktuell, laenge = "", 0
        aktuell += zeichen
        laenge += n
    teile.append(aktuell)
    return "\r\n ".join(teile)


def ics(termin: Termin, zusammenfassung: str, beschreibung: str, jetzt: datetime | None = None) -> str:
    """Kalenderdatei mit einem Ereignis in Europe/Vienna; ohne Uhrzeit ganztägig. Enthält nur, was die Person
    angegeben hat (Datum, Uhrzeit, Ort), und die Texte des Lotsen. Erinnerung einen Tag vorher."""
    if not termin.datum:
        raise ValueError("Termin hat noch kein Datum")
    tag, monat, jahr = (int(x) for x in termin.datum.split("."))
    datum = f"{jahr:04d}{monat:02d}{tag:02d}"
    if termin.uhrzeit:
        stunde, minute = (int(x) for x in termin.uhrzeit.split(":"))
        start = f"DTSTART;TZID=Europe/Vienna:{datum}T{stunde:02d}{minute:02d}00"
    else:
        start = f"DTSTART;VALUE=DATE:{datum}"
    stempel = (jetzt or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zeilen = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Nexovo//SV KI-Lotse//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        *(_VTIMEZONE_WIEN if termin.uhrzeit else ()),
        "BEGIN:VEVENT",
        f"UID:{termin.uid}@sv-ki-lotse",
        f"DTSTAMP:{stempel}",
        start,
        f"SUMMARY:{_ics_text(zusammenfassung)}",
        *([f"LOCATION:{_ics_text(termin.ort)}"] if termin.ort else []),
        f"DESCRIPTION:{_ics_text(beschreibung)}",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        "TRIGGER:-P1D",
        f"DESCRIPTION:{_ics_text(zusammenfassung)}",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_falte_zeile(z) for z in zeilen) + "\r\n"
