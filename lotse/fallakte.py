"""Fallakte: Schritte und Unterlagen je Leistung, Status und nächster Schritt."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from lotse.models import Quelle

STATUS = ("offen", "in_arbeit", "erledigt")

# Antragskette: Ein späterer Schritt setzt die früheren voraus (unterschrieben ⇒ ausgefüllt).
ANTRAG_KETTE = ("antrag_ausfuellen", "antrag_unterschreiben", "antrag_einreichen")


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
        return {
            "id": self.id,
            "schritt_id": self.kurz_id,
            "text": self.text.get(sprache) or self.text.get("de", ""),
            "art": self.art,
            "status": self.status,
            "quelle": self.quelle.to_dict() if self.quelle else None,
        }


@dataclass
class Eintrag:
    """Eine Leistung in der Fallakte."""

    leistung_id: str
    titel: dict[str, str]
    schritte: list[Schritt] = field(default_factory=list)
    unterlagen: list[Schritt] = field(default_factory=list)

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
class Fallakte:
    eintraege: dict[str, Eintrag] = field(default_factory=dict)
    historie: list[dict] = field(default_factory=list)

    def ergaenze(
        self,
        leistung_id: str,
        titel: dict[str, str],
        schritte: list[dict],
        unterlagen: list[tuple[dict[str, str], Quelle | None]],
    ) -> Eintrag:
        """Legt eine Leistung an bzw. ergänzt fehlende Schritte/Unterlagen (idempotent)."""
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
        for text, quelle in unterlagen:
            if _norm(text["de"]) in texte:
                continue
            texte.add(_norm(text["de"]))
            nr = len(eintrag.unterlagen) + 1
            eintrag.unterlagen.append(
                Schritt(f"{leistung_id}.unterlage_{nr}", leistung_id, dict(text), art="unterlage", quelle=quelle)
            )
        return eintrag

    def behalte(self, leistung_ids: list[str]) -> None:
        """Entfernt Leistungen, die nicht mehr im Bündel sind – außer sie haben schon Fortschritt."""
        for lid in list(self.eintraege):
            if lid not in leistung_ids and not self.eintraege[lid].hat_fortschritt():
                del self.eintraege[lid]

    def ordne(self, leistung_ids: list[str]) -> None:
        """Reihenfolge der Akte wie im Bündel (bestimmt den nächsten Schritt der ganzen Akte)."""
        rang = {lid: i for i, lid in enumerate(leistung_ids)}
        self.eintraege = dict(sorted(self.eintraege.items(), key=lambda kv: rang.get(kv[0], len(rang))))

    def schritt(self, schritt_id: str) -> Schritt:
        lid = schritt_id.split(".", 1)[0]
        eintrag = self.eintraege.get(lid)
        if eintrag:
            for s in eintrag.schritte + eintrag.unterlagen:
                if s.id == schritt_id:
                    return s
        raise KeyError(schritt_id)

    def setze(self, schritt_id: str, status: str, zeit: datetime | None = None) -> Schritt:
        """Setzt den Status; „erledigt“ in der Antragskette erledigt auch die Vorstufen."""
        if status not in STATUS:
            raise ValueError(f"Unbekannter Status: {status}")
        ziel = self.schritt(schritt_id)
        zeit = zeit or datetime.now()
        betroffen = [ziel]
        if status == "erledigt" and ziel.art == "schritt" and ziel.kurz_id in ANTRAG_KETTE:
            vorstufen = ANTRAG_KETTE[: ANTRAG_KETTE.index(ziel.kurz_id)]
            betroffen = [
                s for s in self.eintraege[ziel.leistung_id].schritte
                if s.kurz_id in vorstufen and s.status != "erledigt"
            ] + betroffen
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

    def to_dict(self, sprache: str) -> dict:
        naechster = self.naechster_schritt()
        eintraege = []
        for e in self.eintraege.values():
            ns = e.naechster_schritt()
            eintraege.append({
                "leistung_id": e.leistung_id,
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
