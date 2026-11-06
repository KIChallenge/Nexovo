"""Optionale Sprachmodell-Anbindung (Azure Foundry, OpenAI-kompatible Chat Completions).

Aktiv nur mit `AZURE_API_KEY` und `AZURE_OPENAI_ENDPOINT`. Jede Ausgabe wird geprüft
(`grenzen.pruefe_antwort`, Zitate, Zahlen); bei Verstoß, Fehler oder Timeout liefern die
Funktionen ein leeres Ergebnis und der Aufrufer nutzt den regelbasierten Text.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import openai

from lotse import config, grenzen
from lotse.models import WEITERE_SPRACHEN
from lotse.slots import SLOTS

log = logging.getLogger(__name__)

SZENARIEN = ("pflege", "gesundheit", "entlassung", "kind", "unterstuetzung")
TIMEOUT_S = 20.0

# Slots, die das Modell aus freiem Text erkennen darf (keine sensiblen, keine medizinischen).
_VERSTEHE_SLOTS = (
    "anliegen.fuer_wen", "person.bundesland", "versicherung.krankenversicherung",
    "versicherung.pension", "pflege.antragsart", "pflege.stufe", "kind.alter", "termin.anlass", "termin.zeit",
)
_SPRACHNAMEN = {"de": "Deutsch", "en": "Englisch", "tr": "Türkisch", "bs": "Bosnisch/Kroatisch/Serbisch",
                "uk": "Ukrainisch", "ar": "Arabisch"}

_client: openai.OpenAI | None = None


def aktiv() -> bool:
    return bool(config.azure_api_key() and config.azure_endpoint())


def _client_holen() -> openai.OpenAI:
    global _client
    if _client is None:
        _client = openai.OpenAI(
            base_url=config.azure_endpoint(), api_key=config.azure_api_key(), timeout=TIMEOUT_S, max_retries=1
        )
    return _client


def _chat(system: str, nutzer: str, max_tokens: int, json_modus: bool = False, timeout: float = TIMEOUT_S) -> str:
    """Ein Chat-Completions-Aufruf; "" bei jedem Fehler. Schlüssel und Inhalte werden nie geloggt."""
    if not aktiv():
        return ""
    extra: dict = {"response_format": {"type": "json_object"}} if json_modus else {}
    try:
        antwort = _client_holen().chat.completions.create(
            model=config.azure_modell(),
            messages=[{"role": "system", "content": system}, {"role": "user", "content": nutzer}],
            max_completion_tokens=max_tokens,
            reasoning_effort="low",
            timeout=timeout,
            **extra,
        )
    except Exception as e:  # Netz, Timeout, Konfiguration, Kontingent: immer regelbasiert weiter
        log.warning("Sprachmodell nicht verfügbar (%s) – regelbasierte Antwort.", type(e).__name__)
        return ""
    if not antwort.choices:
        return ""
    return (antwort.choices[0].message.content or "").strip()


def _verstehe_system() -> str:
    slots = []
    for sid in _VERSTEHE_SLOTS:
        s = SLOTS[sid]
        werte = " | ".join(s.optionen) if s.optionen else (f"Muster {s.muster}" if s.muster else "Text")
        slots.append(f'- "{sid}" ({s.label["de"]}): {werte}')
    return (
        "Du ordnest Anliegen von Versicherten der österreichischen Sozialversicherung zu. Die Person schreibt "
        "Deutsch, Englisch, Dialekt oder eine andere Sprache. Antworte nur mit einem JSON-Objekt "
        "{\"art\": \"situation\"|\"frage\"|\"termin\"|\"status\", \"szenarien\": [...], \"slots\": {...}, "
        "\"suche\": \"...\"}.\n"
        "art: \"situation\", wenn die Person ihre Lage schildert oder fragt, welche Angebote, Leistungen oder "
        "Schritte für ihre Lage in Frage kommen (z. B. \"Meine Mutter kommt allein nicht mehr zurecht\", "
        "\"Bin aus dem Spital entlassen worden\", \"Ich habe ein Kind, welche Angebote gibt es?\"); "
        "\"frage\", wenn sie eine konkrete Sachfrage zu einer bestimmten Leistung, einem Gesetz, einem Betrag, "
        "einer Frist oder einem Ablauf stellt (z. B. \"Was regelt das ASVG zur Rezeptgebühr?\", "
        "\"Wie lange gibt es Krankengeld?\"); \"termin\", wenn sie einen Arzt-, Zahnarzt- oder anderen "
        "Gesundheitstermin vereinbaren möchte (z. B. \"Ich möchte einen Arzttermin\"); \"status\", wenn sie nach dem "
        "Stand ihrer bisherigen Schritte fragt (z. B. \"Was ist noch offen?\"). Bei \"frage\", \"termin\" und "
        "\"status\" bleibt \"szenarien\" leer.\n"
        "suche: nur bei \"frage\" – die Frage als kurze deutsche Stichworte mit den Fachbegriffen der "
        "österreichischen Sozialversicherung (z. B. \"Rezeptgebühr Befreiung\"), sonst \"\".\n"
        "Szenarien (nur diese IDs, sortiert nach Relevanz, leer wenn keines passt):\n"
        "- \"pflege\": Pflege oder Betreuung einer Person, Pflegegeld, Pflege zu Hause\n"
        "- \"gesundheit\": Gesundheitsförderung, Vorsorge, Bewegung, Ernährung\n"
        "- \"entlassung\": nach einem Spitalsaufenthalt, Entlassungsbrief, Befund erhalten\n"
        "- \"kind\": Angebote für Kinder, Schwangerschaft, Familie\n"
        "- \"unterstuetzung\": soziale oder finanzielle Notlage, Miete, Lebensunterhalt, Sozialhilfe, "
        "Unterstützung in besonderen Lebenslagen\n"
        "Slots (nur diese IDs, nur wenn der Text sie ausdrücklich nennt, Werte exakt wie angegeben):\n"
        + "\n".join(slots)
        + "\nBewerte oder deute keine medizinischen Inhalte."
    )


_ARTEN = ("situation", "frage", "termin", "status")


def verstehe(text: str, sprache: str) -> dict:
    """Szenarien und Slots aus freiem Text; unbekannte IDs und ungültige Werte werden verworfen.

    Zusätzlich (nur wenn das Modell sie liefert): "art" (situation | frage | termin | status) und "suche"
    (deutsche Stichworte einer Sachfrage für die Suche in den Quellen).
    """
    ergebnis: dict = {"szenarien": [], "slots": {}}
    name = _SPRACHNAMEN.get(sprache, sprache)
    roh = _chat(_verstehe_system(), f"Sprache der Sitzung: {name}\nText: {text}", 600, json_modus=True)
    if not roh or grenzen.pruefe_antwort(roh):
        return ergebnis
    try:
        daten = json.loads(roh)
    except ValueError:
        return ergebnis
    if not isinstance(daten, dict):
        return ergebnis
    art = daten.get("art")
    if art in _ARTEN:
        ergebnis["art"] = art
    szenarien = daten.get("szenarien")
    # Sachfragen beantwortet die Wissensschicht; nur geschilderte Lebenslagen eröffnen ein Szenario
    if isinstance(szenarien, list) and art not in ("frage", "termin", "status"):
        for sz in szenarien:
            if isinstance(sz, str) and sz in SZENARIEN and sz not in ergebnis["szenarien"]:
                ergebnis["szenarien"].append(sz)
    slots = daten.get("slots")
    if isinstance(slots, dict):
        for sid, wert in slots.items():
            if sid in _VERSTEHE_SLOTS and isinstance(wert, str) and SLOTS[sid].gueltig(wert):
                ergebnis["slots"][sid] = wert.strip()
    suche = daten.get("suche")
    if art == "frage" and isinstance(suche, str) and suche.strip():
        ergebnis["suche"] = " ".join(suche.split())[:200]
    return ergebnis


_GRENZ_KATEGORIEN = ("diagnose", "befund", "risiko", "therapie", "medikament", "dosis")

_GRENZ_SYSTEM = (
    "Du prüfst Anfragen an einen Wegweiser für Leistungen der österreichischen Sozialversicherung. "
    "Er darf keine medizinische Beurteilung abgeben. Antworte nur mit einem JSON-Objekt "
    "{\"kategorie\": null | \"diagnose\" | \"befund\" | \"risiko\" | \"therapie\" | \"medikament\" | \"dosis\"}.\n"
    "- diagnose: was jemand hat oder ob Beschwerden/Symptome etwas Ernstes sind\n"
    "- befund: was Befunde, Mess- oder Laborwerte bedeuten oder ob ein Wert normal ist\n"
    "- risiko: persönliches Erkrankungsrisiko\n"
    "- therapie: ob eine Behandlung, Operation, Reha oder Kur für die Person medizinisch nötig oder sinnvoll ist, "
    "oder welche Behandlung die richtige ist\n"
    "- medikament: ob oder welches Medikament jemand nehmen soll\n"
    "- dosis: Medikamente absetzen, weglassen, ändern oder dosieren\n"
    "null bei allen administrativen Anliegen, auch wenn sie medizinische Wörter enthalten: Anträge, Zuständigkeit, "
    "Kosten, Bewilligung, Erstattung, Transport, Unterlagen, Fristen, Angebote, Leistungen, Termine. Beispiele für null: "
    "\"Wer zahlt den Transport zur Bestrahlung?\", \"Muss mein Medikament bewilligt werden?\", "
    "\"Im Brief steht, Reha wird empfohlen – was muss ich tun?\", \"Meine Mutter ist chronisch krank, was kann ich tun?\", "
    "\"Ich habe Diabetes – gibt es ein Programm der ÖGK?\", \"Wie beantrage ich eine Reha?\", "
    "\"Ich glaube, ich brauche eine Impfung – wo bekomme ich einen Termin?\", "
    "\"Ich möchte einen Arzttermin wegen Rückenschmerzen\", "
    "\"Mein Vater hatte Darmkrebs. Welche Vorsorgeuntersuchungen gibt es?\" (Frage nach Angeboten; "
    "risiko nur, wenn eine persönliche Einschätzung des Risikos verlangt wird)."
)


def grenzkategorie(text: str) -> str | None:
    """Zweite Stufe der Grenzprüfung; None bei administrativen Anliegen und bei jedem Fehler (dann gelten die Regeln)."""
    roh = _chat(_GRENZ_SYSTEM, text, 300, json_modus=True)
    try:
        kategorie = json.loads(roh).get("kategorie") if roh else None
    except (ValueError, AttributeError):
        return None
    return kategorie if kategorie in _GRENZ_KATEGORIEN else None


BILD_MIME = ("image/jpeg", "image/png", "image/webp")
_BILD_TIMEOUT_S = 60.0
_TRANSKRIPT_SYSTEM = (
    "Transkribiere den gesamten Text im Bild wörtlich und vollständig, Zeile für Zeile, in der Originalsprache. "
    "Keine Zusammenfassung, keine Deutung, keine Ergänzungen, keine Korrekturen. Tabellenzeilen als eine Zeile mit "
    "„ | “ zwischen den Spalten. Unleserliches als [unleserlich]. Ohne Text im Bild: leere Antwort."
)


def transkribiere(inhalt: bytes, mime: str) -> str:
    """Wörtliche Abschrift eines Fotos oder Scans; "" ohne KI-Modus, bei nicht unterstütztem Format oder Fehler."""
    if not aktiv() or mime not in BILD_MIME or not inhalt:
        return ""
    url = f"data:{mime};base64,{base64.b64encode(inhalt).decode()}"
    try:
        antwort = _client_holen().chat.completions.create(
            model=config.azure_modell(),
            messages=[
                {"role": "system", "content": _TRANSKRIPT_SYSTEM},
                {"role": "user", "content": [
                    {"type": "text", "text": "Bitte wörtlich abschreiben."},
                    {"type": "image_url", "image_url": {"url": url}},
                ]},
            ],
            max_completion_tokens=6000,
            reasoning_effort="low",
            timeout=_BILD_TIMEOUT_S,
        )
    except Exception as e:  # Netz, Timeout, Format: Aufrufer meldet „nicht lesbar“
        log.warning("Bild konnte nicht transkribiert werden (%s).", type(e).__name__)
        return ""
    if not antwort.choices:
        return ""
    return (antwort.choices[0].message.content or "").strip()


def _formuliere_system(sprache: str, stil: str) -> str:
    sprache_txt = "Englisch" if sprache == "en" else "Deutsch"
    stil_txt = (
        "Höchstens 8 Sätze; nenne auch Voraussetzungen und Fundstellen, soweit sie in den Fakten stehen."
        if stil == "ausfuehrlich"
        else "Höchstens 4 kurze Sätze in einfacher Sprache."
    )
    return (
        "Du bist der SV KI-Lotse, ein Wegweiser durch Leistungen der österreichischen Sozialversicherung.\n"
        "Regeln:\n"
        "- Verwende ausschließlich die nummerierten Fakten aus der Nutzernachricht, kein Vorwissen.\n"
        "- Belege jede Aussage mit der Nummer ihres Fakts in eckigen Klammern, z. B. [1].\n"
        "- Nenne keine Zahlen, Beträge, Fristen, Adressen oder Telefonnummern, die nicht in den Fakten stehen.\n"
        "- Keine Diagnose, keine Befundinterpretation, keine Risikobewertung, keine Therapie-, "
        "Medikamenten- oder Dosierungsempfehlung.\n"
        "- Ordne keine persönlichen Mess- oder Befundwerte ein. Bei gesundheitlichen Fragen verweise an "
        "Ärztin oder Arzt.\n"
        "- Beantworten die Fakten eine Verwaltungsfrage nicht, sage das in einem Satz und verweise an den "
        "zuständigen Sozialversicherungsträger.\n"
        "- Sprich die Person mit „Sie“ an. Formuliere natürlich (Deutsch: „Laut den Quellen …“, Englisch: "
        "„According to the sources …“), nie „Die Fakten sagen“ bzw. „The facts say“.\n"
        f"- Antworte auf {sprache_txt}. {stil_txt}\n"
        "- Nur Fließtext, kein Markdown."
    )


def formuliere(fakten: list[dict], sprache: str, stil: str, frage: str = "") -> str:
    """Antworttext aus nummerierten Fakten `[{n, text, quelle}]`; "" → regelbasierten Text verwenden."""
    if not fakten:
        return ""
    nutzer = json.dumps({"frage": frage, "fakten": fakten}, ensure_ascii=False)
    roh = _chat(_formuliere_system(sprache, stil), nutzer, 1200)
    if not roh:
        return ""
    verstoesse = pruefe_ausgabe(roh, fakten, frage)
    if verstoesse:
        log.info("KI-Text verworfen: %s", "; ".join(verstoesse))
        return ""
    return roh


_ZITAT = re.compile(r"\[(\d+)\]")
_ZAHL = re.compile(r"\d+(?:[.,]\d+)*")


def _ziffern(text: str) -> set[str]:
    return {re.sub(r"\D", "", z) for z in _ZAHL.findall(text)}


def pruefe_ausgabe(text: str, fakten: list[dict], frage: str = "") -> list[str]:
    """Verstöße eines generierten Texts: Grenzen, fehlende/unbekannte Zitate, unbelegte Zahlen."""
    verstoesse = list(grenzen.pruefe_antwort(text))
    gueltig = {int(f["n"]) for f in fakten}
    zitiert = {int(n) for n in _ZITAT.findall(text)}
    if not zitiert:
        verstoesse.append("keine Quellenangabe")
    elif zitiert - gueltig:
        verstoesse.append("unbekannte Quellennummer")
    belegt = _ziffern(frage) | {str(n) for n in gueltig}
    for f in fakten:
        belegt |= _ziffern(f"{f.get('text', '')} {f.get('quelle', '')}")
    unbelegt = _ziffern(_ZITAT.sub(" ", text)) - belegt
    if unbelegt:
        verstoesse.append("unbelegte Zahl")
    return verstoesse


# ---------------------------------------------------------------------------
# Übersetzung in weitere Sprachen (nur KI-Modus)
# ---------------------------------------------------------------------------

_UEBERSETZ_TIMEOUT_S = 60.0
_UEBERSETZ_BLOCK = 40  # Texte je Modellaufruf; Blöcke laufen parallel
_PLATZHALTER = re.compile(r"⟦T?\d+⟧")  # ⟦n⟧ Zitat, ⟦Tn⟧ fester Begriff des Aufrufers (z. B. Leistungstitel)
_ZITAT_PLATZ = re.compile(r"⟦(\d+)⟧")
# Wörtliche Zitate bleiben im Original: „…“, “…”, »…«
_ZITAT_TEXT = re.compile(r"„[^“”\n]*[“”]|“[^”\n]*”|»[^«\n]*«")
_cache: dict[str, dict[str, str]] = {}  # Sprache → {englischer Text (mit Platzhaltern): Übersetzung}
_cache_sperre = threading.Lock()


def _uebersetz_system(sprache: str) -> str:
    return (
        "Du übersetzt Texte eines Wegweisers durch die österreichische Sozialversicherung aus dem Englischen ins "
        f"{_SPRACHNAMEN[sprache]}. Antworte nur mit einem JSON-Objekt {{\"texte\": [...]}} mit genau so vielen "
        "Einträgen in derselben Reihenfolge wie die Eingabe.\n"
        "Regeln:\n"
        "- Platzhalter wie ⟦0⟧, ⟦T0⟧ oder {n} und Quellenmarken wie [1] unverändert und vollständig übernehmen.\n"
        "- Alle Zahlen, Daten, Uhrzeiten, Beträge, Paragraphen und Telefonnummern unverändert mit den Ziffern 0–9 "
        "schreiben. Keine Zahlen hinzufügen (z. B. „around the clock“ nicht als „24 Stunden“).\n"
        "- Namen von Einrichtungen, Gesetzen, Formularen und Abkürzungen (z. B. ÖGK, PVA, SVS, BVAEB, FSW, ASVG, "
        "e-card, PAL 080) nicht übersetzen.\n"
        "- Einfache, höfliche Sprache. Nichts hinzufügen, nichts weglassen, keine medizinische Bewertung.\n"
        "- Leere Texte bleiben leer. Nur Text, kein Markdown."
    )


def _cache_datei(sprache: str) -> Path:
    return config.CACHE_DIR / "uebersetzungen" / f"{sprache}.json"


def _cache_fuer(sprache: str) -> dict[str, str]:
    """Übersetzungen einer Sprache aus dem Speicher, beim ersten Zugriff aus `CACHE_DIR` (unter der Sperre)."""
    if sprache not in _cache:
        try:
            daten = json.loads(_cache_datei(sprache).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            daten = {}
        _cache[sprache] = {k: v for k, v in daten.items() if isinstance(k, str) and isinstance(v, str)} \
            if isinstance(daten, dict) else {}
    return _cache[sprache]


def _cache_schreiben(sprache: str, eintraege: dict[str, str]) -> None:
    pfad = _cache_datei(sprache)
    try:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        tmp = pfad.with_suffix(".tmp")
        tmp.write_text(json.dumps(eintraege, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(tmp, pfad)
    except OSError as e:
        log.warning("Übersetzungs-Cache nicht geschrieben (%s).", type(e).__name__)


def _schuetze(text: str) -> tuple[str, list[str]]:
    """Zitate durch ⟦n⟧ ersetzen, damit sie wörtlich im Original bleiben."""
    zitate: list[str] = []

    def ersetze(m: re.Match) -> str:
        zitate.append(m.group(0))
        return f"⟦{len(zitate) - 1}⟧"

    return _ZITAT_TEXT.sub(ersetze, text), zitate


def _stelle_her(text: str, zitate: list[str]) -> str:
    return _ZITAT_PLATZ.sub(lambda m: zitate[int(m.group(1))], text)


def pruefe_uebersetzung(quelle: str, ziel: str) -> bool:
    """Gleiche Platzhalter (⟦n⟧, {name}), gleiche Quellenmarken [n] und genau dieselben Zahlen (Ziffern 0–9)."""
    if bool(quelle.strip()) != bool(ziel.strip()):
        return False
    if sorted(_PLATZHALTER.findall(quelle)) != sorted(_PLATZHALTER.findall(ziel)):
        return False
    if set(_ZITAT.findall(quelle)) != set(_ZITAT.findall(ziel)):
        return False
    if set(re.findall(r"\{\w+\}", quelle)) != set(re.findall(r"\{\w+\}", ziel)):
        return False
    rest_q = _ZITAT.sub(" ", _PLATZHALTER.sub(" ", quelle))
    rest_z = _ZITAT.sub(" ", _PLATZHALTER.sub(" ", ziel))
    # Gleichheit der Ziffernfolgen schließt auch fremde Ziffernzeichen (z. B. ٣) aus
    return _ziffern(rest_q) == _ziffern(rest_z)


def _uebersetze_block(texte: list[str], sprache: str) -> list[str | None]:
    roh = _chat(_uebersetz_system(sprache), json.dumps({"texte": texte}, ensure_ascii=False),
                max(1000, 120 * len(texte) + sum(len(t) for t in texte)), json_modus=True,
                timeout=_UEBERSETZ_TIMEOUT_S)
    try:
        liste = json.loads(roh).get("texte") if roh else None
    except (ValueError, AttributeError):
        liste = None
    if not isinstance(liste, list) or len(liste) != len(texte):
        return [None] * len(texte)
    return [z if isinstance(z, str) and pruefe_uebersetzung(q, z) else None for q, z in zip(texte, liste)]


def uebersetze(texte: list[str], sprache: str) -> list[str | None]:
    """Englische Texte → weitere Sprache (models.WEITERE_SPRACHEN). Je Text die Übersetzung oder None, wenn das
    Modell fehlt, ausfällt oder die Prüfung (Zitate, [n], Zahlen) scheitert. Ergebnisse werden im Speicher und
    unter `CACHE_DIR/uebersetzungen/` zwischengespeichert; nur Unbekanntes geht ans Modell."""
    if sprache not in WEITERE_SPRACHEN:
        raise ValueError(f"Keine weitere Sprache: {sprache}")
    geschuetzt = [_schuetze(t) for t in texte]
    with _cache_sperre:
        cache = dict(_cache_fuer(sprache))
    offen = list(dict.fromkeys(g for g, _ in geschuetzt if g.strip() and g not in cache))
    if offen and aktiv():
        neu: dict[str, str] = {}
        for _ in range(2):  # zweiter Durchgang nur für Texte, deren Übersetzung die Prüfung nicht bestand
            bloecke = [offen[i:i + _UEBERSETZ_BLOCK] for i in range(0, len(offen), _UEBERSETZ_BLOCK)]
            with ThreadPoolExecutor(max_workers=min(4, len(bloecke))) as pool:
                ergebnisse = list(pool.map(lambda b: _uebersetze_block(b, sprache), bloecke))
            neu.update({q: z for b, e in zip(bloecke, ergebnisse) for q, z in zip(b, e) if z is not None})
            offen = [q for q in offen if q not in neu]
            if not offen or not neu:  # alles da – oder das Modell liefert gar nichts (dann kein zweiter Versuch)
                break
        if neu:
            with _cache_sperre:
                gesamt = _cache_fuer(sprache)
                gesamt.update(neu)
                _cache_schreiben(sprache, gesamt)
            cache.update(neu)
        if offen:
            log.info("%d von %d Texten nicht übersetzt (Prüfung nicht bestanden).", len(offen), len(neu) + len(offen))
    ergebnis: list[str | None] = []
    for (g, zitate), original in zip(geschuetzt, texte):
        if not g.strip():
            ergebnis.append(original)
        elif g in cache:
            ergebnis.append(_stelle_her(cache[g], zitate))
        else:
            ergebnis.append(None)
    return ergebnis
