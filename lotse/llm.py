"""Optionale Sprachmodell-Anbindung (Azure Foundry, OpenAI-kompatible Chat Completions).

Aktiv nur mit `AZURE_API_KEY` und `AZURE_OPENAI_ENDPOINT`. Jede Ausgabe wird geprüft
(`grenzen.pruefe_antwort`, Zitate, Zahlen); bei Verstoß, Fehler oder Timeout liefern die
Funktionen ein leeres Ergebnis und der Aufrufer nutzt den regelbasierten Text.
"""

from __future__ import annotations

import json
import logging
import re

import openai

from lotse import config, grenzen
from lotse.slots import SLOTS

log = logging.getLogger(__name__)

SZENARIEN = ("pflege", "gesundheit", "entlassung", "kind")
TIMEOUT_S = 20.0

# Slots, die das Modell aus freiem Text erkennen darf (keine sensiblen, keine medizinischen).
_VERSTEHE_SLOTS = (
    "anliegen.fuer_wen", "person.bundesland", "versicherung.krankenversicherung",
    "versicherung.pension", "pflege.antragsart", "pflege.stufe", "kind.alter",
)

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


def _chat(system: str, nutzer: str, max_tokens: int, json_modus: bool = False) -> str:
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
            timeout=TIMEOUT_S,
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
        "Du ordnest Anliegen von Versicherten der österreichischen Sozialversicherung zu. "
        "Antworte nur mit einem JSON-Objekt {\"art\": \"situation\"|\"frage\", \"szenarien\": [...], \"slots\": {...}}.\n"
        "art: \"situation\", wenn die Person ihre Lage schildert oder fragt, welche Angebote, Leistungen oder "
        "Schritte für ihre Lage in Frage kommen (z. B. \"Meine Mutter kommt allein nicht mehr zurecht\", "
        "\"Bin aus dem Spital entlassen worden\", \"Ich habe ein Kind, welche Angebote gibt es?\"); "
        "\"frage\", wenn sie eine konkrete Sachfrage zu einer bestimmten Leistung, einem Gesetz, einem Betrag, "
        "einer Frist oder einem Ablauf stellt (z. B. \"Was regelt das ASVG zur Rezeptgebühr?\", "
        "\"Wie lange gibt es Krankengeld?\"). Bei \"frage\" bleibt \"szenarien\" leer.\n"
        "Szenarien (nur diese IDs, sortiert nach Relevanz, leer wenn keines passt):\n"
        "- \"pflege\": Pflege oder Betreuung einer Person, Pflegegeld, Pflege zu Hause\n"
        "- \"gesundheit\": Gesundheitsförderung, Vorsorge, Bewegung, Ernährung\n"
        "- \"entlassung\": nach einem Spitalsaufenthalt, Entlassungsbrief, Befund erhalten\n"
        "- \"kind\": Angebote für Kinder, Schwangerschaft, Familie\n"
        "Slots (nur diese IDs, nur wenn der Text sie ausdrücklich nennt, Werte exakt wie angegeben):\n"
        + "\n".join(slots)
        + "\nBewerte oder deute keine medizinischen Inhalte."
    )


def verstehe(text: str, sprache: str) -> dict:
    """Szenarien und Slots aus freiem Text; unbekannte IDs und ungültige Werte werden verworfen."""
    ergebnis: dict = {"szenarien": [], "slots": {}}
    roh = _chat(_verstehe_system(), f"Sprache: {sprache}\nText: {text}", 600, json_modus=True)
    if not roh or grenzen.pruefe_antwort(roh):
        return ergebnis
    try:
        daten = json.loads(roh)
    except ValueError:
        return ergebnis
    if not isinstance(daten, dict):
        return ergebnis
    szenarien = daten.get("szenarien")
    # Sachfragen beantwortet die Wissensschicht; nur geschilderte Lebenslagen eröffnen ein Szenario
    if isinstance(szenarien, list) and daten.get("art") != "frage":
        for sz in szenarien:
            if isinstance(sz, str) and sz in SZENARIEN and sz not in ergebnis["szenarien"]:
                ergebnis["szenarien"].append(sz)
    slots = daten.get("slots")
    if isinstance(slots, dict):
        for sid, wert in slots.items():
            if sid in _VERSTEHE_SLOTS and isinstance(wert, str) and SLOTS[sid].gueltig(wert):
                ergebnis["slots"][sid] = wert.strip()
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
