# Prüfprotokoll Bedienbarkeit und Barrierefreiheit (WCAG 2.2 AA)

Stand: 06.11.2026. Vorher = Commit `385ca96` (alte Oberfläche mit Fallakte auf einer Seite), nachher = Arbeitsstand mit
den Ansichten „Gespräch“, „Mein Plan“, „Meine Akte“ und den Unteransichten Leistung und Termin (KISS-Struktur).
Rohdaten: `docs/ux/messung_vorher.json`, `docs/ux/messung_nachher.json`.

## 1. Methode und Werkzeuge

| Werkzeug | Version |
|---|---|
| Chromium (headless, Nix-Store) | 157.0.8103.38 |
| Playwright (Python) | 1.64.1 |
| axe-core über axe-playwright-python | 4.12.1 über 0.1.8 |
| Lotse | regelbasiert (`AZURE_API_KEY=` leer), eigener `LOTSE_CACHE_DIR`, freier Port |

- **Messung** (`tests/ui/messung.py --url … --out …`): stellt jeden Zustand in einem frischen Browser-Kontext über die
  sichtbare Oberfläche her (Rolle und Name) und misst dort Folgendes: axe-Verstöße (Tags wcag2a, wcag2aa, wcag21a,
  wcag21aa, wcag22aa; best-practice getrennt), sichtbare Textelemente < 16 px und < 14 px, Bedienelemente < 24×24 und
  < 44×44 px (Links im Fließtext getrennt; zusätzlich die Abstands-Ausnahme von 2.5.8), sichtbare Wörter (Seite und
  Bereich), `<details>`, sichtbare Buttons, Links und Aufklapper, Anzahl `.hauptaktion`, Tab-Stopps über echte
  Tab-Tastendrücke (gesamt, vor „Ihre Nachricht“, Fokusanzeige ≥ 2 px je Halt), Seitenhöhe, horizontaler Überlauf und
  vorhandene Darstellungs-Unterstützung (CSS-Regeln und Bedienelemente).
- **Zustände:** S1 Start · S2 Pflegefall („Meine Mutter kommt allein nicht mehr zurecht“ → Wien, PVA, ÖGK, Nein –
  Erstantrag) · S2_plan · S2_akte · S3 Leistung Pflegegeld · S4 synthetischer Entlassungsbrief (Demo-Knopf) · S4_akte ·
  S5 Arzttermin (Vorsorge, Graz, vormittags) · S5_plan · S5_termin_ansicht. In der alten Oberfläche sind Plan, Akte und
  Termin derselbe Seitenzustand; als „Bereich“ wird dort `.akte`, die aufgeklappte Pflegegeld-Karte bzw. die
  Terminkarte gezählt.
- **Viewports:** Desktop 1440×900, Mobil 390×844, 320×640, 400 % Zoom (1280×1024 bei 400 % = 320×256 CSS-px).
- **Testsuite** `tests/ui/` (Marker `ui`, 105 Tests): `test_barrierefreiheit.py` (axe-Matrix, Zielgröße, Schrift, Reflow,
  Modi, Semantik, weitere 2.2-Kriterien), `test_tastatur.py` (Tastaturablauf, Fokus, Zurück-Knopf, Dialog),
  `test_ansichten.py` (KISS-Prüfungen, Ansichten, Funktionserhalt, Druck/PDF). Ausführen mit den Variablen aus
  `requirements-dev.txt`: `.venv/bin/python -m pytest -q tests/ui`.

## 2. Vorher/nachher (Auszug; alle Zustände × Viewports in den JSON-Dateien)

Höchstwert über alle 10 Zustände × 4 Viewports:

| Messgröße | vorher | nachher |
|---|---:|---:|
| axe-Verstöße WCAG 2.0–2.2 A/AA (Knoten) | 0 | **0** |
| sichtbare Textelemente < 16 px | 144 | **0** (kleinste Schrift 16,2 px, vorher 12 px) |
| sichtbare Textelemente < 14 px | 97 | **0** |
| Bedienelemente < 24×24 px | 29 | **0** |
| Bedienelemente < 44×44 px | 84 | **9**, nur Unterlagen-Checkboxen (24 px, klickbare Zeile ≥ 44 px, erlaubt) |
| Tab-Halte ohne Fokusanzeige ≥ 2 px | 0 | 0 |
| horizontaler Überlauf (px) | 0 | 0 |
| Seitenhöhe max. (px) | 15.160 | 4.778 |

Je Zustand, Desktop 1440 px (vorher → nachher):

| Zustand | Wörter Seite | Buttons sichtbar | `<details>` im DOM | Tab-Stopps | Tab vor „Ihre Nachricht“ | Seitenhöhe px | Text < 16 px | Ziele < 44 px |
|---|---|---|---|---|---|---|---|---|
| S1 Start | 158 → 54 | 17 → 9 | 0 → 1 | 23 → 17 | 16 → 12 | 900 → 900 | 17 → 0 | 21 → 0 |
| S2 Gespräch nach Pflegefall | 1.569 → 167 | 23 → 4 | 53 → 1 | 88 → 14 | 22 → 9 | 6.213 → 1.230 | 117 → 0 | 82 → 0 |
| S2 Plan (alt: Fallakte) | 1.569 → 80 | 23 → 5 | 53 → 2 | 88 → 12 | – | 6.213 → 900 | 117 → 0 | 82 → 0 |
| S2 Akte (Angaben) | 1.569 → 263 | 23 → 16 | 53 → 2 | 88 → 24 | – | 6.213 → 1.804 | 117 → 0 | 82 → 0 |
| S3 Leistung Pflegegeld | 1.569 (Karte 551) → 200 | 23 → 1 | 53 → 3 | 88 → 18 | – | 6.213 → 1.366 | 117 → 0 | 82 → 9* |
| S4 Brief geladen | 1.795 → 298 | 23 → 12 | 66 → 1 | 94 → 21 | 25 → 13 | 6.845 → 1.395 | 144 → 0 | 84 → 0 |
| S4 Akte mit Dokumenten | 1.795 → 250 | 23 → 16 | 66 → 2 | 94 → 28 | – | 6.845 → 2.134 | 144 → 0 | 84 → 0 |
| S5 Termin vorbereitet | 552 → 183 | 23 → 4 | 2 → 1 | 45 → 14 | 30 → 9 | 1.751 → 1.230 | 55 → 0 | 34 → 0 |
| S5 Plan mit Termin | 552 → 37 | 23 → 5 | 2 → 1 | 45 → 9 | – | 1.751 → 900 | 55 → 0 | 34 → 0 |
| S5 Termin-Ansicht | 552 (Karte 202) → 185 | 23 → 3 | 2 → 3 | 45 → 14 | – | 1.751 → 1.581 | 55 → 0 | 34 → 0 |

\* Unterlagen-Checkboxen, siehe Ausnahmeliste in Abschnitt 5. 320 px: S4 Brief 15.160 → 4.144 px Seitenhöhe,
S2 Plan 8.048 → 1.418 px.

Darstellungs-Unterstützung (vorher → nachher): forced-colors nein → ja, dunkles Farbschema nein → ja, hoher Kontrast
nein → ja, Textgröße nein → ja (A/A+/A++), Leichte Sprache nein → ja, Druck-Stylesheet nein → ja, „Plan drucken“ nein → ja,
reduzierte Bewegung ja → ja. Hinweis: Das Merkmal `angaben_aendern` steht in der JSON fälschlich auf „false“. Die
Wortgrenze im Muster `\bÄndern\b` erkennt „Ä“ nicht. Dass Angaben änderbar sind, belegen die Tests (Abschnitt 4 und 7).

## 3. Entfernte UI-Komplexität und erhaltene Funktionen

Entfernt bzw. verlagert (Zahlen siehe Tabelle): Leistungskarten im Gespräch (vorher 15 Karten mit 53 `<details>`,
nachher 0 Karten, 1 Box „Ihr nächster Schritt“ mit 1 Schritt + höchstens 2 Aufgaben), Sprach- und Darstellungsschalter,
Modus-Badge und Grenztext aus der Kopfzeile (jetzt im Dialog „Einstellungen“, Kopfzeile hat nur noch dieses eine
Bedienelement), getrennte Knöpfe „Dokument hochladen“ und „Foto aufnehmen“ (jetzt ein Knopf „Dokument hinzufügen“,
`accept` mit PDF, TXT und `image/*`), ein „Vorlesen“-Knopf pro Antwort (jetzt einer für die letzte Antwort),
Quellenlisten im Gespräch (nur noch mit „Belege anzeigen“). Ebenfalls weg ist der Zähler an „Mein Plan“, eine
bewusste KISS-Entscheidung. Jede Ansicht hat genau eine sichtbare `.hauptaktion` (geprüft).

Erhalt jeder bisherigen Funktion. Die Wege sind automatisch geprüft
(`test_funktion_in_hoechstens_zwei_schritten`, `test_funktion_termin_und_dokumente_in_hoechstens_zwei_schritten`).
Gezählt wird ab dem Gespräch nach dem Pflegefall, jede Navigation oder jedes Aufklappen ist ein Schritt.

| Bisherige Funktion | Weg nachher | Schritte |
|---|---|---:|
| Nachricht senden (Enter), Rückfrage-Antworten, Vorlesen, Spracheingabe (nur mit Web Speech API) | Gespräch | 0 |
| Dokument hochladen / Foto | Gespräch bzw. Meine Akte: „Dokument hinzufügen“ | 0 |
| Nächster Schritt | Gespräch: Box „Ihr nächster Schritt“ | 0 |
| Beispielszenarien (6) | Gespräch im Leerzustand (Kacheln); im laufenden Fall Meine Akte → „Neuen Fall beginnen“ | 0 / 2 |
| Demo-Dokumente inkl. KI-Hinweis beim Foto | Gespräch im Leerzustand → „Beispiele zum Ausprobieren“ | 1 |
| Sprache, Darstellung (+ Leichte Sprache), Textgröße, Farbschema, Vorlesetempo, Modus, Grenztext mit Quelle | „Einstellungen“ | 1 |
| Quellen zu jeder Aussage | „Einstellungen“ → „Belege anzeigen“ bzw. „Belege (N)“ in Leistung/Termin | 2 |
| Fortschritt, Schritte, „Erledigt“, „Plan drucken“, „Plan vorlesen“ | Mein Plan | 1 |
| Weitere Angebote | Mein Plan → „Weitere Möglichkeiten (N)“ | 2 |
| Leistung: Kurztext, Stelle + Kontakt, Formular-Download, Unterlagen-Checkliste, Termin vorbereiten | Mein Plan → Leistung | 2 |
| Leistung: Nutzen, Details, Voraussetzungen, Region, Einrichtungen, Schrittstatus | Leistung → „Mehr zu dieser Leistung“ | 2 ab Box-Link bzw. Hash, 3 ab Plan |
| Termin: Anfragetext kopieren, Datum/Uhrzeit, .ics, erledigt, Schritte, Quellen | Mein Plan → „Termin öffnen“ | 2 (Schritte und Belege: 3) |
| Angaben ansehen/ändern/löschen, fehlende Formularangaben (füllen das PDF) | Meine Akte | 1–2 |
| Dokumentliste, Impfungen-Tabelle, Erstattungsstatus inkl. Varianten | Meine Akte (→ aufklappen) | 1–2 |
| Fall speichern, Fall laden, Neuer Fall | Meine Akte | 1 |

## 4. Tastatur-Durchgang (automatisiert, Desktop 1440 und Mobil 390, nur Tastatur)

| Schritt | Ergebnis |
|---|---|
| 1. Tab → erster Halt ist der Sprunglink, bei Fokus sichtbar; Enter → Fokus in `main` | bestanden |
| 2. Tab zur Kachel „Pflege“, Enter → Rückfrage | bestanden |
| 3. Alle Rückfragen (Wien, PVA, ÖGK, Nein – Erstantrag) per Tab + Enter; Fokus nie auf `body` | bestanden |
| 4. Navigation „Mein Plan“ → `#/plan`, Fokus auf h1, Titel und Live-Region aktualisiert | bestanden |
| 5. „Antrag vorbereiten“ → `#/leistung/pflegegeld` | bestanden |
| 6. Hauptaktion „Antrag herunterladen (PDF)“ erreichbar (`?leistung=pflegegeld`) | bestanden |
| 7. Zurück-Knopf des Browsers → „Mein Plan“, Fokus auf h1 | bestanden |
| 8. Navigation „Meine Akte“ → „Ändern Bundesland“ → Niederösterreich per Tastatur → „Speichern“, Änderung sichtbar | bestanden |
| 9. „Einstellungen“: Fokusfalle (40 Tabs im Dialog), Pfeiltasten A++ (Schrift ≥ 125 %), Farbschema „Dunkel“, Esc schließt, Fokus zurück auf „Einstellungen“ | bestanden |
| 10. Navigation „Mein Plan“ → „Plan drucken“ löst `window.print` aus | bestanden |
| Jeder Tab-Halt mit outline/box-shadow ≥ 2 px, kein Fokusverlust nach Aktionen | bestanden |

Außerdem: Fokus auf h1 und Titelwechsel bei Navigation, Hash-Routen, Zurück/Vor; Esc und Fokusrückgabe auch bei
Mausbedienung.

## 5. Weitere automatische Prüfungen (alle grün)

- **axe-core 0 Verstöße** in 13 Zuständen (Start, Gespräch nach Pflegefall, Mein Plan, Leistung, Meine Akte, Plan mit
  Termin, Termin-Ansicht, Akte mit Dokumenten, Einstellungen-Dialog; Plan, Leistung, Termin und Akte zusätzlich mit allen
  `<details>` geöffnet). Das gilt für Desktop, 390 px, 320 px und 400 % Zoom sowie für Dunkel (System-Präferenz),
  Hoher Kontrast, A++ und Leichte Sprache, jeweils bei Desktop und 320 px.
- **Hoher Kontrast ≥ 7:1:** axe-Regel `color-contrast-enhanced` liefert 0 Treffer. **Dunkel** folgt `prefers-color-scheme`.
- **Zielgröße:** WCAG 2.5.8 (≥ 24 px oder Abstands-Ausnahme) erfüllt. Designziel 44×44 px ebenfalls erfüllt, mit
  ausdrücklicher Ausnahmeliste: (a) Checkbox/Radio ≥ 24 px mit klickbarer Label-Zeile ≥ 44 px, (b) Quell-URLs als
  Textlinks in Beleg-Listen.
- **Schrift:** kein sichtbarer Text < 16 px (auch A++/320 px und Leichte Sprache).
- **Reflow:** kein horizontales Scrollen bei 320 px, 400 % Zoom, 320 px + A++ und 320 px + Leichte Sprache. Die
  Hauptaktionen liegen in der Breite und werden nicht von festen Leisten verdeckt.
- **1.4.12 Textabstände** (Zeile 1,5, Absatz 2 em, Buchstaben 0,12 em, Wörter 0,16 em): nichts abgeschnitten, kein
  Überlauf (Desktop und 320 px).
- **1.4.11 Nicht-Text-Kontrast:** Grenzen der Bedienelemente und die Fokusanzeige ≥ 3:1 im Standard-, Dunkel- und
  Kontrastmodus.
- **2.4.11 Fokus nicht verdeckt:** alle Tab-Halte in Gespräch, Plan und Akte bei 390 px und 400 % Zoom.
- **2.5.3 Beschriftung im Namen** (axe `label-content-name-mismatch`): 0 Treffer. **1.3.5:** `autocomplete` nur, wenn
  die Angaben die Person am Gerät betreffen, für Angehörige `off`. **3.1.2:** Sprachnamen tragen `lang`.
- **forced-colors:** alle Bedienelemente mit Rahmen, Fokus als outline. **prefers-reduced-motion:** keine Animation und
  keine Transition > 10 ms.
- **Keine technischen Platzhalter** („null“, „undefined“, `{…}`) im sichtbaren Text.
- **RTL:** Arabisch gibt es nur im KI-Modus. Geprüft wurde mit abgefangenen API-Antworten (gerenderte Vorlage):
  `dir=rtl`, kein Überlauf, axe 0.

## 6. Screenreader-Semantik (Accessibility-Tree, `aria_snapshot`)

Geprüft und bestanden: Landmarken `banner` (App-Name kein h1, nur „Einstellungen“), `navigation „Hauptnavigation“` mit
genau 3 Links und `aria-current="page"` (Leistung/Termin → „Mein Plan“), `main`. Je Ansicht genau ein h1. Leistung: h2
„Zuständige Stelle“ und „Unterlagen“, h3 in „Mehr zu dieser Leistung“ in fester Reihenfolge. Akte: „Ihre Angaben“, „Für
Formulare fehlen noch“, „Ihre Dokumente“. Kein Button, Link, Feld, Radio oder Schalter ohne Namen. Das Gespräch ist
`role=log`. Die Live-Region enthält die `ansage` der Antwort und meldet Ansichtswechsel. Der Dialog heißt
„Einstellungen“ und hat 5 benannte Radiogruppen mit genau einer Auswahl. Der Schalter „Belege anzeigen“ (`role=switch`)
meldet seinen Zustand über `aria-checked`. Validierung: `aria-invalid` plus Meldung über `aria-describedby`.

## 7. Funktionserhalt (automatisch, Auszug)

Kacheln senden dieselben Beispielsätze wie bisher. Demo-Dokumente funktionieren, das Foto ist ohne KI deaktiviert und
trägt den Hinweis. Weiter geprüft: Hochladen, Mikrofon nur mit Web Speech API, Vorlesen (ganze Antwort inkl. Rückfrage,
Tempo Langsam < Normal < Schnell, Stopp beim zweiten Klick, „Plan vorlesen“), Formular-Download liefert ein PDF,
eingetragene Angaben stehen im PDF, eine sensible SV-Nummer (öffentliches Musterbeispiel) erscheint weder im DOM noch
im Druck. Ebenso: Unterlagen-Checkbox und Schrittstatus bleiben gespeichert, Termin (Text kopieren in die
Zwischenablage, Datum/Uhrzeit, .ics mit `BEGIN:VCALENDAR`, erledigt), Impfungen-Tabelle, Erstattungsstatus inkl.
Varianten (Vorlage), Belege ein/aus, Fall speichern/laden, „Neuen Fall beginnen“ (mit Bestätigung), Leichte Sprache
zeigt den `leicht`-Text, Englisch, Grenzantwort bei medizinischer Frage. Druck: Navigation, Gespräch und Knöpfe
verborgen. Plan, Stellen, Unterlagen und Datum werden gedruckt. `page.pdf()` erzeugt Seiten mit dem ersten Schritt.

## 8. WCAG 2.2 AA – Kriterien

B = bestanden (automatisch geprüft), B* = bestanden laut automatischer Teilprüfung, Rest manuell zu bestätigen,
N = nicht anwendbar, M = nur manuell prüfbar.

| Kriterium | Ergebnis | Grundlage |
|---|---|---|
| 1.1.1 Nicht-Text-Inhalt | B* | axe; Symbole `aria-hidden`, Buttons benannt |
| 1.2.1–1.2.5 Zeitbasierte Medien | N | keine Audio-/Videoinhalte |
| 1.3.1 Info und Beziehungen | B* | axe, Accessibility-Tree (Landmarken, Überschriften, Listen, Tabelle, Gruppen) |
| 1.3.2 Bedeutungstragende Reihenfolge | B* | DOM-/Tab-Reihenfolge; Lesereihenfolge manuell bestätigen |
| 1.3.3 Sensorische Merkmale | M | Texte verweisen nicht auf Form/Farbe/Lage (Stichprobe) |
| 1.3.4 Ausrichtung | B* | keine Sperre; 390 px und 1440 px geprüft |
| 1.3.5 Eingabezweck | B | `autocomplete` für eigene Daten, `off` für Angehörige |
| 1.4.1 Benutzung von Farbe | B* | Status zusätzlich als Text bzw. aria-Zustand |
| 1.4.2 Audio-Steuerelement | B | Vorlesen nur auf Klick, zweiter Klick stoppt |
| 1.4.3 Kontrast (Minimum) | B | axe in allen Zuständen und Modi |
| 1.4.4 Textgröße ändern | B | A++ = 130 % ohne Verlust; Reflow bei 400 % |
| 1.4.5 Bilder von Text | N | keine |
| 1.4.10 Reflow | B | 320 CSS-px und 400 % Zoom ohne horizontales Scrollen |
| 1.4.11 Nicht-Text-Kontrast | B* | eigene Prüfung für Grenzen und Fokus; native Checkboxen und Grafiken manuell |
| 1.4.12 Textabstände | B | eigene Prüfung |
| 1.4.13 Inhalt bei Hover/Fokus | N | keine eigenen Tooltips/Popover |
| 2.1.1 Tastatur | B | Tastatur-Durchgang |
| 2.1.2 Keine Tastaturfalle | B | Dialogfalle mit Esc verlassbar, Seite zyklisch |
| 2.1.4 Tastaturkürzel | N | keine Einzeltasten-Kürzel |
| 2.2.1 Zeitbegrenzung | N | keine Fristen in der Oberfläche |
| 2.2.2 Pausieren, Beenden | N | keine bewegten Inhalte |
| 2.3.1 Drei Blitze | N | keine |
| 2.4.1 Blöcke umgehen | B | Sprunglinks, Landmarken |
| 2.4.2 Seitentitel | B | Titel je Ansicht |
| 2.4.3 Fokus-Reihenfolge | B* | Durchgang; Sinnhaftigkeit manuell |
| 2.4.4 Linkzweck | B* | „Ansehen <Titel>“, „Ändern <Angabe>“ |
| 2.4.5 Mehrere Wege | B* | Navigation + direkte Links (Box, Plan, Hash-Routen) |
| 2.4.6 Überschriften und Beschriftungen | B* | Accessibility-Tree; Verständlichkeit manuell |
| 2.4.7 Fokus sichtbar | B | jeder Tab-Halt ≥ 2 px, auch forced-colors |
| 2.4.11 Fokus nicht verdeckt (Minimum) | B | eigene Prüfung 390 px und 400 % |
| 2.5.1 Zeigergesten | N | keine Pfad-/Mehrfingergesten |
| 2.5.2 Zeigerabbruch | B* | Standard-`click` |
| 2.5.3 Beschriftung im Namen | B | axe `label-content-name-mismatch` |
| 2.5.4 Auslösung durch Bewegung | N | keine |
| 2.5.7 Ziehbewegungen | N | keine |
| 2.5.8 Zielgröße (Minimum) | B | eigene Prüfung inkl. Abstands-Ausnahme |
| 3.1.1 Sprache der Seite | B | `lang` (axe) |
| 3.1.2 Sprache von Teilen | B* | Sprachnamen mit `lang`; zitierte Originaltexte in Übersetzungen manuell |
| 3.2.1 Bei Fokus | B* | keine Kontextwechsel beim Tab-Durchgang |
| 3.2.2 Bei Eingabe | B* | Einstellungen wirken sofort im offenen Dialog (Inhalts-, kein Kontextwechsel) |
| 3.2.3 Konsistente Navigation | B | gleiche Navigation in allen Ansichten |
| 3.2.4 Konsistente Erkennung | B* | gleiche Namen für gleiche Funktionen |
| 3.2.6 Konsistente Hilfe | B* | Grenzhinweis und Dialog an gleicher Stelle |
| 3.3.1 Fehlererkennung | B | `aria-invalid` + Meldung |
| 3.3.2 Beschriftungen/Anweisungen | B | Labels, Formathinweis („Format: 4 Ziffern“) |
| 3.3.3 Fehlerempfehlung | B* | Meldung mit Format; Wortlaut manuell |
| 3.3.4 Fehlervermeidung (rechtlich, finanziell) | N | nichts wird eingereicht; „Neuen Fall beginnen“ fragt nach |
| 3.3.7 Redundante Eingabe | B | Angaben werden für Formulare wiederverwendet |
| 3.3.8 Barrierefreie Authentifizierung | N | keine Anmeldung |
| 4.1.2 Name, Rolle, Wert | B | axe + Accessibility-Tree (Schalter, Radios, Toggles) |
| 4.1.3 Statusmeldungen | B | Live-Region mit `ansage`, „Text kopiert“ als `role=status` |

## 9. Behobene Befunde während der Prüfung

Alle von QA gemeldet und von Frontend behoben, danach erneut getestet:

1. Reflow bei 320 px, A++ und 400 % (Kontaktzeilen, Schrittkarten, Checklisten-Zeilen bis 110 px Überlauf).
2. Fokusanzeige auf dem gewählten Segment-Radio unsichtbar (1,02:1).
3. Wörtliches „null“ in der Box „Ihr nächster Schritt“ bei einem Termin als nächstem Schritt.
4. Radio bei 320 px + A++ auf 23,3 px gestaucht.
5. Druck: Überschrift allein am Seitenende.
6. Klicks vor dem Anlegen der ersten Sitzung wurden still verworfen.

## 10. Offene Punkte und Grenzen dieser Prüfung

- **Keine echten Screenreader-Tests.** NVDA, JAWS, VoiceOver und TalkBack waren hier nicht verfügbar. Geprüft wurde
  der Accessibility-Tree von Chromium. Ein Mensch sollte prüfen:
  - Ansage der Live-Region bei jeder Antwort, ohne Doppelansage durch den Verlauf (`aria-live=off`),
  - Vorlesereihenfolge in Box, Plan und Akte,
  - Dialog „Einstellungen“ (Fokusfalle, Esc) mit VoiceOver/iOS und TalkBack,
  - die Datei-Auswahl „Dokument hinzufügen“ auf dem Handy (Kamera-Angebot im Auswahldialog des Systems),
  - Spracheingabe mit echter Erkennung,
  - Vorlesen mit echten Stimmen.
- **Kein Test mit Nutzerinnen und Nutzern** (ältere Menschen, Menschen mit Seh-, Motorik- oder kognitiven
  Einschränkungen). Für Leichte Sprache wird eine Prüfung durch eine Prüfgruppe empfohlen.
- **Nur Chromium.** Firefox und Safari (WebKit) wurden nicht geprüft, insbesondere Druckbild und forced-colors unter
  Windows.
- **KI-Modus nicht im Browser getestet.** Weitere Sprachen, RTL mit echten Übersetzungen und Fotos gibt es nur mit
  Schlüssel. Für RTL lief nur die gerenderte Vorlage.
- **Varianten im Erstattungsstatus:** Die Demo-Dokumente enthalten keine gemischten Boxen. Geprüft wurde mit einer
  abgefangenen Antwort (Vorlage).
- **Demo-Dokumente** stehen nur im Leerzustand im Gespräch. Ein laufender Fall bekommt Beispieldateien über „Dokument
  hinzufügen“. Das ist eine bewusste KISS-Entscheidung, keine Barriere.
- **Schritt-Zählung:** Details einer Leistung brauchen ab „Mein Plan“ 3 Schritte (Plan → Leistung → „Mehr zu dieser
  Leistung“), ab der Box bzw. per Hash 2. Ebenso brauchen Termin-Schritte und -Belege 3 Schritte. Die Vorgabe „höchstens
  2 Klicks/Ansichten“ ist damit für Ansichtswechsel erfüllt, für reine Klicks in diesen Fällen knapp nicht.
