# Nexovo – SV KI-Lotse (KI Challenge 2026, Use Case 1)

Persönlicher KI-Lotse für Versicherte im österreichischen Gesundheits- und Sozialversicherungssystem. Aus einer Situation oder einem Dokument (z. B. Entlassungsbrief) erkennt der Lotse ausdrücklich dokumentierte Empfehlungen und relevante Leistungen. Dann führt er zu den konkreten Schritten: zuständige Stelle, vorausgefülltes Formular, Unterlagen-Checkliste, Status der offenen Schritte. Jede Aussage nennt ihre Quelle.

Der Lotse stellt keine Diagnosen, interpretiert keine Befunde, bewertet keine medizinischen Risiken und gibt keine Therapie- oder Medikamentenempfehlungen.

## Stand

Planungsphase. Noch kein ausführbarer Prototyp.

- `Analyse/Plan_1_Platz.md`: Anforderungsmatrix mit Abnahmefällen, Architektur, Zeitplan, Demo-Drehbuch, Risiken
- `Analyse/Gegenpruefung.md`: Prüfprotokoll aller Plan-Aussagen gegen die Originalquellen

## Daten

Die Quelldaten (Rechtstexte der SozDok, Erstattungskodex, Leistungskataloge, Formulare, Befunde) stammen aus der SV-Box der Veranstalter. Sie liegen nicht im Repository. Lokal werden sie im Projektwurzelverzeichnis mit diesen Ordnernamen erwartet:

```
Rechtstexte/  Anträge und Formulare/  Medikamenten Erstattungskodex/  Befunde/  Leistungskataloge/
```

## Konfiguration

Zugangsdaten (z. B. `AZURE_API_KEY`) kommen ausschließlich aus Umgebungsvariablen oder einer lokalen `.env`. Die `.env` ist per `.gitignore` ausgeschlossen.

## Bekannte Einschränkungen und offene Punkte

- Die Gewichtung der Bewertungskriterien der Finaljury ist in den Unterlagen nicht angegeben.
- Layout- und OCR-Qualität der PDF-Quellen wurde nicht visuell geprüft.
- Weitere offene Punkte stehen in `Analyse/Plan_1_Platz.md`, Abschnitt 9.
