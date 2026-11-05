# Gegenprüfung: Plan und Analyse gegen Originalquellen

Methode: Ich habe jede Aussage direkt in der Originaldatei nachgeprüft, nicht anhand der Agentenberichte. PDF-Text über `pypdf`, DOCX über `zipfile` (`word/document.xml`, Header-Relationen), XML über `xml.etree`, TXT byteweise. Personen- und Gesundheitswerte aus `Befunde/` stehen nicht in diesem Protokoll; Identitätsvergleiche liefen nur über Hashes.

Status: **bestätigt** · **korrigiert** (die Aussage war falsch oder ungenau) · **nicht prüfbar** (die Grenze ist angegeben)

## 1. Wettbewerb (KI Challenge Teilnahmeinformationen.pdf)

| Aussage im Plan v1 | Befund in der Quelle | Status |
|---|---|---|
| Start Do 5.11. 12:00 | S.1: „12:00 Uhr: offizieller Start“ | bestätigt |
| „Abgabe Fr 13:00“ | So steht es nicht im Text. S.1: Veranstaltung bis Fr 13:00. S.4: Ergebnisse „bis zum Ende der Challenge vollständig im zugewiesenen Repository“. S.2 und S.4: Die Fachjury bewertet **ab Fr 10:00**. S.3: „22 bis 24 Stunden“ | **korrigiert**: Lauffähige Demo und Repo müssen bis Fr 10:00 stehen (Stunde 22). Spätestens 13:00 muss das Repo vollständig sein |
| Fachjury: 15-Minuten-Pitch | S.4: Die Fachjury „kommt zu den Teams“ und bewertet die Lösung gemeinsam mit ihnen, etwa 15 Min. Zu vermitteln sind Problem, Funktionsweise und Mehrwert | **korrigiert**: Demo am Arbeitsplatz, kein Bühnenpitch |
| Finale: Top-Team je Use Case | S.4: „Aus jedem Use Case wird das top gereihte Team“ eingeladen. S.2: „Top-3-Teams“ | bestätigt. Ohne Sieg im Use Case 1 gibt es keinen Platz 1 |
| Finaljury-Kriterien fehlen | S.5 nennt Erwartungen an die Präsentation: Lösungsansatz, wichtigste Funktionen, konkreter Nutzen, Grenzen, nächste Entwicklungsschritte. Eine Live-Demo ist „sinnvoll“. S.2: Präsentation über Beamer (HDMI) | **korrigiert**: Inhaltliche Erwartungen sind belegt, die Gewichtung fehlt |
| Preise 5.000/3.000/2.000 € | S.5 | bestätigt |
| Teamgröße max. 5, Fragestunde Do 17:00 | S.2, S.1 | bestätigt |
| Use Case darf gewechselt werden | S.3 | bestätigt (neu aufgenommen) |
| Methoden und Entscheidungen dokumentieren | S.3: „nachvollziehbar dokumentiert“ | bestätigt (neu als Pflicht aufgenommen) |
| Keine echten Daten; Befunde nicht ins Repo | S.2: „Alle übergebenen Daten der SV Box sind öffentlich verfügbar und können somit frei verteilt werden.“ Use Case: Befunde sind „realistische anonymisierte Befunde“. S.3: keine **echten** personenbezogenen Daten | **korrigiert**: Die SV-Box-Befunde sind als Demo-Eingabe zulässig. Nicht veröffentlicht werden: Passwort, API-Key, eigene echte Daten |
| README-Pflichtinhalte | S.3–4: Beschreibung, Ausführung, Abhängigkeiten, Konfiguration, Einschränkungen | bestätigt |

## 2. Use Case 1 (DOCX)

| Aussage | Befund | Status |
|---|---|---|
| Fachjury-Kriterien im Use Case | Der Plan v1 hat Kriterien ausgelassen: wie **eigenständig und durchdacht** die Lösung ist, wie **flexibel und intelligent** sie unterschiedliche Aufgaben bewältigt und wie gut **Daten und Wissensquellen genutzt und verknüpft** werden | **korrigiert** |
| Szenarien nur für die Demo | Die Überschrift lautet „Szenarien – **auch für die Bewertung**“: Pflege, Gesundheitsförderung, Case Manager nach Spitalsaufenthalt, Kind | **korrigiert**: Alle 4 Szenarien müssen vorführbar sein |
| Statusverfolgung als optional | Das Zielbild verlangt, offene Schritte mitzuteilen; 3.1 nennt erledigte und offene Schritte | **korrigiert**: Statusverfolgung ist Pflicht |
| Bild nach der Finaljury-Überschrift | `image1.jpeg` hängt an `header1.xml.rels`. Es ist das SV-Logo in der Kopfzeile. Nach der letzten Überschrift „Finaljury“ stehen 3 leere Absätze, keine Bilder, Tabellen oder Textboxen | **korrigiert**: Der Abschnitt ist leer |
| Harte Grenzen | Abschnitt 4 | bestätigt |
| Spannungsfeld Vorsorge | 3.4 verlangt, nach familiären Erkrankungen zu fragen und die Vorsorge mit hohem Mehrwert zu erklären. Abschnitt 4 verbietet Risikobewertung | neu: Vorsorge nur über offizielle Programmkriterien erklären, ohne individuelle Risikoeinschätzung |
| „Bewegt im Park“ | Wird im Use Case genannt; im Serviceratgeber 0 Treffer | neu: Externe Quelle nötig (Liste im Use Case) |

## 3. API-Beispiel (DOCX)

| Befund | Status |
|---|---|
| Azure-Foundry-Endpoint `…/openai/v1`, Deployment `gpt-5-4-mini`; Chat Completions (curl) und Responses API (Python) | bestätigt (neu aufgenommen) |
| Key nur über `$AZURE_API_KEY` bzw. `<your-api-key>`; im Dokument steht kein echter Key | bestätigt |
| Das Python-Beispiel lässt sich so nicht ausführen: der Endpoint steht ohne Anführungszeichen | neu |

## 4. Inventar

| Prüfung | Ergebnis | Status |
|---|---|---|
| Neu-Scan ohne `Analyse/` und `.git/` | 14.270 Dateien; 79.238.295 Byte (79,2 MB bzw. 75,6 MiB) | bestätigt |
| CSV gegen Neu-Scan | 0 Dateien fehlen, 0 überzählig, 0 Hash-Abweichungen, 0 Hash-Duplikate | bestätigt |
| Verteilung | Rechtstexte 14.244 · Formulare 7 · Medikamente 7 · Befunde 5 · Leistungskataloge 3 · Wurzelverzeichnis 4 | bestätigt |

## 5. Rechtstexte (14.244 XML)

| Aussage | Befund | Status |
|---|---|---|
| 0 Parsefehler, 812 Familien, ASVG 1.218 | Neu gezählt; Root-Element immer `sozdok` | bestätigt |
| Kernquellen vorhanden | BPGG 80, BPGGEinstV_1999 9, B-KUVG 383, GSVG 543, BSVG 576, KBGG 70, FLAG 143. Die ASVG-Paragraphen 135, 137, 141, 143a–d, 154, 154a, 155, 156, 160, 302–307, 307h liegen jeweils als eigene Datei vor | bestätigt |
| „Versionslogik nötig“ | Jede Norm liegt in **genau einer** Datei vor (0 Normen mit mehreren Dateien). Der Korpus ist eine Momentaufnahme ohne Versionshistorie. Dateiname: `Kürzel=Typ=Nr=BGBl-Nr=Kundmachung=Inkrafttreten` | **korrigiert** |
| § 154a als Datumsanomalie | 3.277 Dateien wurden nach ihrem Inkrafttreten kundgemacht. Das ist rückwirkendes Inkrafttreten und kein Datenfehler. Echte Auffälligkeiten: 215 Dateien mit dem Platzhalterdatum `1111-…` und 6 Dateien mit abweichendem Namensschema | **korrigiert** |
| Jüngster Rechtsstand | Inkrafttreten spätestens 2026-10-01, Kundmachung spätestens 2026-09-17; nichts tritt erst nach dem 5.11.2026 in Kraft | neu |
| § 141 ASVG: Anm. 1 mit 660,52 € (2025) und 708,74 € (2026), BGBl. II Nr. 263/2025 | Im Text vorhanden | bestätigt |
| „Pflegegeldhöhen fehlen“ | BPGG § 5 enthält nur die Grundbeträge ab 2020 (Stufe 1: 157,30 €) samt Anpassungsregel. Die **Beträge für 2026** stehen in `Aufwertung_und_Anpassung_nach_ASVG,_GSVG,_BSVG,_B-KUVG,_BPGG_fuer_2026=ART=3` (BGBl. II Nr. 263/2025): Stufe 1 206,20 € · 2: 380,30 € · 3: 592,60 € · 4: 888,50 € · 5: 1.206,90 € · 6: 1.685,40 € · 7: 2.214,80 € | **korrigiert**: Die Beträge sind im Korpus. Liest man nur § 5, kommen falsche Beträge heraus |

## 6. Medikamente (Erstattungskodex)

| Aussage | Befund | Status |
|---|---|---|
| `medikament.txt`: 6.985 Zeilen, cp1252, CRLF, feste Breite 195 | Bestätigt; alle 6.985 PZN sind eindeutig und numerisch | bestätigt |
| `atccode.txt`: 6.611 Zeilen, Breite 207, ohne PZN-Join | Bestätigt. Die Datei ist eine ATC-Referenz (Code + Bezeichnung); 6.597 von 6.611 Codes sind formal gültig. In `medikament.txt` findet sich kein ATC-Muster | bestätigt |
| IND 1.269 / RE 1.330, eindeutig, alle in `medikament.txt`, keine Überschneidung, v1 und v2 mit gleicher Schlüsselfolge | Bestätigt; v2 ist UTF-8 mit HTML-Entities (IND 3.826, RE 10.310); 78 RE-Zeilen enthalten `;` im Text | bestätigt |
| Kennzeichen | Box `Y` ⇔ Schlüssel in der Regeltext-Datei (1.330 = RE1 856 + RE2 474). Kennzeichen `IND` ⇔ Schlüssel in der Indikationstext-Datei (1.269). Dazu kommen weitere Kennzeichen (N, F14, D, …) laut Legende | neu, bestätigt |

## 7. Leistungskataloge

| Aussage | Befund | Status |
|---|---|---|
| Serviceratgeber 2026 (ÖGK), 59 S. | S.1: „Die ÖGK im Überblick – Leistungen und Services 2026“ | bestätigt |
| Pflegegeld im Serviceratgeber | Nur im Zusammenhang mit Selbst- bzw. Weiterversicherung pflegender Angehöriger (ab Stufe 3). Keine Beträge, keine Antragstelle, 0 Treffer für „Pflegeheim“ | bestätigt |
| Zahnärzte-HO 2026, 48 S., S.48 ohne Text | „gültig ab 1. Jänner 2026“; nur S.48 ohne Text | bestätigt |
| ÖGK-HO nur für die Steiermark, Stand 01.01.2025, 147 S. | Deckblatt: „im Bundesland Steiermark … Stand: 01.01.2025“ | bestätigt |

## 8. Formulare und Befunde

| Aussage (Agentenbericht) | Befund | Status |
|---|---|---|
| Bei 4 Formularen seien die Feldnamen nicht auslesbar | `pypdf` liest bei **allen 7** Formularen die AcroForm-Felder: KUR1 96 · Fahrtkosten 13 · WG 21 · Einrichtungswunsch 13 · PAL080 102 · Reha nach Unfall 59 · FSW 122 (davon 3 Signaturfelder). Alle Felder sind leer. Die Namen sind sprechend (z. B. PAL080 `Fam.Name`, `Geburtsdatum`; KUR1 `VSNR_1`, `zuständiger SV-träger`, `Pflegegeld`) | **korrigiert**: Vorbefüllen über AcroForm ist technisch machbar |
| PAL080 = Pflegegeld nach BPGG, PVA, Ausgabe 01.2025, 8 S. | S.1: „Pensionsversicherungsanstalt … PAL 080 (01. 2025) … ANTRAG auf PFLEGEGELD nach dem Bundespflegegeldgesetz (BPGG)“ | bestätigt |
| Fahrtkosten-Zuschuss: ÖGK, Strahlentherapie-Ausnahme, IBAN | „ÖGK“, „Strahlentherapie“ und „IBAN“ kommen im Text vor | bestätigt |
| FSW: Pflege zu Hause S.5, Unterlagen S.12–13 | V8 03/2026. S.5: „Pflege und Betreuung zu Hause / Tagesbetreuung“; Beilagen dazu auf **S.13**. Außerdem „Mobile Frühförderung“ (S.7, S.13) | bestätigt (Seitenangabe präzisiert). Neu: Frühförderung passt zum Szenario Kind |
| KUR1 mit Onkologie-Kategorie | Treffer „Onkolog“ vorhanden | bestätigt |
| Seitenzahlen (7/2/3/3/1 Befunde; 8/2/2/2/13/2/2 Formulare) | Neu gezählt; alle Seiten enthalten Text, kein reiner Scan | bestätigt |
| Der Entlassungsbefund dokumentiert administrative Empfehlungen | Ausdrücklich genannt: Rehabilitationsantrag vorbereiten, Pflegegeldanspruch prüfen, mobile Hauskrankenpflege organisieren, Transport bzw. Fahrten zu Bestrahlungsterminen klären, Rezeptgebührenbefreiung. Der Befund hält selbst fest: „Ein Anspruch ist nicht automatisch durch die Krebserkrankung gegeben“. Entlassungsdatum im Oktober 2026 | neu: Ein konstruierter Komplettfall, der zu PAL080, KUR1, Fahrtkosten und FSW passt |
| Identitätsdaten widersprechen sich zwischen den Befunden | Ein Hash-Vergleich der Feldwerte ließ keine belastbare Aussage zu; nur der Entlassungsbefund enthält Datumsangaben im Format TT.MM.JJJJ | **nicht prüfbar** |
| Layout- und OCR-Qualität | Ohne Renderer nicht visuell geprüft | **nicht prüfbar** |

## 9. Folgen für den Plan

Alle korrigierten Punkte sind in `Analyse/Plan_1_Platz.md` (v2) eingearbeitet: Zeitplan mit Fachjury in Stunde 22, alle 4 Bewertungsszenarien, Statusverfolgung als Pflicht, Rechtsstand-Auflösung mit Pflegegeld-Testfall, AcroForm-Vorbefüllung, Entlassungsbefund als Hauptdemo, korrigierte Datenregel und Modellanbindung.
