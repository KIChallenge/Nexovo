# Nexovo – SV KI-Lotse (KI Challenge 2026, Use Case 1)

Persönlicher Lotse für Versicherte durch die Leistungen des österreichischen Gesundheits- und Sozialversicherungssystems. Er hilft von der ersten Frage bis zum vorausgefüllten Antrag.

Man beschreibt seine Situation in eigenen Worten („Meine Mutter kommt allein nicht mehr zurecht“) oder lädt einen Entlassungsbrief hoch. Der Lotse zeigt dann:

- **passende Leistungen** innerhalb und außerhalb der Sozialversicherung (39 kuratierte Leistungen für Pflege, Gesundheitsförderung, Entlassung und Kind),
- die **zuständige Stelle**, aufgelöst nach den eigenen Angaben (z. B. Pflegegeld → Pensionsträger laut BPGG § 22),
- das **vorausgefüllte Originalformular** (PAL080 Pflegegeld, KUR1 Reha, ÖGK-Fahrtkosten, FSW-Förderung u. a.),
- **Unterlagen-Checkliste, Schritte mit Status und den nächsten Schritt** in einer Fallakte,
- **zu jeder Aussage die Quelle**: Rechtsnorm mit BGBl.-Fundstelle und Inkrafttreten, Seite im ÖGK-Serviceratgeber 2026, Formularseite oder wörtliches Zitat aus dem hochgeladenen Dokument.

Er fragt nur nach, was den nächsten Schritt verändert: im Pflegefall 4 Fragen bis zum Antrag. Er spricht Deutsch oder Englisch, auf Wunsch einfach oder ausführlich.

**Medizinische Grenze:** Der Lotse stellt keine Diagnosen, deutet keine Befunde, bewertet keine Risiken und empfiehlt keine Therapien, Medikamente oder Dosierungen. Aus medizinischen Dokumenten übernimmt er nur ausdrücklich dokumentierte Empfehlungen, wörtlich und mit Seitenangabe. Medizinische Fragen lehnt er mit Begründung ab und verweist an Ärztin oder Arzt bzw. an 1450. Stattdessen bietet er den administrativen Weg an.

## Schnellstart

Voraussetzung: Python 3 (entwickelt und getestet mit Python 3.14).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m lotse              # http://127.0.0.1:8000
```

Port ändern: `LOTSE_PORT=8080 .venv/bin/python -m lotse`.

In der Oberfläche starten die vier Beispielknöpfe (Pflege, Gesundheit, Nach dem Spital, Kind) je einen neuen Fall. Der Knopf „Synthetischer Entlassungsbrief“ zeigt die Dokumentfunktion auch ohne SV-Box-Daten.

## Daten

Die Quelldaten stammen aus der SV-Box der Veranstalter und liegen **nicht** im Repository: Rechtstexte der SozDok (14.244 XML), Erstattungskodex, Leistungskataloge, Formulare und Befunde. Standardmäßig werden sie im Projektwurzelverzeichnis erwartet, ein anderer Ort lässt sich mit `LOTSE_DATA_DIR` setzen:

```
Rechtstexte/  Anträge und Formulare/  Medikamenten Erstattungskodex/  Befunde/  Leistungskataloge/
```

Beim ersten Start mit Daten baut der Lotse den Suchindex auf (etwa 8 s). Danach lädt er ihn aus `.cache/` (unter 1 s).

Ohne Daten laufen Katalog, Grenzprüfung, Dialog und der synthetische Entlassungsbrief weiter. Rechtssuche, Pflegegeldbeträge, Erstattungskodex, Formular-PDFs und der SV-Box-Befund brauchen die Daten. Fehlen sie, sagt der Lotse das, statt abzubrechen.

## Konfiguration

| Variable | Zweck |
|---|---|
| `LOTSE_DATA_DIR` | Ort der SV-Box-Daten (Standard: Projektwurzel) |
| `LOTSE_CACHE_DIR` | Ort des Index-Caches (Standard: `.cache/`) |
| `LOTSE_PORT` | Port der Oberfläche (Standard: 8000) |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_API_KEY`, `AZURE_OPENAI_MODEL` | Optionaler KI-Modus (Standard-Modell `gpt-5-4-mini`) |

Vorlage: `.env.example` nach `.env` kopieren. `.env` wird nicht eingecheckt. Ohne Schlüssel läuft der Lotse im **regelbasierten Modus**, das Badge oben rechts zeigt den Modus an. Mit Schlüssel formuliert das Modell Antworten auf Wissensfragen und hilft beim Verstehen von Freitext. Es arbeitet dabei nur mit den belegten Fakten, und jede Ausgabe wird auf Grenzverstöße, gültige Zitate und unbelegte Zahlen geprüft. Bei einem Verstoß, Fehler oder Timeout kommt die regelbasierte Antwort.

## Tests

```bash
.venv/bin/python -m pytest -q
```

Mit SV-Box-Daten bestehen alle 310 Tests. Ohne Daten bestehen 230; die 80 datenabhängigen Tests (Marker `daten`) werden übersprungen.

| Anforderung (Plan) | Nachweis |
|---|---|
| Alle 4 Bewertungsszenarien: je ≥ 3 Leistungen mit Quelle und Stelle | `tests/test_lotse.py`, `tests/test_katalog.py` |
| Pflegefall: Antrag nach ≤ 5 Rückfragen | `tests/test_lotse.py` (tatsächlich 4) |
| Rechtsquellen: Sollquelle in den Top 5 | `tests/test_wissen.py`: 20 von 20 Fragen |
| Pflegegeld 2026 nach geltendem Recht (Stufe 3: 592,60 €, nicht 451,80 €) | `tests/test_wissen.py`, `tests/test_lotse.py` |
| Entlassungsbrief: dokumentierte Empfehlungen wörtlich mit Seite, keine Diagnosen | `tests/test_dokument.py` |
| Formulare: korrekte Felder, Unterschrift und ärztlicher Teil bleiben leer | `tests/test_formulare.py` |
| Medizinische Grenze: Ablehnung ohne Fehlalarm bei Verwaltungsfragen | `tests/test_grenzen.py` |
| Zitate im Katalog stehen wörtlich auf der genannten Seite | `tests/test_katalog.py` |
| Erstattungskodex: Box und Kennzeichen laut Legende, keine Empfehlung | `tests/test_ekodex.py` |
| Web-Ablauf Sitzung → Nachricht → Upload → PDF | `tests/test_web.py` |

## Aufbau

```
lotse/
  wissen.py  recht.py  suche.py  pdfquellen.py  ekodex.py   Wissensschicht (Recht, PDFs, Erstattungskodex, BM25)
  katalog.py  data/leistungen.json                          Leistungskatalog mit Belegen
  formulare.py  data/formulare/*.json                       Formular-Registry und AcroForm-Füllung
  dokument.py                                               Dokumentfunktion (Empfehlungen, Stammdaten)
  grenzen.py                                                Medizinische Grenze (Anfrage und Ausgabe)
  lotse.py  fallakte.py  texte.py  llm.py                   Dialog, Fallakte, Texte DE/EN, optionales LLM
  slots.py  models.py  config.py                            Gemeinsame Typen und Konfiguration
  web/app.py  web/static/                                   FastAPI und Oberfläche (ohne Build-Schritt)
examples/entlassungsbrief_synthetisch.txt                   Fiktiver Entlassungsbrief für die Demo
docs/ARCHITEKTUR.md                                         Architektur und methodische Entscheidungen
Analyse/                                                    Plan und Gegenprüfung gegen die Originalquellen
```

Mehr zu Methodik und Entscheidungen in [`docs/ARCHITEKTUR.md`](docs/ARCHITEKTUR.md).

## Bekannte Einschränkungen und offene Punkte

- **KI-Modus nicht live getestet:** Bei der Entwicklung stand kein API-Schlüssel zur Verfügung. Die Anbindung ist nach dem SDK geschrieben, die Ausgabeprüfung ist getestet.
- **Kein Foto-Upload und keine Spracheingabe:** Eingelesen werden PDF und Text, Bilder werden nicht per OCR erkannt.
- **Termine:** Der Lotse nennt Kontakt und Terminvereinbarung laut Quelle (z. B. PVA-Landesstelle), bucht aber nicht selbst.
- **Regionale Abdeckung:** Die regionalen Angebote stammen aus den lokalen Quellen und betreffen Wien (FSW). Das Fahrtkostenformular ist das der ÖGK Wien. Bei SVS und BVAEB ist die Zuständigkeit für Kassenleistungen als „lokal nicht geprüft“ markiert.
- **Zitate in englischen Antworten** bleiben im deutschen Original, damit der Beleg wörtlich bleibt.
- **Suche:** Die Suche ist lexikalisch (BM25, ohne Embeddings). Allgemeine Sätze erkennt die Szenarioerkennung des Katalogs, nicht die Suche.
- **Erstattungskodex:** Die Kennzeichen DSX, KNP und ADL erklärt die lokale Legende nicht. Der Lotse sagt das so, ohne eigene Deutung.
- **Sitzungen** liegen nur im Arbeitsspeicher und sind nach einem Neustart weg.
- **Gewichtung der Finaljury-Kriterien:** in den Unterlagen nicht angegeben (siehe `Analyse/Plan_1_Platz.md`, Abschnitt 9).
