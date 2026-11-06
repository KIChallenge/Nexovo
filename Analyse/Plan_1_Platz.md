# Plan: 1. Platz – KI Challenge 2026, Use Case 1 (SV KI-Lotse)

Version 2. Die Aussagen sind gegen die Originalquellen geprüft; das Prüfprotokoll steht in `Analyse/Gegenpruefung.md`. Repo: `git@github.com:KIChallenge/Nexovo.git`. Zugangsdaten werden weder in Ausgaben noch ins Repo übernommen.

## 1. Spielregeln (belegt)

| Thema | Vorgabe | Quelle |
|---|---|---|
| Arbeitszeit | Start Do 5.11. 12:00. Die Fachjury bewertet **ab Fr 10:00** (Stunde 22). Die Challenge endet Fr 13:00; bis dahin muss das Repo vollständig sein | Teilnahmeinfo S.1–4 |
| Fachjury | Kommt **an den Arbeitsplatz**, etwa 15 Min. Schnell zeigen: Problem, Funktionsweise, Mehrwert | S.4 |
| Weg zu Platz 1 | Nur das bestgereihte Team je Use Case kommt ins Finale. Erst Use Case 1 gewinnen, dann das Finale | S.4 |
| Finale | 12:00–12:45 vor der Finaljury, Beamer (HDMI). Zu zeigen: Lösungsansatz, wichtigste Funktionen, konkreter Nutzen, Grenzen, nächste Schritte; Live-Demo ist „sinnvoll“. Eine Gewichtung ist nicht angegeben | S.2, S.5; Use-Case-DOCX (Abschnitt leer) |
| Allgemeine Kriterien | Methodik/Daten-/KI-Qualität · Nutzen/Wirkung · Umsetzbarkeit/Time-to-Impact · Transparenz/verantwortungsvoller KI-Einsatz · Nutzbarkeit/Kommunikation · Innovationsgrad | S.4–5 |
| Use-Case-Kriterien | Technik + Nutzen · **Eigenständigkeit/Durchdachtheit** · **Flexibilität bei unterschiedlichen Aufgaben** · **Nutzung und Verknüpfung von Daten und Wissensquellen** · Verständlichkeit · Qualität der Handlungsschritte · Umgang mit Unsicherheit und Grenzen · Weg zum Produkt · Zusatznutzen | Use-Case-DOCX |
| Bewertungsszenarien | Pflege · Gesundheitsförderung · Case Manager nach Spitalsaufenthalt · Kind („auch für die Bewertung“) | Use-Case-DOCX |
| Repo-Inhalt | Code, Konfiguration ohne Geheimnisse, Doku des Ansatzes, Tests/Beispiele, README (Beschreibung, Ausführung, Abhängigkeiten, Konfiguration, Grenzen). Methoden und Entscheidungen nachvollziehbar dokumentieren | S.3–4 |
| Daten | Die SV-Box-Daten sind „öffentlich verfügbar“ und frei verteilbar; die Befunde sind „realistische anonymisierte“. Verboten: echte personenbezogene Daten, API-Keys, Passwörter, Tokens, interne Zugangsdaten | S.2–3; Use-Case-DOCX |
| Grenze | Keine Diagnose, keine Befundinterpretation, keine Risikobewertung, keine Therapie- oder Medikamentenempfehlung. Erlaubt ist, **ausdrücklich dokumentierte Empfehlungen** administrativ zu nutzen | Use-Case-DOCX Abschn. 4 |
| Modell | Azure Foundry, Deployment `gpt-5-4-mini`, Chat Completions bzw. Responses API, Key über `AZURE_API_KEY` | API-Beispiel-DOCX |

## 2. Siegesthese

Platz 1 holt ein Lotse, der den mitgelieferten **Entlassungsbefund** live in einen vollständigen, quellenbelegten Fallplan verwandelt: dokumentierte Empfehlung → Leistung → zuständige Stelle → vorausgefülltes Originalformular → Unterlagen-Checkliste → Status. Die medizinische Grenze ist dabei sichtbar eingehalten. Die Daten geben diesen Fall her:

- Der Entlassungsbefund nennt ausdrücklich: Rehabilitationsantrag vorbereiten, Pflegegeldanspruch prüfen, mobile Hauskrankenpflege organisieren, Fahrten bzw. Transport zu Bestrahlungsterminen klären, Rezeptgebührenbefreiung. Er schreibt selbst: „Ein Anspruch ist nicht automatisch … gegeben“. Daran lässt sich die Grenze vorführen.
- Passende Originalformulare mit auslesbaren AcroForm-Feldern: PAL080 Pflegegeld (PVA, 102 Felder), KUR1 Reha (96), ÖGK-Fahrtkosten mit Strahlentherapie-Ausnahme (13), FSW-Förderung Pflege zu Hause (122).
- Rechtsgrundlagen mit aktuellem Stand: BPGG, ASVG und die Anpassungsverordnung 2026 (Pflegegeld 2026: Stufe 1 206,20 € bis Stufe 7 2.214,80 €, BGBl. II Nr. 263/2025).

Wodurch wir uns abheben (Innovation und Transparenz):
1. **Rechtsstand-Auflösung:** BPGG § 5 liefert nur die Grundbeträge von 2020 (Stufe 1: 157,30 €). Der Lotse verweist auf die geltende Anpassungsverordnung und zeigt beide Quellen. Ein naiver RAG-Ansatz würde falsche Beträge nennen.
2. **Belegpflicht:** Jede Aussage nennt ihre Quelle (Norm/§ mit BGBl.-Nummer und Inkrafttreten bzw. Seite in Serviceratgeber oder Formular) oder ist als „nicht belegt“ markiert.
3. **Zitat statt Interpretation:** Empfehlungen aus dem Befund werden wörtlich mit Fundstelle übernommen; eine eigene medizinische Ableitung gibt es nicht.
4. **Fallakte mit Status:** offene und erledigte Schritte, Fristen, fehlende Unterlagen.

## 3. Datenbestand (geprüft)

| Bestand | Befund | Nutzung |
|---|---|---|
| Gesamt | 14.270 Dateien, 79,2 MB, 0 Hash-Duplikate (`Analyse/Dokumenteninventar.csv`) | – |
| Rechtstexte | 14.244 XML, 0 Parsefehler, 812 Familien. Momentaufnahme mit genau 1 Datei pro Norm. Name: `Kürzel=Typ=Nr=BGBl=Kundmachung=Inkrafttreten`. 3.277 Dateien sind rückwirkend in Kraft gesetzt, 215 tragen das Platzhalterdatum `1111`, 6 haben ein abweichendes Namensschema | Index mit Metadaten (Norm, §, BGBl, Kundmachung, Inkrafttreten). Platzhalterdatum als „Stand unbekannt“ anzeigen |
| Kernnormen | BPGG (80), BPGGEinstV_1999, Anpassungs-VO 2026, ASVG §§ 135, 137, 141, 143a–d, 154, 154a, 155, 156, 160, 302–307h; B-KUVG, GSVG, BSVG, KBGG, FLAG | Pflege, Reha, Transport, Krankengeld, Familie |
| Erstattungskodex | 6.985 PZN. Box `Y` ⇔ Regeltext (RE1 856 + RE2 474); `IND` ⇔ Indikationstext (1.269). `atccode.txt` ist nur eine ATC-Referenz ohne PZN | Nur Erstattungsstatus: „bewilligungspflichtig?“. Nie Auswahl oder Empfehlung |
| Serviceratgeber ÖGK 2026 | 59 S., Leistungen und Services; Pflegegeld nur im Kontext Selbstversicherung pflegender Angehöriger; „Bewegt im Park“ nicht enthalten | Hauptquelle für ÖGK-Leistungen (Szenarien Gesundheit, Kind, Reha, Kur) |
| Honorarordnungen | Zahnärzte 2026 (S.48 ohne Text); ÖGK-HO nur für die Steiermark, Stand 01.01.2025 | Nur für Zusatzfragen zu Kosten bzw. Kassenleistungen; Gültigkeitsbereich anzeigen |
| Formulare | 7 PDFs, alle mit leeren, auslesbaren AcroForm-Feldern. Der FSW-Antrag (V8 03/2026) deckt „Pflege und Betreuung zu Hause“ (S.5) und „Mobile Frühförderung“ (S.7) ab; Beilagen auf S.13 | Vorausfüllen über `pypdf`; Frühförderung für das Szenario Kind |
| Befunde | 5 PDFs mit Text. Nur der Entlassungsbefund enthält administrative Empfehlungen; Impfpass für Szenario Vorsorge | Demo-Eingabe; nur zitieren, nicht interpretieren |

## 4. Anforderungsmatrix

| ID | Anforderung | Priorität | Abnahmefall (messbar) |
|---|---|---|---|
| R1 | Situation verstehen, Leistungsbündel vorschlagen | Pflicht | Alle 4 Bewertungsszenarien: je ≥ 3 Bündel, jedes mit Quelle und zuständiger Stelle |
| R2 | Nur notwendige Rückfragen | Pflicht | Pflegefall „Mutter kommt allein nicht zurecht“: ≤ 5 Rückfragen bis zum PAL080-Entwurf (Teamziel) |
| R3 | Rechtsgrundlage mit Stand | Pflicht | 20 Fragen mit Sollquelle; Treffer ≥ 18/20. Pflegegeld Stufe 3 für 2026 = 592,60 € mit Quelle BGBl. II Nr. 263/2025 (nicht 451,80 €) |
| R4 | Dokumentfunktion: dokumentierte Empfehlungen | Pflicht | Entlassungsbefund: alle 5 administrativen Aufgaben wörtlich und mit Seite erkannt; 0 eigene medizinische Aussagen |
| R5 | Formulare vorausfüllen | Pflicht | Ausgefüllte PDFs für PAL080 und KUR1 aus Dialog und Befund; Pflichtfelder markiert; Unterschrift bleibt bei der Person; nichts wird automatisch versendet |
| R6 | Zuständige Stelle und Einrichtung | Pflicht | Pflegegeld → PVA (bzw. Träger laut Pension); Reha → zuständiger SV-Träger; Fahrtkosten → ÖGK; Pflege zu Hause → FSW. Jeweils mit Quelle |
| R7 | Unterlagen-Checkliste | Pflicht | Je Antrag eine Liste aus dem Formulartext; fehlende Unterlagen markiert |
| R8 | Statusverfolgung (offen/erledigt) | Pflicht | Die Fallakte zeigt Schrittstatus; nach „Antrag unterschrieben“ ändert sich der nächste Schritt |
| R9 | Personalisierung | Pflicht | Derselbe Fall in Deutsch einfach, Deutsch ausführlich und Englisch; Quellen bleiben gleich |
| R10 | Grenzen und Unsicherheit | Pflicht | 10 Negativtests (Diagnose, Medikament, Dosis, Risiko, „brauche ich Reha?“): 10/10 korrekt abgelehnt, mit Verweis an die zuständige Stelle |
| R11 | Vorsorge ohne Risikobewertung | Pflicht | „Familiäre Vorbelastung“ → nur offizielle Programmangebote mit Quelle, keine individuelle Risikoeinschätzung |
| R12 | Datenschutz und Geheimnisse | Pflicht | Secret-Scan ohne Treffer; `.env` nicht im Repo; kein SV-Box-Passwort im Repo |
| R13 | Dokumentierte Methodik | Pflicht | README und `docs/` mit Architektur, Datenfluss, Quellen, Testergebnissen, Grenzen |
| R14 | Termine | Optional | Terminvorbereitung (Fragen, Unterlagen, Kontakt); keine echte Buchung |
| R15 | Foto/Upload, Sprachsteuerung | Optional | PDF-Upload Pflicht für R4; Foto bzw. Sprache nur, wenn R1–R13 grün sind |

## 5. Lösungsarchitektur (Entscheidung)

- **Wissensschicht:** XML-Parser → Normindex (Metadaten aus Dateiname und `metadaten`); PDF-Text aus Serviceratgeber und Formularen mit Seitenbezug; Lookup im Erstattungskodex über PZN. Abruf lexikalisch mit BM25. Embeddings sind entfallen: Es gab keinen API-Schlüssel, und das Fragenset erreicht auch so 20/20 (Begründung in `docs/ARCHITEKTUR.md`). Rechtsstand-Regel: Anpassungsverordnung schlägt Grundbetrag.
- **Lotse:** Modell `gpt-5-4-mini` über die Azure-Endpoint-Konfiguration in `.env`. Zustandsautomat: Situation → Bündel → Rückfragen → Antrag → Checkliste → Status. Antworten nur aus abgerufenen Belegen (Zitierpflicht im Ausgabeschema).
- **Guardrail:** Vorgeschaltete Klassifikation „medizinische Beurteilung?“ plus Prüfung der Ausgabe auf Diagnose- und Medikamentensprache.
- **Formular-Service:** Feldmapping je Formular (JSON) → `pypdf` füllt AcroForm → Vorschau und Download.
- **UI:** Chat + Fallakte (Bündel, Schritte, Quellen, Formulare). Sprachwahl und Detailtiefe als Schalter.

## 6. Zeitplan (Do 12:00 = Stunde 0)

| Zeit | Paket | Abnahme |
|---|---|---|
| Do 12:00–13:00 | Scope, Rollen (max. 5), Repo-Setup mit `.gitignore` und `.env.example`, Architekturskizze | Leeres Repo gepusht, ohne Geheimnisse |
| 13:00–17:00 | Wissensschicht: Normindex, Serviceratgeber, Formularkatalog, Erstattungskodex-Lookup, Rechtsstand-Regel | 20 Quellfragen ≥ 18/20 |
| 13:00–17:00 | Dokumentfunktion Entlassungsbefund | R4 grün |
| **17:00** | **Fragestunde:** Finaljury-Gewichtung? Repo-Zugang? Externe Webquellen (z. B. „Bewegt im Park“) erlaubt? SV-Box-Daten im Repo ablegen? | Antworten in `docs/` |
| 17:00–23:00 | Lotse-Dialog, Rückfragen, Bündel für alle 4 Szenarien | R1, R2 grün |
| 20:00–02:00 | Formular-Service PAL080 und KUR1; Checklisten; Fahrtkosten | R5, R6, R7 grün |
| laufend | Guardrails und Negativtests | R10, R11 grün |
| Fr 02:00–05:00 | Fallakte und Status, Personalisierung | R8, R9 grün |
| 05:00–08:00 | Ende-zu-Ende-Test aller Szenarien, README, Doku, Secret-Scan, Push | R12, R13 grün |
| 08:00–09:30 | Demo-Proben (15 Min. am Platz), Backup-Video, **Code-Freeze 09:30** | Demo zweimal fehlerfrei |
| 10:00–11:30 | Fachjury am Arbeitsplatz | – |
| 11:30–12:00 | Finale auf Beamer/HDMI vorbereiten | Technikcheck |
| 12:00–12:45 | Finalpräsentation | – |
| bis 13:00 | Repo final und vollständig | Letzter Push |

## 7. Demo-Drehbuch (15 Min. Fachjury)

1. **Problem (1 Min.):** „Nach der Entlassung: 5 Aufgaben, 4 Stellen, 4 Formulare.“
2. **Hauptfall (7 Min.):** Entlassungsbefund hochladen → 5 zitierte Empfehlungen → Bündel mit zuständigen Stellen → 3 Rückfragen → vorausgefülltes PAL080 und KUR1 → Unterlagen-Checkliste → Fallakte.
3. **Grenze (2 Min.):** „Brauche ich wegen meiner Diagnose Reha?“ → begründete Ablehnung und Weg zur Ärztin bzw. zum Arzt. Pflegegeldbetrag 2026 mit Quelle und dem Hinweis auf den Rechtsstand.
4. **Breite (3 Min.):** Kind und Gesundheitsförderung im Schnelldurchlauf; Umschalten auf Englisch bzw. einfache Sprache.
5. **Umsetzbarkeit (2 Min.):** Architektur, Testergebnisse (R3, R10), Weg zum Produkt (ELGA-/Träger-Schnittstellen, Terminservices).

Finale: dieselbe Geschichte in 3 Teilen (Ansatz, Funktionen, Nutzen) plus Grenzen und nächste Schritte, mit Live-Demo und Backup-Video.

## 8. Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| Ein anderes Team gewinnt Use Case 1 (kein Finale) | Fachjury-Kriterien des Use Case vollständig abdecken (Abschn. 4) und alle 4 Szenarien vorführbar machen |
| Modell halluziniert Quellen | Zitierpflicht im Schema; nicht belegte Aussagen werden verworfen; R3-Testset |
| Falscher Rechtsstand (z. B. Pflegegeldbetrag) | Rechtsstand-Regel und Testfall R3 |
| Medizinische Grenze überschritten | Guardrail vor und nach dem Modell; R10 |
| API-Ausfall oder Kontingent erschöpft | Antwort-Cache für die Demofälle und Backup-Video |
| Geheimnis im Repo | `.gitignore`, `.env.example`, Secret-Scan vor jedem Push |
| Rohdaten im Repo | Entschieden: Die Daten, die zur Ausführung nötig sind, liegen im Repo (laut Teilnahmeinfo S. 2 frei verteilbar). Nicht im Repo sind `Befunde/`, beide DOCX und die Teilnahmeinfo. Editor-Swap-Dateien sind per `.gitignore` gesperrt |
| Zeitverzug | Reihenfolge R4 → R5 → R1; Optionales (R14, R15) zuerst streichen |

## 9. Offene Punkte

- Gewichtung der Finaljury: steht in keiner Unterlage. S. 5 nennt nur die Inhalte der Präsentation, die Use-Case-Überschrift „Bewertungskriterien für Finaljury“ ist leer.
- Repo-Zugang: erledigt (SSH-Push funktioniert).
- Externe Webquellen: laut Use Case erlaubt („Weitere mögliche Quellen zur Identifikation von Leistungsangeboten“). Bedingung laut Teilnahmeinfo S. 3: Nutzungsbedingungen beachten; nur Inhalte mit Veröffentlichungsrechten ins Repo übernehmen.
- Zuständigkeit für Pflegegeld hängt vom Pensionsträger ab (PVA, SVS, BVAEB). Im Demofall muss der Lotse dazu nachfragen.
- Layout der PDFs: geprüft (alle Befund- und Formularseiten gerendert). Die Befunde sind laut Dokument bzw. Name („Testpatient“) fiktiv; Details in `Analyse/Gegenpruefung.md`.

## 10. Stand der Planabnahme

- [x] Inventar neu berechnet und mit der CSV deckungsgleich (14.270; 0 Abweichungen).
- [x] Alle Aussagen zu Wettbewerb, Use Case, API, Rechtstexten, Erstattungskodex, Katalogen und Formularen gegen die Originale geprüft (`Analyse/Gegenpruefung.md`).
- [x] Pflichtanforderungen R1–R13 mit messbarem Abnahmefall.
- [ ] Finaljury-Gewichtung: nicht belegbar.
- [x] Visuelle Prüfung von Layout und Textebene: alle Formular- und Befundseiten gerendert geprüft (06.11.).
