# Nexovo – SV KI-Lotse (KI Challenge 2026, Use Case 1)

Ein persönlicher Lotse für Versicherte und Angehörige durch die Leistungen des österreichischen Gesundheits- und Sozialversicherungssystems. Er begleitet von der ersten Frage bis zum vorausgefüllten Antrag, und jede Aussage hat eine Quelle.

Man beschreibt seine Situation in eigenen Worten („Mama schafft's daheim nimma allein“) oder lädt einen Entlassungsbrief hoch, als PDF, Text oder Foto. Der Lotse zeigt dann:

- **passende Leistungen** innerhalb und außerhalb der Sozialversicherung: 46 kuratierte Leistungen in 5 Lebenslagen (Pflege, Gesundheitsförderung, nach dem Spital, Kind, soziale und finanzielle Unterstützung). Die 3 wichtigsten stehen oben, jeweils mit einer Erklärung, warum sie helfen,
- die **zuständige Stelle**, aufgelöst nach den eigenen Angaben (z. B. Pflegegeld → Pensionsträger laut BPGG § 22; Reha bei SVS → SVS mit Kontakt), dazu **Angebote im eigenen Bundesland** (alle 9 Länder) und **Einrichtungen bzw. Suchdienste**,
- das **vorausgefüllte Originalformular** (PAL080 Pflegegeld, KUR1 Reha, ÖGK-Fahrtkosten, FSW-Förderung u. a.); Unterschrift und ärztlicher Teil bleiben frei,
- eine **Terminvorbereitung** wie im Use Case („Ich möchte einen Arzttermin“ → Anlass, Nähe, Tageszeit): wohin, was mitnehmen, Arztsuche im Bundesland, ein fertiger Text für die Anfrage und nach der Vereinbarung ein Kalendereintrag (.ics),
- eine **Fallakte** mit Unterlagen-Checkliste, Schritten, Status und nächstem Schritt; „Was ist noch offen?“ beantwortet der Lotse aus der Fallakte. Fälle lassen sich speichern und später wieder laden,
- aus Dokumenten: **ausdrücklich dokumentierte Empfehlungen** (wörtlich, mit Seite), administrative Stammdaten für das Formular, **dokumentierte Impfungen** (nur abgeschrieben) und den **Erstattungsstatus** der genannten Medikamente laut Erstattungskodex,
- **zu jeder Aussage die Quelle**: Rechtsnorm mit BGBl.-Fundstelle und Inkrafttreten, Seite im ÖGK-Serviceratgeber 2026, Formular- oder Honorarordnungsseite, wörtliches Zitat aus dem Dokument oder eine externe Seite, die als „extern – nicht lokal geprüft“ markiert ist.

Er fragt nur nach, was den nächsten Schritt verändert; im Pflegefall sind es 4 Fragen bis zum Antrag. Er versteht Dialekt und spricht Deutsch und Englisch, im KI-Modus zusätzlich Türkisch, Bosnisch/Kroatisch/Serbisch, Ukrainisch und Arabisch (von rechts nach links). Auf Wunsch antwortet er einfach oder ausführlich. Antworten lassen sich vorlesen; in Browsern mit Web-Speech-Unterstützung gibt es auch Spracheingabe.

**Medizinische Grenze:** Der Lotse stellt keine Diagnosen, deutet keine Befunde, bewertet keine Risiken und empfiehlt keine Therapien, Medikamente oder Dosierungen. Medizinische Fragen lehnt er mit Begründung ab, auch im Dialekt („Is des wos Schlimmes?“), verweist an Ärztin oder Arzt bzw. an 1450 und bietet stattdessen den administrativen Weg an.

## Schnellstart

Voraussetzung: Python 3.12 oder neuer (getestet mit 3.12 und 3.14).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m lotse              # http://127.0.0.1:8000
```

Port ändern: `LOTSE_PORT=8080 .venv/bin/python -m lotse`.

Mit Container (Docker oder Podman):

```bash
docker build -t nexovo-lotse .
docker run --rm -p 8000:8000 nexovo-lotse                     # regelbasiert
docker run --rm -p 8000:8000 --env-file .env nexovo-lotse     # mit KI-Modus
```

In der Oberfläche starten die Beispielknöpfe (Pflege, Gesundheit, Nach dem Spital, Kind, Unterstützung, Arzttermin) je einen neuen Fall. Die Demo-Dokumente sind fiktiv: Entlassungsbrief als Text, als Foto (nur im KI-Modus) und ein Impfpass.

Folien und Demo-Video für die Jury liegen in `docs/praesentation/` (`index.html` im Browser öffnen, Pfeiltasten; PDF-Fassung und `demo.mp4` daneben).

## Daten

Die Quelldaten stammen aus der SV-Box der Veranstalter. Sie sind laut Teilnahmeinformation (S. 2) „öffentlich verfügbar“ und dürfen „frei verteilt werden“. Was der Prototyp zur Ausführung braucht, liegt deshalb im Repository:

```
Rechtstexte/                     14.244 XML der SozDok
Anträge und Formulare/           7 Original-PDF-Formulare
Medikamenten Erstattungskodex/   Erstattungskodex (TXT) und Zeichenerklärung (PDF)
Leistungskataloge/               ÖGK-Serviceratgeber 2026, Honorarordnungen
```

**Nicht** im Repository liegen:
- `Befunde/`: Die SV-Box-Befunde sind laut Dokument bzw. Name („Testpatient“) fiktiv. Wir haben sie trotzdem aus Vorsicht nicht veröffentlicht.
- das Use-Case-Dokument, weil es den SV-Box-Zugang enthält,
- das API-Beispiel, weil es den internen Endpoint enthält.

Wer die Befunde hat, legt sie als `Befunde/` in die Projektwurzel; dann erscheint zusätzlich der Demo-Knopf „Entlassungsbefund (SV-Box)“. Liegen die Daten woanders, setzt man `LOTSE_DATA_DIR`.

Beim ersten Start baut der Lotse den Suchindex auf (etwa 8 s), danach lädt er ihn aus `.cache/` (unter 1 s). Im Container ist der Index schon eingebaut.

Fehlen die Daten ganz, laufen Katalog, Grenzprüfung, Dialog, Termine und der synthetische Brief trotzdem. Bei Rechtsfragen, Pflegegeldbeträgen, Erstattungskodex und Formular-PDFs sagt der Lotse dann, dass die Quellen fehlen, statt abzubrechen.

## Konfiguration

| Variable | Zweck |
|---|---|
| `LOTSE_DATA_DIR` | Ort der SV-Box-Daten (Standard: Projektwurzel) |
| `LOTSE_CACHE_DIR` | Ort von Suchindex, gespeicherten Fällen und Übersetzungen (Standard: `.cache/`) |
| `LOTSE_PORT` | Port der Oberfläche (Standard: 8000) |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_API_KEY`, `AZURE_OPENAI_MODEL` | Optionaler KI-Modus (Standard-Modell `gpt-5-4-mini`) |

Vorlage: `.env.example` nach `.env` kopieren; `.env` wird nicht eingecheckt. Ohne Schlüssel läuft der Lotse im **regelbasierten Modus**. Das Badge oben rechts zeigt „KI“ nur, wenn eine Antwort tatsächlich mit dem Modell entstanden ist. Mit Schlüssel (live getestet mit `gpt-5.4-mini` auf Azure Foundry) übernimmt das Modell diese Aufgaben:

1. **Verstehen:** Freitext, Dialekt und andere Sprachen werden einer Lebenslage zugeordnet. Sachfragen („Was regelt das ASVG zur Rezeptgebühr?“) gehen an die Wissensschicht.
2. **Grenzprüfung, zweite Stufe:** Was die Regeln durchlassen, prüft das Modell noch einmal auf medizinische Beurteilung. Im Testset gab es 0 Fehlalarme bei 52 Verwaltungsfragen, und alle 46 medizinischen Fragen wurden erkannt.
3. **Formulieren:** Wissensantworten entstehen nur aus den abgerufenen, nummerierten Belegen. Jede Ausgabe wird auf Grenzverstöße, gültige Zitate und unbelegte Zahlen geprüft.
4. **Fotos lesen:** wörtliche Abschrift von Fotos und Scans; danach dieselben Regeln wie für Text.
5. **Übersetzen** in die weiteren Sprachen. Zitate, Zahlen und Quellennummern bleiben unverändert, das wird geprüft.

Bei einem Verstoß, Fehler oder Timeout greift die regelbasierte Antwort. Pro Nachricht kostet der KI-Modus etwa 0,5–3 s.

## Datenschutz

- Nur synthetische bzw. fiktive Demo-Daten. Keine Schlüssel im Repository.
- Gespeicherte Fälle liegen lokal unter `.cache/sitzungen/` und werden nach 30 Tagen gelöscht. Sensible Angaben (SVNR, Geburtsdatum, Telefon, E-Mail, IBAN) werden weder gespeichert noch exportiert; nach einem Neustart oder Import fehlen sie im Formularentwurf wieder.
- Im KI-Modus gehen Nachrichtentexte, Fotos und zu übersetzende Antworttexte an den konfigurierten Azure-Endpoint.

## Tests

```bash
.venv/bin/python -m pytest -q
```

Nach dem Klonen bestehen 606 Tests, 19 werden übersprungen: Sie brauchen `Befunde/` (Marker `befunde`). Mit `Befunde/` bestehen alle 625. Ganz ohne SV-Box-Daten bestehen 527, 98 werden übersprungen (Marker `daten`). Die Tests laufen ohne Netz und ohne Modell.

| Anforderung | Nachweis |
|---|---|
| 5 Lebenslagen: je ≥ 5 belegte Leistungen mit Stelle; Regionen für 9 Bundesländer | `tests/test_katalog.py` |
| Pflegefall: Antrag nach ≤ 5 Rückfragen; passende Leistung zuerst (z. B. Fahrtkosten) | `tests/test_lotse.py` |
| Termin: Rückfragen, Anfragetext, Kalendereintrag (RFC 5545), Status | `tests/test_lotse.py`, `tests/test_web.py` |
| Rechtsquellen: Sollquelle in den Top 5; themenfremde Fragen ohne Zitat | `tests/test_wissen.py` (20 von 20), `tests/test_lotse.py` |
| Pflegegeld 2026 nach geltendem Recht (Stufe 3: 592,60 €, nicht 451,80 €) | `tests/test_wissen.py`, `tests/test_lotse.py` |
| Dokumente: Empfehlungen wörtlich mit Seite, ohne Satzfragmente; Impfungen, Medikamente, Fotos | `tests/test_dokument.py` |
| Formulare: korrekte Felder, Unterschrift und ärztlicher Teil leer; regionale Gültigkeit | `tests/test_formulare.py`, `tests/test_lotse.py` |
| Medizinische Grenze inkl. Dialekt, ohne Fehlalarm bei Verwaltungsfragen | `tests/test_grenzen.py` |
| Zitate im Katalog und in `termine.json` stehen wörtlich auf der genannten Seite | `tests/test_katalog.py` |
| Erstattungskodex: Box und Kennzeichen laut Legende, keine Empfehlung | `tests/test_ekodex.py`, `tests/test_lotse.py` |
| Speichern, Laden, Neustart, Export/Import mit Prüfung | `tests/test_speicher.py`, `tests/test_web.py` |

## Aufbau

```
lotse/
  wissen.py  recht.py  suche.py  pdfquellen.py  ekodex.py   Wissensschicht (Recht, PDFs, Erstattungskodex, BM25, Relevanz)
  katalog.py  data/leistungen.json  data/termine.json       Leistungskatalog und Terminwissen mit Belegen
  formulare.py  data/formulare/*.json                       Formular-Registry und AcroForm-Füllung
  dokument.py                                               Dokumentfunktion (Empfehlungen, Stammdaten, Impfungen, Medikamente, Fotos)
  grenzen.py                                                Medizinische Grenze (Anfrage und Ausgabe)
  lotse.py  fallakte.py  texte.py  llm.py  speicher.py      Dialog, Fallakte, Termine, Texte, KI-Anbindung, Speicherung
  slots.py  models.py  config.py                            Gemeinsame Typen und Konfiguration
  web/app.py  web/static/                                   FastAPI und Oberfläche (ohne Build-Schritt)
examples/                                                   Fiktive Demo-Dokumente (Brief als Text und Foto, Impfpass)
docs/ARCHITEKTUR.md                                         Architektur und methodische Entscheidungen
docs/praesentation/                                         Folien (HTML, PDF) und Demo-Video
Analyse/                                                    Plan und Gegenprüfung gegen die Originalquellen
Dockerfile                                                  Container mit eingebautem Suchindex
```

Mehr zu Methodik und Entscheidungen in [`docs/ARCHITEKTUR.md`](docs/ARCHITEKTUR.md).

## Bekannte Einschränkungen und offene Punkte

- **Keine echte Buchung oder Einreichung:** Der Lotse bereitet Termine und Anträge vor; vereinbaren, unterschreiben und einreichen tut die Person selbst.
- **KI-Modus:** live getestet. Die automatischen Tests laufen bewusst ohne Modell. Modellausgaben schwanken; Schutz bieten die Prüfungen nach der Ausgabe und die regelbasierte Rückfallebene. Weitere Sprachen und Fotos gibt es nur im KI-Modus. Fotos immer mit dem Original vergleichen.
- **Spracheingabe** nur in Browsern mit Web Speech API (z. B. Chrome); Firefox hat sie nicht, dort ist der Knopf ausgeblendet. Getestet wurde die Einbindung mit einer simulierten Erkennung; Vorlesen läuft in allen gängigen Browsern.
- **Regionale Angebote** außerhalb Wiens sind offizielle Landesseiten (extern markiert, am 06.11.2026 geprüft). FSW-Formulare gelten nur in Wien. Für das ÖGK-Fahrtkostenformular (Wiener Fassung) ist die Gültigkeit in anderen Ländern lokal nicht belegt. Mobile Frühförderung ist nur für Wien hinterlegt, Wohnbeihilfe fehlt.
- **Externe Belege:** Sozialhilfe, Familienberatung und Schuldenberatung stützen sich auf externe Seiten, weil die Gesetze nicht im Korpus liegen. Den Richtsatz der Ausgleichszulage 2026 nennt der Lotse nicht.
- **Zitate in Übersetzungen** bleiben im deutschen Original, damit der Beleg wörtlich bleibt. Der Anfragetext für die Ordination ist immer Deutsch.
- **Suche:** lexikalisch (BM25, ohne Embeddings). Themenfremde Fragen werden über einen Fachwortschatz herausgefiltert.
- **Erstattungskodex:** Die Kennzeichen DSX, KNP und ADL erklärt die lokale Legende nicht; der Lotse sagt das so, ohne eigene Deutung.
- **Gewichtung der Finaljury-Kriterien:** in den Unterlagen nicht angegeben (siehe `Analyse/Plan_1_Platz.md`, Abschnitt 9).

## Lizenz

Code und Dokumentation: MIT (siehe `LICENSE`). Die SV-Box-Daten unterliegen den Bedingungen ihrer Herausgeber und der Teilnahmeinformation der KI Challenge 2026.
