# Architektur und Methodik

## Grundsatz

Der Lotse beantwortet nichts ohne Beleg. Jede fachliche Aussage stammt aus einer lokalen Quelle der SV-Box, also aus einem Rechtstext, einer Seite im ÖGK-Serviceratgeber 2026, einem Formular oder einem hochgeladenen Dokument. Sie wird mit Fundstelle und Rechtsstand angezeigt. Aussagen ohne lokalen Beleg sind als „extern – nicht lokal geprüft“ markiert.

Der Kern arbeitet deterministisch. Ein Sprachmodell (Azure Foundry, `gpt-5.4-mini`) ist optional. Es ordnet Freitext zu (auch Dialekt und andere Sprachen) und unterscheidet dabei Lebenslagen von Sachfragen. Als zweite Stufe der Grenzprüfung erkennt es medizinische Beurteilungsfragen, die die Regeln nicht kennen. Außerdem formuliert es Wissensantworten, bekommt dafür aber nur die bereits belegten Fakten, und jede Ausgabe läuft durch dieselbe Prüfung. Fällt das Modell aus, läuft die Demo regelbasiert unverändert weiter.

## Datenfluss

```
Nachricht / Dokument
   │
   ▼
grenzen.pruefe_anfrage ── blockiert ──► Erklärung + Verweis an Ärztin/Arzt (keine Weiterverarbeitung)
   │ erlaubt
   ▼
lotse.Lotse
   ├─ offene Rückfrage? → Antwort in Slot übernehmen (slots.SLOTS, Validierung)
   ├─ katalog.erkenne_szenarien → katalog.fuer_szenario(bundesland) → Leistungsbündel
   ├─ dokument.empfehlungen / stammdaten → wörtliche Zitate + Vorbefüllung
   ├─ wissen.suche / pflegegeld / ekodex → Belege für Wissensfragen
   └─ formulare.ausfuellen → vorausgefülltes Originalformular (AcroForm)
   │
   ▼
fallakte → Schritte je Leistung, Status, nächster Schritt
   │
   ▼
Antwort (Text, eine Rückfrage, Bündel, Quellen, Grenze, Fallakte, Modus) → Web-UI
```

## Module

| Modul | Aufgabe |
|---|---|
| `lotse/recht.py`, `lotse/pdfquellen.py`, `lotse/suche.py`, `lotse/wissen.py` | Liest die 14.244 XML-Rechtstexte und die PDF-Seiten von Serviceratgeber, Honorarordnungen und Formularen ein, baut einen BM25-Index (rund 30.000 Abschnitte) und liefert Quellen mit BGBl.-Fundstelle und Inkrafttreten bzw. PDF-Seite |
| `lotse/ekodex.py` | Erstattungskodex: Box und Kennzeichen laut Legende, Regel- und Indikationstexte. Gibt nur den Erstattungsstatus aus, keine Empfehlung |
| `lotse/katalog.py`, `lotse/data/leistungen.json` | Kuratierte Leistungen für die vier Szenarien mit Stelle, Voraussetzungen, Unterlagen, Schritten und Belegen |
| `lotse/dokument.py` | Erkennt ausdrücklich dokumentierte Empfehlungen (wörtlich, mit Seite) und administrative Stammdaten |
| `lotse/formulare.py`, `lotse/data/formulare/` | Ordnet Slots den AcroForm-Feldern der Originalformulare zu, füllt nur den Teil für Versicherte aus, prüft Pflichtangaben |
| `lotse/grenzen.py` | Medizinische Grenze: Regeln vor der Verarbeitung, im KI-Modus ergänzt um eine Modellprüfung (Stufe 2); Nachkontrolle von Modellausgaben |
| `lotse/lotse.py`, `lotse/fallakte.py` | Dialogsteuerung mit minimalen Rückfragen, Fallakte mit Status |
| `lotse/llm.py` | Optionale Azure-Anbindung: `verstehe` (Szenario/Slots, Lebenslage vs. Sachfrage), `grenzkategorie` (Grenzprüfung Stufe 2), `formuliere` (belegte Wissensantwort); ohne Schlüssel inaktiv |
| `lotse/web/` | FastAPI und eine statische Oberfläche ohne Build-Schritt |

## Methodische Entscheidungen

- **Rechtsstand statt reiner Ähnlichkeitssuche.** BPGG § 5 enthält nur die Grundbeträge von 2020 (Stufe 1: 157,30 €). Die geltenden Beträge für 2026 stehen in der Anpassungsverordnung (BGBl. II Nr. 263/2025). Der Lotse löst das aktiv auf und zeigt beide Quellen. Eine reine Ähnlichkeitssuche würde die veralteten Beträge liefern.
- **BM25 statt Embeddings.** Der Index läuft lokal, ist reproduzierbar und braucht weder Netz noch Schlüssel. Bei Normtexten mit festem Fachvokabular ist die lexikalische Suche für Gesetzesbegriffe präzise. Die Trefferquote wird mit einem festen Fragenset gemessen (`tests/test_wissen.py`).
- **Zitieren statt interpretieren.** Aus medizinischen Dokumenten übernimmt der Lotse nur wörtliche, administrative Empfehlungen samt Seitenangabe. Diagnosen, Medikation und Befundwerte werden nicht ausgegeben.
- **Rückfragen nur bei Entscheidungsbedarf.** Gefragt wird nur, was den nächsten konkreten Schritt verändert, etwa die zuständige Stelle oder die Antragsart. Persönliche Daten können die Versicherten im vorausgefüllten PDF ergänzen.
- **Originalformulare.** Der Lotse füllt die echten PDF-Formulare aus und erzeugt keine Nachbauten. Den ärztlichen Teil und die Unterschrift lässt er bewusst leer.
