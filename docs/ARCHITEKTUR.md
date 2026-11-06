# Architektur und Methodik

## Grundsatz

Der Lotse sagt nichts ohne Beleg. Jede fachliche Aussage stammt aus einer lokalen Quelle der SV-Box: einem Rechtstext, einer Seite im ÖGK-Serviceratgeber 2026, einem Formular, einer Honorarordnung, dem Erstattungskodex oder einem hochgeladenen Dokument. Angezeigt werden dazu Fundstelle und Rechtsstand. Wo eine lokale Quelle fehlt, etwa bei Landesangeboten oder Arztsuchen, nutzt der Lotse offizielle Websites aus der Quellenliste des Use Case. Diese sind als „extern – nicht lokal geprüft“ markiert und mit Abrufdatum versehen.

Der Kern arbeitet deterministisch und läuft offline. Ein Sprachmodell (Azure Foundry, `gpt-5.4-mini`) ist optional. Es übernimmt fünf Aufgaben:

- Freitext zuordnen, auch Dialekt und andere Sprachen, und dabei Lebenslagen von Sachfragen unterscheiden,
- als zweite Stufe der Grenzprüfung medizinische Beurteilungsfragen erkennen,
- belegte Wissensantworten formulieren,
- Fotos wörtlich abschreiben,
- übersetzen.

Jede Modellausgabe wird geprüft. Fällt das Modell aus, läuft der Lotse regelbasiert weiter.

## Datenfluss

```
Nachricht / Dokument / Foto
   │
   ▼
grenzen.pruefe_anfrage  (+ im KI-Modus llm.grenzkategorie) ── blockiert ──► Erklärung, Verweis an Ärztin/Arzt bzw. 1450,
   │ erlaubt                                                                 administrative Alternative
   ▼
lotse.Lotse
   ├─ Statusfrage? → Antwort aus der Fallakte („Was ist noch offen?“)
   ├─ offene Rückfrage? → Antwort in Slot übernehmen (slots.SLOTS, Validierung, Ort → Bundesland)
   ├─ Terminwunsch? → Anlass → Nähe → Tageszeit → katalog.termin_info → Terminauftrag, Anfragetext, .ics
   ├─ katalog.erkenne_szenarien / passende_leistungen / vorsorge_hinweise → Leistungsbündel (3 wichtigste zuerst)
   ├─ dokument.empfehlungen / stammdaten / impfeintraege / medikamente → Zitate, Vorbefüllung, Impfungen, Erstattungsstatus
   ├─ wissen.relevante / pflegegeld / ekodex → Belege für Sach- und Rechtsfragen (Relevanzschwellen + Fachwortschatz)
   └─ formulare.ausfuellen → vorausgefülltes Originalformular (AcroForm), nur wo es regional gilt
   │
   ▼
fallakte → Schritte je Leistung und Termin, Status, nächster Schritt, Übersicht
speicher → JSON unter .cache/sitzungen (ohne sensible Angaben und ohne Freitext), Export/Import
   │
   ▼
Antwort (Text, eine Rückfrage, Bündel, Termine, Impfungen, Medikamente, Quellen, Grenze, Fallakte, Modus, Sprache)
   → optional llm.uebersetze → Web-UI
```

## Module

| Modul | Aufgabe |
|---|---|
| `lotse/recht.py`, `lotse/pdfquellen.py`, `lotse/suche.py`, `lotse/wissen.py` | Liest die 14.244 XML-Rechtstexte und die PDF-Seiten von Serviceratgeber, Honorarordnungen und Formularen ein und baut einen BM25-Index (rund 30.000 Abschnitte). Liefert Quellen mit BGBl.-Fundstelle und Inkrafttreten bzw. PDF-Seite. `relevante()` lässt nur Treffer durch, die die Frage abdecken und mindestens einen Fachbegriff der Sozialversicherung treffen |
| `lotse/ekodex.py` | Erstattungskodex: Box und Kennzeichen laut Legende, Regel- und Indikationstexte. Gibt nur den Erstattungsstatus aus, keine Empfehlung |
| `lotse/katalog.py`, `lotse/data/leistungen.json`, `lotse/data/termine.json` | 46 kuratierte Leistungen in 5 Lebenslagen mit Stelle (je Träger), Kontakt, Nutzen, Voraussetzungen, Unterlagen, Schritten, Einrichtungen und Landesangeboten für alle 9 Bundesländer. Dazu Terminwissen je Anlass (wohin, Hinweise, Suchdienste je Bundesland). Alle Einträge sind belegt |
| `lotse/dokument.py` | Liest PDF, Text und Fotos (über `llm.transkribiere`). Erkennt ausdrücklich dokumentierte Empfehlungen (wörtlich, mit Seite, ohne Satzfragmente), administrative Stammdaten, Impfeinträge und Medikamentennamen |
| `lotse/formulare.py`, `lotse/data/formulare/` | Ordnet Slots den AcroForm-Feldern der Originalformulare zu, füllt nur den Teil für Versicherte aus, prüft Pflichtangaben |
| `lotse/grenzen.py` | Medizinische Grenze: Regeln (auch Dialekt) vor der Verarbeitung, im KI-Modus ergänzt um eine Modellprüfung; Nachkontrolle von Modellausgaben |
| `lotse/lotse.py`, `lotse/fallakte.py` | Dialogsteuerung mit minimalen Rückfragen, Terminvorbereitung, Statusfragen, Fallakte mit Status und Kalendereintrag (RFC 5545) |
| `lotse/speicher.py` | Versionierte Speicherung und Export/Import von Fällen mit strenger Prüfung beim Laden; sensible Angaben und Freitexte werden nie geschrieben |
| `lotse/llm.py` | Optionale Azure-Anbindung: `verstehe`, `grenzkategorie`, `formuliere`, `transkribiere`, `uebersetze`, jeweils mit Prüfung der Ausgabe; ohne Schlüssel inaktiv |
| `lotse/web/` | FastAPI und eine statische Oberfläche ohne Build-Schritt (barrierearm, mobil, von rechts nach links für Arabisch, Vorlesen und Spracheingabe) |

## Methodische Entscheidungen

- **Rechtsstand statt reiner Ähnlichkeitssuche.** BPGG § 5 enthält nur die Grundbeträge von 2020 (Stufe 1: 157,30 €). Die geltenden Beträge für 2026 stehen in der Anpassungsverordnung (BGBl. II Nr. 263/2025). Der Lotse löst das aktiv auf und zeigt beide Quellen.
- **BM25 statt Embeddings.** Der Index läuft lokal, ist reproduzierbar und braucht weder Netz noch Schlüssel. Bei Normtexten mit festem Fachvokabular ist die lexikalische Suche präzise. Gemessen wird mit einem festen Fragenset (20 von 20 Sollquellen in den Top 5). Gegen Fehlantworten bei themenfremden Fragen helfen Relevanzschwellen und ein Fachwortschatz. Bei Fragen zu Katalogleistungen („Unterschied zwischen Kur und Reha“) antwortet der Lotse mit den kuratierten, belegten Texten.
- **Zitieren statt interpretieren.** Aus medizinischen Dokumenten übernimmt der Lotse nur wörtliche, administrative Empfehlungen samt Seitenangabe. Diagnosen, Befundwerte und Dosierungen gibt er nicht aus. Impfeinträge werden nur abgeschrieben und nicht bewertet. Bei Medikamenten nennt er nur den Erstattungsstatus aller Einträge zum Namen, nicht eine einzelne Packung.
- **Rückfragen nur bei Entscheidungsbedarf.** Gefragt wird nur, was den nächsten konkreten Schritt verändert: die zuständige Stelle, die Antragsart, beim Termin Anlass, Nähe und Tageszeit. Persönliche Daten können die Versicherten im vorausgefüllten PDF ergänzen.
- **Weniger ist mehr.** Die 3 wichtigsten Leistungen stehen oben, die übrigen zugeklappt. Eine konkrete Frage („Wer zahlt die Fahrt zur Bestrahlung?“) bringt die passende Leistung an die erste Stelle.
- **Originalformulare.** Der Lotse füllt die echten PDF-Formulare aus und erzeugt keine Nachbauten. Den ärztlichen Teil und die Unterschrift lässt er bewusst leer. Regional gebundene Formulare (FSW) erscheinen nur, wo sie gelten.
- **Vorbereiten statt buchen.** Termine und Anträge bereitet der Lotse vor: Anfragetext, Kalendereintrag, Unterlagen. Er behauptet nie, etwas gebucht oder eingereicht zu haben.
- **Modell nur mit Netz und doppeltem Boden.** Jede Modellausgabe muss Grenzprüfung, Zitat- und Zahlenprüfung bzw. die Platzhalter- und Ziffernprüfung bei Übersetzungen bestehen. Sonst gilt die regelbasierte Antwort. Das Badge zeigt ehrlich an, ob das Modell beteiligt war.
- **Datensparsamkeit.** Gespeichert werden nur strukturierte Fallangaben. Sensible Angaben (SVNR, Geburtsdatum, Kontakt, IBAN) und Freitext landen nie auf der Platte oder im Export. Fälle verfallen nach 30 Tagen.
