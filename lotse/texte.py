"""Alle Texte für Engine und Oberfläche, jeweils Deutsch und Englisch.

Keine Sachaussagen ohne Quelle: Diese Texte führen nur durch den Dialog. Fachliche Inhalte
(Leistungen, Beträge, Stellen) kommen aus Katalog und Wissensbasis mit Quellenangabe.
"""

from __future__ import annotations

from lotse.models import WEITERE_SPRACHEN, Quelle
from lotse.slots import SLOTS

SPRACHEN = ("de", "en")  # Basissprachen: alle Texte liegen in beiden vor
STILE = ("einfach", "ausfuehrlich", "leicht")  # leicht = Leichte Sprache (eigene Vorlagen in _LEICHT)
SPRACH_NAMEN = {"de": "Deutsch", "en": "English"}
RTL = frozenset({"ar"})

# Quelle für den Hinweis auf die telefonische Gesundheitsberatung (Serviceratgeber, PDF-S. 42).
QUELLE_1450 = Quelle(
    art="serviceratgeber",
    titel="ÖGK – Leistungen und Services 2026",
    fundstelle="PDF-S. 42",
    datei="Leistungskataloge/Serviceratgeber-2026_Broschuere_A5_OEAM_99-19_klein_korr.pdf",
    zitat="Unter der Rufnummer 1450 beraten besonders geschulte, diplomierte Krankenpflegepersonen direkt am Telefon.",
)

# Engine-Texte; Platzhalter im format()-Stil.
_ENGINE: dict[str, dict[str, str]] = {
    "begruessung": {
        "de": "Willkommen beim SV KI-Lotsen. Beschreiben Sie Ihre Situation in eigenen Worten "
              "oder laden Sie ein Dokument hoch, zum Beispiel einen Entlassungsbrief. "
              "Ich zeige Ihnen passende Leistungen, die zuständige Stelle und die nächsten Schritte – jeweils mit Quelle.",
        "en": "Welcome to the SV AI Navigator. Describe your situation in your own words "
              "or upload a document, for example a discharge letter. "
              "I will show you matching services, the responsible body and the next steps – each with a source.",
    },
    "begruessung_details": {
        "de": "Ich frage nur nach, wenn eine Angabe den nächsten Schritt verändert. "
              "Persönliche Daten wie Sozialversicherungsnummer oder Geburtsdatum tragen Sie selbst im Formular ein. "
              "Ich stelle keine Diagnosen, deute keine Befunde und empfehle keine Therapien oder Medikamente.",
        "en": "I only ask when an answer changes the next step. "
              "You enter personal data such as your social security number or date of birth in the form yourself. "
              "I do not diagnose, interpret findings or recommend treatments or medicines.",
    },
    "leer": {
        "de": "Bitte beschreiben Sie Ihr Anliegen in ein, zwei Sätzen.",
        "en": "Please describe your request in one or two sentences.",
    },
    "verstanden": {
        "de": "Ich habe Ihr Anliegen so verstanden: {szenarien}.",
        "en": "I understood your request as: {szenarien}.",
    },
    "gefunden": {
        "de": "Ich habe {k} wichtige Hilfen für Sie gefunden: {wichtigste}.",
        "en": "I found {k} important services for you: {wichtigste}.",
    },
    "gefunden_weitere": {
        "de": "Weitere Möglichkeiten stehen in Ihrem Plan.",
        "en": "More options are listed in your plan.",
    },
    "nutzen_zeile": {
        "de": "• {titel}: {nutzen} [{n}]",
        "en": "• {titel}: {nutzen} [{n}]",
    },
    "vorsorge_einleitung": {
        "de": "Für Vorsorge gibt es diese offiziellen Programme. Ob und wann eine Untersuchung für Sie in Frage kommt, "
              "besprechen Sie bitte mit Ihrer Ärztin oder Ihrem Arzt – ich bewerte kein persönliches Risiko.",
        "en": "These official prevention programmes are available. Please discuss with your doctor whether and when "
              "an examination is right for you – I do not assess personal risk.",
    },
    "gefunden_eine": {
        "de": "Ich habe eine passende Hilfe für Sie gefunden: {titel}.",
        "en": "I found one matching service for you: {titel}.",
    },
    "gefunden_keine": {
        "de": "Dazu habe ich in meinem Leistungskatalog noch keine passende Leistung.",
        "en": "My service catalogue does not contain a matching service for this yet.",
    },
    "leistung_zeile": {
        "de": "• {titel}: {kurz}",
        "en": "• {titel}: {kurz}",
    },
    "naechster": {
        "de": "Ihr nächster Schritt: {titel} – {schritt}.",
        "en": "Your next step: {titel} – {schritt}.",
    },
    "alles_erledigt": {
        "de": "Alle Schritte in Ihrem Plan sind erledigt.",
        "en": "All steps in your plan are done.",
    },
    "notiert": {
        "de": "Danke, notiert.",
        "en": "Thank you, noted.",
    },
    "uebersprungen": {
        "de": "In Ordnung, diese Angabe lasse ich offen.",
        "en": "Fine, I will leave this open.",
    },
    "nicht_verstanden": {
        "de": "Diese Antwort konnte ich nicht zuordnen.",
        "en": "I could not match this answer.",
    },
    "moegliche_antworten": {
        "de": "Mögliche Antworten: {optionen}.",
        "en": "Possible answers: {optionen}.",
    },
    "format_datum": {
        "de": "Bitte im Format TT.MM.JJJJ angeben.",
        "en": "Please use the format DD.MM.YYYY.",
    },
    "grund_region": {
        "de": "Damit ich die Angebote in Ihrer Region zeigen kann:",
        "en": "So that I can show the offers in your region:",
    },
    "grund_stelle": {
        "de": "Damit ich die zuständige Stelle nennen kann:",
        "en": "So that I can name the responsible body:",
    },
    "grund_antrag": {
        "de": "Damit ich das Formular richtig vorbereite:",
        "en": "So that I can prepare the form correctly:",
    },
    "grund_sonst": {
        "de": "Eine Frage noch:",
        "en": "One more question:",
    },
    "keine_fragen": {
        "de": "Alles beisammen. Den Antrag finden Sie in Ihrem Plan.",
        "en": "That's everything. You will find the application in your plan.",
    },
    "formular_hinweis": {
        "de": "Das Formular ist ein Entwurf. Fehlende persönliche Angaben ergänzen Sie selbst im PDF. "
              "Unterschreiben und einreichen tun Sie selbst – der Lotse versendet nichts.",
        "en": "The form is a draft. You add missing personal details in the PDF yourself. "
              "You sign and submit it yourself – the navigator sends nothing.",
    },
    "anspruch_hinweis": {
        "de": "Der Lotse prüft keinen Anspruch. Darüber entscheidet die zuständige Stelle.",
        "en": "The navigator does not decide on entitlement. The responsible body does.",
    },
    "dokument_tipp": {
        "de": "Wenn Sie den Entlassungsbrief hochladen, übernehme ich die darin ausdrücklich dokumentierten "
              "Empfehlungen wörtlich und mit Seitenangabe.",
        "en": "If you upload the discharge letter, I will take over the recommendations explicitly documented in it, "
              "word for word and with the page number.",
    },
    "dokument_gelesen": {
        "de": "Ich habe Ihr Dokument „{name}“ gelesen ({seiten}).",
        "en": "I have read your document “{name}” ({seiten}).",
    },
    "dokument_steht": {
        "de": "In Ihrem Dokument steht: „{zitat}“ (S. {seite})",
        "en": "Your document states: “{zitat}” (p. {seite})",
    },
    # Kurzfassung im Gespräch: Zahl der Empfehlungen und die erste; alle Zitate stehen in „Meine Akte“
    "dokument_empfehlung_eine": {
        "de": "Darin steht eine ausdrücklich dokumentierte Empfehlung: „{zitat}“ (S. {seite}) {marke}.",
        "en": "It contains one explicitly documented recommendation: “{zitat}” (p. {seite}) {marke}.",
    },
    "dokument_empfehlungen": {
        "de": "Darin stehen {n} ausdrücklich dokumentierte Empfehlungen, zum Beispiel: „{zitat}“ (S. {seite}) "
              "{marke}. Alle Zitate mit Seitenangabe stehen in Ihrer Akte.",
        "en": "It contains {n} explicitly documented recommendations, for example: “{zitat}” (p. {seite}) "
              "{marke}. All quotes with page numbers are in your records.",
    },
    "dokument_zitat_zeile": {
        "de": "• „{zitat}“ (S. {seite}) {marke}",
        "en": "• “{zitat}” (p. {seite}) {marke}",
    },
    "dokument_keine_empfehlung": {
        "de": "In diesem Dokument habe ich keine ausdrücklich dokumentierte Empfehlung zu einer Leistung gefunden. "
              "Offene Fragen zum Inhalt klären Sie bitte mit Ihrer Ärztin oder Ihrem Arzt.",
        "en": "I did not find any explicitly documented recommendation for a service in this document. "
              "Please discuss questions about its content with your doctor.",
    },
    "dokument_stammdaten": {
        "de": "Für das Formular habe ich {anzahl} aus dem Dokument übernommen.",
        "en": "I took {anzahl} for the form from the document.",
    },
    "dokument_fehler": {
        "de": "Dieses Dokument konnte ich nicht lesen. Bitte laden Sie eine PDF- oder Textdatei oder ein Foto "
              "(JPG, PNG, WebP) hoch.",
        "en": "I could not read this document. Please upload a PDF or text file or a photo (JPG, PNG, WebP).",
    },
    "wissen_einleitung": {
        "de": "Dazu habe ich in den Quellen gefunden:",
        "en": "Here is what I found in the sources (quotes are in German):",
    },
    "wissen_zeile": {
        "de": "„{zitat}“ – {titel}, {fundstelle} [{n}]",
        "en": "“{zitat}” – {titel}, {fundstelle} [{n}]",
    },
    "wissen_nichts": {
        "de": "Dazu habe ich in den lokalen Quellen nichts Belastbares gefunden. "
              "Bitte wenden Sie sich an Ihren Sozialversicherungsträger.",
        "en": "I found nothing reliable on this in the local sources. "
              "Please contact your social insurance provider.",
    },
    "quellen_fehlen": {
        "de": "Für diese Frage brauche ich die lokalen Rechtstexte und den Erstattungskodex (SV-Box-Daten). "
              "Sie sind in dieser Installation nicht geladen – siehe README, Abschnitt „Daten“.",
        "en": "To answer this I need the local legal texts and the reimbursement code (SV box data). "
              "They are not loaded in this installation – see README, section “Daten”.",
    },
    "wissen_tipp": {
        "de": "Sie können auch Ihre Situation beschreiben, zum Beispiel: „{beispiel}“",
        "en": "You can also describe your situation, for example: “{beispiel}”",
    },
    "pflegegeld_einleitung": {
        "de": "Pflegegeld {jahr} je Stufe:",
        "en": "Care allowance {jahr} per level:",
    },
    "pflegegeld_zeile": {
        "de": "Stufe {stufe}: {betrag} [{n}]",
        "en": "Level {stufe}: {betrag} [{n}]",
    },
    "pflegegeld_fehlt": {
        "de": "Die Pflegegeldbeträge konnte ich in den lokalen Rechtstexten nicht finden.",
        "en": "I could not find the care allowance amounts in the local legal texts.",
    },
    "ekodex_einleitung": {
        "de": "Laut Erstattungskodex:",
        "en": "According to the reimbursement code (Erstattungskodex):",
    },
    "ekodex_zeile": {
        "de": "{name} (PZN {pzn}) [{n}]:\n{erklaerung}",
        "en": "{name} (PZN {pzn}) [{n}]:\n{erklaerung}",
    },
    "ekodex_nichts": {
        "de": "Im Erstattungskodex habe ich dazu keinen Eintrag gefunden. Nennen Sie mir am besten die "
              "Pharmazentralnummer (PZN) von der Packung.",
        "en": "I found no entry in the reimbursement code. Ideally, give me the pharmacy central number (PZN) "
              "from the package.",
    },
    "status_gesetzt": {
        "de": "Status geändert: {titel} – {schritt}: {status}.",
        "en": "Status changed: {titel} – {schritt}: {status}.",
    },
    "zurueck_zur_frage": {
        "de": "Zurück zu meiner Frage:",
        "en": "Back to my question:",
    },
    "grenze_alternativen": {
        "de": "Was ich Ihnen stattdessen zeigen kann:",
        "en": "What I can show you instead:",
    },
    "wissen_angebot": {
        "de": "Ich helfe Ihnen gern bei diesen Anliegen: {szenarien}. Auch einen Arzttermin bereite ich mit Ihnen vor – "
              "schreiben Sie zum Beispiel „Ich möchte einen Arzttermin“.",
        "en": "I am happy to help with these topics: {szenarien}. I can also prepare a doctor's appointment with you – "
              "for example, write “I would like a doctor's appointment”.",
    },
    # Terminvorbereitung (Use Case 3.3)
    "termin_start": {
        "de": "Gern bereite ich den Termin mit Ihnen vor. Buchen kann ich ihn nicht – das machen Sie selbst, "
              "ich gebe Ihnen alles dafür mit.",
        "en": "I am happy to prepare the appointment with you. I cannot book it – you do that yourself, "
              "and I will give you everything you need.",
    },
    "grund_termin": {
        "de": "Damit ich den Termin passend vorbereite:",
        "en": "So that I can prepare the appointment:",
    },
    "termin_fertig": {
        "de": "Ihr Terminauftrag ist fertig: {details}.",
        "en": "Your appointment request is ready: {details}.",
    },
    "termin_nahe": {
        "de": "in der Nähe von {ort}",
        "en": "near {ort}",
    },
    "termin_wo": {
        "de": "Wo Sie den Termin bekommen: {wo}",
        "en": "Where to get the appointment: {wo}",
    },
    "termin_suche": {
        "de": "Suchen und vereinbaren: {namen} (Links in Ihrem Plan).",
        "en": "Search and book: {namen} (links in your plan).",
    },
    "termin_anfrage": {
        "de": "Den fertigen Anfragetext, Hinweise und Suchdienste finden Sie in Ihrem Plan.",
        "en": "You will find the ready-made request text, tips and search services in your plan.",
    },
    "termin_sprache_de": {
        "de": "Den Anfragetext habe ich auf Deutsch vorbereitet, damit ihn die Ordination sicher versteht.",
        "en": "I have prepared the request text in German so that the practice will understand it.",
    },
    "termin_datum_tipp": {
        "de": "Sobald Sie einen Termin haben, schreiben Sie mir zum Beispiel „Termin am 12.11.2026 um 10:30“ – dann "
              "trage ich ihn in Ihren Plan ein und erstelle einen Kalendereintrag.",
        "en": "As soon as you have an appointment, write for example “appointment on 12.11.2026 at 10:30” – I will "
              "then add it to your plan and create a calendar entry.",
    },
    "termin_vereinbart": {
        "de": "Eingetragen: {titel} am {datum}{uhrzeit}. Den Kalendereintrag (.ics) laden Sie in Ihrem Plan herunter. "
              "Vereinbart haben Sie den Termin selbst – ich habe ihn nur notiert.",
        "en": "Added: {titel} on {datum}{uhrzeit}. You can download the calendar entry (.ics) from your plan. "
              "You booked the appointment yourself – I have only noted it.",
    },
    "uhrzeit_um": {
        "de": " um {uhrzeit} Uhr",
        "en": " at {uhrzeit}",
    },
    "termin_erledigt": {
        "de": "Termin als erledigt vermerkt: {titel}.",
        "en": "Appointment marked as done: {titel}.",
    },
    "termin_unbekannt": {
        "de": "In Ihrem Plan steht noch kein Termin. Schreiben Sie zum Beispiel „Ich möchte einen Arzttermin“, "
              "dann bereite ich ihn mit Ihnen vor.",
        "en": "There is no appointment in your plan yet. Write for example “I would like a doctor's appointment” "
              "and I will prepare it with you.",
    },
    "termin_titel": {
        "de": "Termin: {anlass}",
        "en": "Appointment: {anlass}",
    },
    "termin_schritt_anfragen": {
        "de": "Termin anfragen – mit dem vorbereiteten Text per Telefon oder E-Mail",
        "en": "Request the appointment – by phone or email using the prepared text",
    },
    "termin_schritt_eintragen": {
        "de": "Vereinbarten Termin eintragen",
        "en": "Enter the booked appointment",
    },
    "termin_schritt_wahrnehmen": {
        "de": "Termin wahrnehmen",
        "en": "Attend the appointment",
    },
    "termin_beschreibung": {
        "de": "Vorbereitet mit dem SV KI-Lotsen. Den Termin haben Sie selbst vereinbart.",
        "en": "Prepared with the SV AI Navigator. You booked this appointment yourself.",
    },
    "anfrage_text": {
        "de": "Guten Tag, ich möchte gern einen Termin {anlass} vereinbaren.{zeit}{versicherung} "
              "Bitte nennen Sie mir einen freien Termin. Vielen Dank und freundliche Grüße",
        "en": "Hello, I would like to make an appointment {anlass}.{zeit}{versicherung} "
              "Please let me know when you have a free slot. Thank you and kind regards",
    },
    "anfrage_versichert": {
        "de": " Ich bin bei der {kv} versichert und bringe meine e-card mit.",
        "en": " I am insured with {kv} and will bring my e-card.",
    },
    "anfrage_ecard": {
        "de": " Meine e-card bringe ich mit.",
        "en": " I will bring my e-card.",
    },
    # Weiterverfolgen (Status des Plans bzw. der Fallakte)
    "status_einleitung": {
        "de": "Stand Ihres Plans: In Ihren wichtigsten Anliegen sind {erledigt} von {gesamt} Schritten erledigt.",
        "en": "Your plan: in your most important matters, {erledigt} of {gesamt} steps are done.",
    },
    # Erklärung kuratierter Leistungen (Sach- und Vergleichsfragen)
    "leistung_erklaerung": {
        "de": "Dazu steht in meinem Leistungskatalog, jeweils mit Quelle:",
        "en": "My service catalogue says, each with a source:",
    },
    "leistung_erklaerung_recht": {
        "de": "Passende Stellen in den Rechtsquellen:",
        "en": "Matching passages in the legal sources (quotes are in German):",
    },
    "leistung_erklaerung_angebot": {
        "de": "Wenn Sie Ihre Situation beschreiben, lege ich die passenden Leistungen mit Schritten in Ihrem Plan an.",
        "en": "If you describe your situation, I will add the matching services with steps to your plan.",
    },
    # Erstattungskodex: alle Einträge zu einem Namen
    "eko_einheitlich": {
        "de": "Alle {n} Einträge zu „{name}“ im Erstattungskodex: {box} (z. B. {beispiel}).",
        "en": "All {n} entries for “{name}” in the reimbursement code: {box} (e.g. {beispiel}).",
    },
    "eko_einheitlich_eins": {
        "de": "Ein Eintrag zu „{name}“ im Erstattungskodex: {box} ({beispiel}).",
        "en": "One entry for “{name}” in the reimbursement code: {box} ({beispiel}).",
    },
    "eko_varianten": {
        "de": "Die {n} Einträge zu „{name}“ im Erstattungskodex unterscheiden sich je nach Stärke bzw. Packung: "
              "{varianten}.",
        "en": "The {n} entries for “{name}” in the reimbursement code differ by strength or pack: {varianten}.",
    },
    "eko_variante": {
        "de": "{box}{kennzeichen} – {anzahl} (z. B. {beispiel})",
        "en": "{box}{kennzeichen} – {anzahl} (e.g. {beispiel})",
    },
    "eko_mit_kennzeichen": {
        "de": " mit Kennzeichen {kennzeichen}",
        "en": " with codes {kennzeichen}",
    },
    "eko_anzahl": {
        "de": "{n} Einträge",
        "en": "{n} entries",
    },
    "eko_anzahl_eins": {
        "de": "1 Eintrag",
        "en": "1 entry",
    },
    "medikament_zeile_alle": {
        "de": "• {name} (S. {seite}): {box} – alle {n} Einträge im Erstattungskodex {marken}",
        "en": "• {name} (p. {seite}): {box} – all {n} entries in the reimbursement code {marken}",
    },
    "medikament_zeile_eins": {
        "de": "• {name} (S. {seite}): {box} – 1 Eintrag im Erstattungskodex {marken}",
        "en": "• {name} (p. {seite}): {box} – 1 entry in the reimbursement code {marken}",
    },
    "medikament_zeile_varianten": {
        "de": "• {name} (S. {seite}): je nach Stärke bzw. Packung unterschiedlich – {varianten} {marken}",
        "en": "• {name} (p. {seite}): differs by strength or pack – {varianten} {marken}",
    },
    "status_zeile": {
        "de": "• {titel}: {erledigt} von {gesamt} erledigt – nächster Schritt: {schritt}",
        "en": "• {titel}: {erledigt} of {gesamt} done – next step: {schritt}",
    },
    "status_zeile_fertig": {
        "de": "• {titel}: alle Schritte erledigt",
        "en": "• {titel}: all steps done",
    },
    "status_termin_vorbereitet": {
        "de": "• {titel}: vorbereitet, noch nicht vereinbart",
        "en": "• {titel}: prepared, not yet booked",
    },
    "status_termin_vereinbart": {
        "de": "• {titel}: vereinbart am {datum}{uhrzeit}",
        "en": "• {titel}: booked for {datum}{uhrzeit}",
    },
    "status_termin_erledigt": {
        "de": "• {titel}: erledigt",
        "en": "• {titel}: done",
    },
    "status_leer": {
        "de": "Ihr Plan ist noch leer. Beschreiben Sie Ihre Situation, dann lege ich die passenden Leistungen an.",
        "en": "Your plan is still empty. Describe your situation and I will add the matching services.",
    },
    "wiederhergestellt": {
        "de": "Ihr Fall ist wiederhergestellt.",
        "en": "Your case has been restored.",
    },
    # Fotos, Impfeinträge, Medikamente
    "bild_ki_inaktiv": {
        "de": "Fotos kann ich nur im KI-Modus lesen, und der ist gerade nicht aktiv. Bitte laden Sie das Dokument "
              "als PDF- oder Textdatei hoch.",
        "en": "I can only read photos in AI mode, which is not active right now. Please upload the document "
              "as a PDF or text file.",
    },
    "bild_format": {
        "de": "Dieses Bildformat kann ich nicht lesen (zum Beispiel HEIC oder GIF). Bitte speichern Sie das Foto als "
              "JPG, PNG oder WebP oder laden Sie ein PDF hoch.",
        "en": "I cannot read this image format (for example HEIC or GIF). Please save the photo as JPG, PNG or WebP "
              "or upload a PDF.",
    },
    "bild_unlesbar": {
        "de": "Auf dem Foto konnte ich keinen Text lesen. Bitte fotografieren Sie das Dokument gerade, scharf und gut "
              "beleuchtet – oder laden Sie ein PDF hoch.",
        "en": "I could not read any text in the photo. Please photograph the document straight, in focus and well lit "
              "– or upload a PDF.",
    },
    "dokument_transkribiert": {
        "de": "Text per KI aus dem Foto abgeschrieben – Zitate beziehen sich auf die Abschrift.",
        "en": "Text transcribed from the photo by AI – quotes refer to the transcript.",
    },
    # Kurzfassung im Gespräch; die einzelnen Einträge stehen in „Meine Akte“ (ausführlich auch im Gespräch)
    "impfungen_kurz_impfpass": {
        "de": "Laut Ihrem Impfpass dokumentiert: {anzahl} (nur abgeschrieben, keine Bewertung). "
              "Die Liste steht in Ihrer Akte.",
        "en": "Documented in your vaccination record: {anzahl} (copied only, not assessed). "
              "The list is in your records.",
    },
    "impfungen_kurz": {
        "de": "Laut Ihrem Dokument dokumentiert: {anzahl} (nur abgeschrieben, keine Bewertung). "
              "Die Liste steht in Ihrer Akte.",
        "en": "Documented in your document: {anzahl} (copied only, not assessed). The list is in your records.",
    },
    "impfung_zeile": {
        "de": "• {impfung}: {datum} (S. {seite})",
        "en": "• {impfung}: {datum} (p. {seite})",
    },
    "impfungen_arzt": {
        "de": "Welche Impfungen Sie brauchen, klären Sie bitte mit Ihrer Ärztin oder Ihrem Arzt.",
        "en": "Please ask your doctor which vaccinations you need.",
    },
    "medikamente_kurz": {
        "de": "Für {anzahl} aus dem Dokument steht der Erstattungsstatus laut Erstattungskodex in Ihrer Akte – "
              "keine Empfehlung zu Einnahme, Wechsel oder Dosierung.",
        "en": "For {anzahl} named in the document, the reimbursement status from the reimbursement code is in your "
              "records – no advice on taking, switching or dosage.",
    },
    "medikament_nicht_gefunden": {
        "de": "• {name} (S. {seite}): im Erstattungskodex nicht gefunden",
        "en": "• {name} (p. {seite}): not found in the reimbursement code",
    },
    "formular_region_hinweis": {
        "de": "Dieses Formular gilt nur in: {regionen}.",
        "en": "This form only applies in: {regionen}.",
    },
    "uebersetzung_fehlt": {
        "de": "Die Übersetzung ist gerade nicht verfügbar – Teile dieser Antwort stehen auf Englisch.",
        "en": "Translation is not available right now – parts of this answer are shown in English.",
    },
    # Angaben ändern („Mein Plan“ → „Ihre Angaben“)
    "geaendert": {
        "de": "Geändert: {label} – {wert}.",
        "en": "Changed: {label} – {wert}.",
    },
    "geaendert_sensibel": {
        "de": "Geändert: {label}. Diesen Wert speichere ich nicht dauerhaft; er kommt nur in den Formularentwurf.",
        "en": "Changed: {label}. I do not store this value permanently; it only goes into the draft form.",
    },
    "geloescht": {
        "de": "Gelöscht: {label}.",
        "en": "Deleted: {label}.",
    },
    # Prüfmeldungen beim Ändern einer Angabe (ohne Anführungszeichen im Englischen, damit sie übersetzbar bleiben)
    "angabe_unbekannt": {
        "de": "Diese Angabe kann hier nicht geändert werden.",
        "en": "This detail cannot be changed here.",
    },
    "angabe_auswahl": {
        "de": "Bitte wählen Sie für „{label}“ eine der angebotenen Möglichkeiten.",
        "en": "Please choose one of the options for {label}.",
    },
    "angabe_datum": {
        "de": "Bitte prüfen Sie „{label}“. Geben Sie ein gültiges Datum im Format {muster} ein.",
        "en": "Please check {label}. Enter a valid date in the format {muster}.",
    },
    "angabe_muster": {
        "de": "Bitte prüfen Sie „{label}“. Erwartet: {muster}.",
        "en": "Please check {label}. Expected: {muster}.",
    },
    "angabe_ungueltig": {
        "de": "Bitte prüfen Sie Ihre Eingabe bei „{label}“.",
        "en": "Please check your entry for {label}.",
    },
    # Kurze Ansage für Screenreader (eine Zeile je Antwort, in jeder Darstellung gleich)
    "ansage_start": {
        "de": "Willkommen. Beschreiben Sie Ihre Situation oder laden Sie ein Dokument hoch.",
        "en": "Welcome. Describe your situation or upload a document.",
    },
    "ansage_gefunden": {
        "de": "{n} wichtige Hilfen gefunden.",
        "en": "{n} important services found.",
    },
    "ansage_gefunden_eine": {
        "de": "Eine passende Hilfe gefunden.",
        "en": "One matching service found.",
    },
    "ansage_gefunden_keine": {
        "de": "Keine passende Hilfe gefunden.",
        "en": "No matching service found.",
    },
    "ansage_notiert": {
        "de": "Notiert.",
        "en": "Noted.",
    },
    "ansage_abschluss": {
        "de": "Alle Fragen beantwortet.",
        "en": "All questions answered.",
    },
    "ansage_geaendert": {
        "de": "Gespeichert: {label} – {wert}.",
        "en": "Saved: {label} – {wert}.",
    },
    "ansage_geaendert_sensibel": {
        "de": "Gespeichert: {label}.",
        "en": "Saved: {label}.",
    },
    "ansage_geloescht": {
        "de": "Gelöscht: {label}.",
        "en": "Deleted: {label}.",
    },
    "ansage_naechster": {
        "de": "Nächster Schritt: {titel} – {schritt}.",
        "en": "Next step: {titel} – {schritt}.",
    },
    "ansage_naechster_titel": {
        "de": "Nächster Schritt: {titel}.",
        "en": "Next step: {titel}.",
    },
    "ansage_alles_erledigt": {
        "de": "Alle Schritte erledigt.",
        "en": "All steps done.",
    },
    "ansage_frage": {
        "de": "Eine Frage an Sie.",
        "en": "One question for you.",
    },
    "ansage_grenze": {
        "de": "Medizinische Frage. Das kann ich nicht beurteilen. Bitte fragen Sie Ihre Ärztin oder Ihren Arzt.",
        "en": "Medical question. I cannot assess this. Please ask your doctor.",
    },
    "ansage_wissen": {
        "de": "Antwort mit {n} Quellen.",
        "en": "Answer with {n} sources.",
    },
    "ansage_wissen_eine": {
        "de": "Antwort mit einer Quelle.",
        "en": "Answer with one source.",
    },
    "ansage_status": {
        "de": "Stand: {erledigt} von {gesamt} Schritten erledigt.",
        "en": "Progress: {erledigt} of {gesamt} steps done.",
    },
    "ansage_status_gesetzt": {
        "de": "Status gespeichert: {status}.",
        "en": "Status saved: {status}.",
    },
    "ansage_termin_start": {
        "de": "Terminvorbereitung gestartet.",
        "en": "Appointment preparation started.",
    },
    "ansage_termin_fertig": {
        "de": "Ihr Terminauftrag ist fertig.",
        "en": "Your appointment request is ready.",
    },
    "ansage_termin_eingetragen": {
        "de": "Termin eingetragen: {datum}{uhrzeit}.",
        "en": "Appointment added: {datum}{uhrzeit}.",
    },
    "ansage_termin_erledigt": {
        "de": "Termin als erledigt vermerkt.",
        "en": "Appointment marked as done.",
    },
    "ansage_dokument": {
        "de": "Dokument gelesen.",
        "en": "Document read.",
    },
    "ansage_wiederhergestellt": {
        "de": "Ihr Fall ist geladen.",
        "en": "Your case is loaded.",
    },
    "ansage_einstellungen": {
        "de": "Einstellungen gespeichert: {sprachname}, {darstellung}.",
        "en": "Settings saved: {sprachname}, {darstellung}.",
    },
}

# Leichte Sprache (stil "leicht"): gleiche Schlüssel und Platzhalter wie _ENGINE, gleiche Aussage. Kurze Sätze mit je
# einer Aussage, höchstens 12 Wörter, keine Abkürzungen wie „z. B.“; Fachwörter werden im Satz erklärt. Keine neuen
# Fakten: Fachliches kommt weiter nur aus Katalog und Quellen. Fehlt ein Schlüssel, gilt der Text aus _ENGINE.
_LEICHT: dict[str, dict[str, str]] = {
    "begruessung": {
        "de": "Willkommen! Ich bin der Lotse für die Sozialversicherung. Schreiben Sie in eigenen Worten: "
              "Worum geht es? Sie können auch ein Dokument hochladen. Zum Beispiel einen Brief vom Spital. "
              "Ich zeige Ihnen passende Hilfen. Ich zeige Ihnen auch die nächsten Schritte. "
              "Bei jeder Aussage steht die Quelle.",
        "en": "Welcome! I am the guide for social insurance. Tell me in your own words: "
              "What is it about? You can also upload a document. For example a letter from the hospital. "
              "I show you help that fits. I also show you the next steps. "
              "Every statement has a source.",
    },
    "leer": {
        "de": "Bitte schreiben Sie Ihr Anliegen. Ein oder zwei Sätze reichen.",
        "en": "Please write what you need. One or two sentences are enough.",
    },
    "verstanden": {
        "de": "Ich habe verstanden. Es geht um: {szenarien}.",
        "en": "I understood. This is about: {szenarien}.",
    },
    "gefunden": {
        "de": "Ich habe {k} wichtige Hilfen für Sie gefunden: {wichtigste}.",
        "en": "I found {k} important services for you: {wichtigste}.",
    },
    "gefunden_weitere": {
        "de": "Weitere Hilfen stehen in Ihrem Plan.",
        "en": "More services are in your plan.",
    },
    "gefunden_eine": {
        "de": "Ich habe eine passende Hilfe gefunden: {titel}.",
        "en": "I found one service that fits: {titel}.",
    },
    "gefunden_keine": {
        "de": "Dafür kenne ich noch keine passende Hilfe.",
        "en": "I do not know a service for this yet.",
    },
    "vorsorge_einleitung": {
        "de": "Für die Vorsorge gibt es diese Programme. Fragen Sie Ihre Ärztin oder Ihren Arzt: "
              "Passt eine Untersuchung für Sie? Ich bewerte kein persönliches Risiko.",
        "en": "There are these programmes for prevention. Ask your doctor: "
              "Is an examination right for you? I do not assess your personal risk.",
    },
    "naechster": {
        "de": "Ihr nächster Schritt: {titel} – {schritt}.",
        "en": "Your next step: {titel} – {schritt}.",
    },
    "alles_erledigt": {
        "de": "Sie haben alle Schritte erledigt.",
        "en": "You have done all steps.",
    },
    "notiert": {
        "de": "Danke. Ich habe das notiert.",
        "en": "Thank you. I wrote that down.",
    },
    "uebersprungen": {
        "de": "Gut. Diese Frage lasse ich offen.",
        "en": "All right. I will leave this question open.",
    },
    "nicht_verstanden": {
        "de": "Diese Antwort habe ich nicht verstanden.",
        "en": "I did not understand this answer.",
    },
    "moegliche_antworten": {
        "de": "Sie können so antworten: {optionen}.",
        "en": "You can answer like this: {optionen}.",
    },
    "format_datum": {
        "de": "Bitte schreiben Sie das Datum so: Tag, Monat, Jahr. Zum Beispiel: 05.03.1950.",
        "en": "Please write the date like this: day, month, year. For example: 05.03.1950.",
    },
    "grund_region": {
        "de": "Ich möchte Ihnen Hilfen in Ihrer Region zeigen.",
        "en": "I want to show you help in your region.",
    },
    "grund_stelle": {
        "de": "Ich möchte Ihnen die richtige Stelle nennen.",
        "en": "I want to tell you the right office.",
    },
    "grund_antrag": {
        "de": "Ich möchte das Formular richtig vorbereiten.",
        "en": "I want to prepare the form correctly.",
    },
    "grund_sonst": {
        "de": "Ich habe noch eine Frage.",
        "en": "I have one more question.",
    },
    "grund_termin": {
        "de": "Ich möchte den Termin gut vorbereiten.",
        "en": "I want to prepare the appointment well.",
    },
    "zurueck_zur_frage": {
        "de": "Zurück zu meiner Frage.",
        "en": "Back to my question.",
    },
    "keine_fragen": {
        "de": "Jetzt ist alles da. Den Antrag finden Sie in Ihrem Plan.",
        "en": "Now everything is there. You find the application in your plan.",
    },
    "dokument_tipp": {
        "de": "Haben Sie einen Brief vom Spital? Dann laden Sie ihn hoch. "
              "Ich übernehme nur klar geschriebene Empfehlungen. Ich schreibe sie wörtlich ab. Ich nenne auch die Seite.",
        "en": "Do you have a letter from the hospital? Then upload it. "
              "I only take clearly written recommendations. I copy them word for word. I also name the page.",
    },
    "dokument_gelesen": {
        "de": "Ich habe Ihr Dokument „{name}“ gelesen. Es hat {seiten}.",
        "en": "I have read your document “{name}”. It has {seiten}.",
    },
    "dokument_steht": {
        "de": "In Ihrem Dokument steht: „{zitat}“ (Seite {seite})",
        "en": "Your document says: “{zitat}” (page {seite})",
    },
    "dokument_empfehlung_eine": {
        "de": "Im Dokument steht eine klare Empfehlung: „{zitat}“ (Seite {seite}) {marke}.",
        "en": "The document has one clear recommendation: “{zitat}” (page {seite}) {marke}.",
    },
    "dokument_empfehlungen": {
        "de": "Im Dokument stehen {n} klare Empfehlungen. Ein Beispiel: „{zitat}“ (Seite {seite}) {marke}. "
              "Alle Zitate stehen in Ihrer Akte.",
        "en": "The document has {n} clear recommendations. One example: “{zitat}” (page {seite}) {marke}. "
              "All quotes are in your records.",
    },
    "dokument_zitat_zeile": {
        "de": "• „{zitat}“ (Seite {seite}) {marke}",
        "en": "• “{zitat}” (page {seite}) {marke}",
    },
    "dokument_keine_empfehlung": {
        "de": "In diesem Dokument steht keine klare Empfehlung für eine Hilfe. Haben Sie Fragen zum Inhalt? "
              "Dann fragen Sie Ihre Ärztin oder Ihren Arzt.",
        "en": "This document has no clear recommendation for a service. Do you have questions about the content? "
              "Then ask your doctor.",
    },
    "dokument_stammdaten": {
        "de": "Ich habe {anzahl} für das Formular übernommen.",
        "en": "I took {anzahl} for the form.",
    },
    "dokument_fehler": {
        "de": "Ich kann dieses Dokument nicht lesen. Bitte laden Sie eine andere Datei hoch. "
              "Das geht: PDF, Text-Datei oder Foto. Fotos bitte als JPG, PNG oder WebP.",
        "en": "I cannot read this document. Please upload another file. "
              "These work: PDF, text file or photo. Photos please as JPG, PNG or WebP.",
    },
    "dokument_transkribiert": {
        "de": "Die künstliche Intelligenz hat den Text vom Foto abgeschrieben. Die Zitate kommen aus dieser Abschrift.",
        "en": "The artificial intelligence copied the text from the photo. The quotes come from this copy.",
    },
    "wissen_einleitung": {
        "de": "Das habe ich in den Quellen gefunden:",
        "en": "This is what I found in the sources. The quotes are in German:",
    },
    "wissen_nichts": {
        "de": "Dazu habe ich keine sichere Quelle gefunden. Bitte fragen Sie Ihre Sozialversicherung.",
        "en": "I found no reliable source for this. Please ask your social insurance.",
    },
    "quellen_fehlen": {
        "de": "Für diese Frage fehlen mir Daten. Es fehlen die Gesetze und der Erstattungskodex. "
              "Mehr dazu steht in der Datei README. Der Abschnitt heißt „Daten“.",
        "en": "Data is missing for this question. The laws and the reimbursement code are missing. "
              "The file README tells you more. The section is called “Daten”.",
    },
    "wissen_tipp": {
        "de": "Sie können auch Ihre Situation beschreiben. Zum Beispiel: „{beispiel}“",
        "en": "You can also describe your situation. For example: “{beispiel}”",
    },
    "wissen_angebot": {
        "de": "Ich helfe Ihnen gern bei diesen Themen: {szenarien}. Ich helfe auch bei einem Arzttermin. "
              "Schreiben Sie dafür: „Ich möchte einen Arzttermin“.",
        "en": "I am happy to help with these topics: {szenarien}. I can also help with a doctor's appointment. "
              "Just write: “I would like a doctor's appointment”.",
    },
    "pflegegeld_einleitung": {
        "de": "So viel Pflegegeld gibt es {jahr} in jeder Stufe:",
        "en": "This is the care allowance in {jahr} for each level:",
    },
    "pflegegeld_fehlt": {
        "de": "Ich habe die Beträge für das Pflegegeld nicht gefunden.",
        "en": "I did not find the amounts of care allowance.",
    },
    "ekodex_einleitung": {
        "de": "Das steht im Erstattungskodex:",
        "en": "This is in the reimbursement code:",
    },
    "ekodex_nichts": {
        "de": "Dazu habe ich im Erstattungskodex nichts gefunden. Nennen Sie mir bitte die Pharmazentralnummer. "
              "Die Nummer steht auf der Packung.",
        "en": "I found nothing about this in the reimbursement code. Please tell me the pharmacy central number. "
              "It is on the package.",
    },
    "status_gesetzt": {
        "de": "Gespeichert: {titel} – {schritt}. Neuer Stand: {status}.",
        "en": "Saved: {titel} – {schritt}. New status: {status}.",
    },
    "grenze_alternativen": {
        "de": "Dabei kann ich Ihnen helfen:",
        "en": "I can help you with this:",
    },
    "termin_start": {
        "de": "Gern bereite ich den Termin mit Ihnen vor. Ich kann den Termin nicht buchen. "
              "Das machen Sie selbst. Ich gebe Ihnen alles dafür mit.",
        "en": "I am happy to prepare the appointment with you. I cannot book the appointment. "
              "You do that yourself. I give you everything you need.",
    },
    "termin_fertig": {
        "de": "Ihr Termin-Auftrag ist fertig: {details}.",
        "en": "Your appointment request is ready: {details}.",
    },
    "termin_wo": {
        "de": "Hier bekommen Sie den Termin: {wo}",
        "en": "Where you get the appointment: {wo}",
    },
    "termin_suche": {
        "de": "Hier können Sie suchen: {namen}. Die Links stehen in Ihrem Plan.",
        "en": "You can search here: {namen}. The links are in your plan.",
    },
    "termin_anfrage": {
        "de": "Den fertigen Text für Ihre Anfrage finden Sie in Ihrem Plan. Dort stehen auch Hinweise und Suchdienste.",
        "en": "You find the ready-made request text in your plan. Tips and search services are there too.",
    },
    "termin_sprache_de": {
        "de": "Den Text habe ich auf Deutsch geschrieben. So versteht ihn die Praxis sicher.",
        "en": "I wrote the text in German. That way the practice will understand it.",
    },
    "termin_datum_tipp": {
        "de": "Haben Sie einen Termin bekommen? Dann schreiben Sie mir Datum und Uhrzeit. "
              "Zum Beispiel: „Termin am 12.11.2026 um 10:30“. Ich trage den Termin in Ihren Plan ein. "
              "Dann bekommen Sie einen Eintrag für Ihren Kalender.",
        "en": "Did you get an appointment? Then write me the date and time. "
              "For example: “appointment on 12.11.2026 at 10:30”. I add the appointment to your plan. "
              "Then you get an entry for your calendar.",
    },
    "termin_vereinbart": {
        "de": "Ich habe eingetragen: {titel} am {datum}{uhrzeit}. Den Eintrag für Ihren Kalender finden Sie in "
              "Ihrem Plan. Den Termin haben Sie selbst vereinbart. Ich habe ihn nur notiert.",
        "en": "I added: {titel} on {datum}{uhrzeit}. You find the entry for your calendar in your plan. "
              "You booked the appointment yourself. I only wrote it down.",
    },
    "termin_erledigt": {
        "de": "Erledigt: {titel}.",
        "en": "Done: {titel}.",
    },
    "termin_unbekannt": {
        "de": "In Ihrem Plan steht noch kein Termin. Schreiben Sie zum Beispiel: „Ich möchte einen Arzttermin“. "
              "Dann bereite ich den Termin mit Ihnen vor.",
        "en": "There is no appointment in your plan yet. Write for example: “I would like a doctor's appointment”. "
              "Then I will prepare it with you.",
    },
    "status_einleitung": {
        "de": "So weit sind Sie: {erledigt} von {gesamt} Schritten sind erledigt.",
        "en": "Your progress: {erledigt} of {gesamt} steps are done.",
    },
    "status_zeile": {
        "de": "• {titel}: {erledigt} von {gesamt} erledigt. Als Nächstes: {schritt}",
        "en": "• {titel}: {erledigt} of {gesamt} done. Next: {schritt}",
    },
    "status_zeile_fertig": {
        "de": "• {titel}: alles erledigt",
        "en": "• {titel}: all done",
    },
    "status_termin_vorbereitet": {
        "de": "• {titel}: vorbereitet, noch kein Termin",
        "en": "• {titel}: prepared, no appointment yet",
    },
    "status_termin_vereinbart": {
        "de": "• {titel}: Termin am {datum}{uhrzeit}",
        "en": "• {titel}: appointment on {datum}{uhrzeit}",
    },
    "status_leer": {
        "de": "Ihr Plan ist noch leer. Beschreiben Sie Ihre Situation. Dann zeige ich Ihnen passende Hilfen.",
        "en": "Your plan is still empty. Describe your situation. Then I show you services that fit.",
    },
    "wiederhergestellt": {
        "de": "Ihr Fall ist wieder da.",
        "en": "Your case is back.",
    },
    "leistung_erklaerung": {
        "de": "Das steht in meiner Liste der Hilfen. Bei jeder Hilfe steht die Quelle:",
        "en": "This is in my list of services. Each one has a source:",
    },
    "leistung_erklaerung_recht": {
        "de": "Dazu steht in den Gesetzen:",
        "en": "The laws say this. The quotes are in German:",
    },
    "leistung_erklaerung_angebot": {
        "de": "Beschreiben Sie Ihre Situation. Dann trage ich passende Hilfen in Ihren Plan ein. "
              "Mit allen Schritten.",
        "en": "Describe your situation. Then I add services that fit to your plan. With all steps.",
    },
    "bild_ki_inaktiv": {
        "de": "Fotos kann ich nur im KI-Modus lesen. KI heißt künstliche Intelligenz. Der KI-Modus ist gerade aus. "
              "Bitte laden Sie das Dokument als PDF hoch. Oder als Text-Datei.",
        "en": "I can only read photos in AI mode. AI means artificial intelligence. AI mode is off right now. "
              "Please upload the document as a PDF. Or as a text file.",
    },
    "bild_format": {
        "de": "Dieses Bild-Format kann ich nicht lesen. Bitte speichern Sie das Foto als JPG, PNG oder WebP. "
              "Oder laden Sie ein PDF hoch.",
        "en": "I cannot read this picture format. Please save the photo as JPG, PNG or WebP. Or upload a PDF.",
    },
    "bild_unlesbar": {
        "de": "Auf dem Foto kann ich keinen Text lesen. Bitte machen Sie ein neues Foto. "
              "Das Dokument soll gerade liegen. Das Foto soll scharf und hell sein. Oder laden Sie ein PDF hoch.",
        "en": "I cannot read any text on the photo. Please take a new photo. "
              "The document should lie straight. The photo should be sharp and bright. Or upload a PDF.",
    },
    "impfungen_kurz_impfpass": {
        "de": "Ihr Impfpass nennt {anzahl}. Ich habe die Einträge nur abgeschrieben. Ich bewerte sie nicht. "
              "Die Liste steht in Ihrer Akte.",
        "en": "Your vaccination record lists {anzahl}. I only copied the entries. I do not assess them. "
              "The list is in your records.",
    },
    "impfungen_kurz": {
        "de": "Ihr Dokument nennt {anzahl}. Ich habe die Einträge nur abgeschrieben. Ich bewerte sie nicht. "
              "Die Liste steht in Ihrer Akte.",
        "en": "Your document lists {anzahl}. I only copied the entries. I do not assess them. "
              "The list is in your records.",
    },
    "impfung_zeile": {
        "de": "• {impfung}: {datum} (Seite {seite})",
        "en": "• {impfung}: {datum} (page {seite})",
    },
    "impfungen_arzt": {
        "de": "Welche Impfungen brauchen Sie? Das sagt Ihnen Ihre Ärztin oder Ihr Arzt.",
        "en": "Which vaccinations do you need? Your doctor will tell you.",
    },
    "medikamente_kurz": {
        "de": "Im Dokument stehen {anzahl}. Ihr Eintrag im Erstattungskodex steht in Ihrer Akte. "
              "Ich gebe keine Empfehlung zur Einnahme. Ich gebe keine Empfehlung zur Dosis.",
        "en": "The document names {anzahl}. Their entry in the reimbursement code is in your records. "
              "I give no advice on taking them. I give no advice on the dose.",
    },
    "geaendert": {
        "de": "Ich habe geändert: {label} – {wert}.",
        "en": "I changed: {label} – {wert}.",
    },
    "geaendert_sensibel": {
        "de": "Ich habe geändert: {label}. Diesen Wert speichere ich nicht dauerhaft. Er kommt nur in das Formular.",
        "en": "I changed: {label}. I do not store this value for long. It only goes into the form.",
    },
    "geloescht": {
        "de": "Ich habe gelöscht: {label}.",
        "en": "I deleted: {label}.",
    },
}

# Rückfragen in Leichter Sprache (gleiche Frage wie slots.SLOTS[...].frage, kürzer); sonst gilt die Slot-Frage.
FRAGE_LEICHT: dict[str, dict[str, str]] = {
    "anliegen.fuer_wen": {
        "de": "Geht es um Sie selbst? Oder geht es um eine Person aus Ihrer Familie?",
        "en": "Is this about you? Or is it about someone in your family?",
    },
    "person.bundesland": {
        "de": "In welchem Bundesland wohnt die Person?",
        "en": "Which federal state does the person live in?",
    },
    "versicherung.krankenversicherung": {
        "de": "Bei welcher Krankenkasse ist die Person versichert? Zum Beispiel die Gesundheitskasse ÖGK, die SVS "
              "oder die BVAEB.",
        "en": "Which health insurance does the person have? For example the health insurance fund ÖGK, the SVS "
              "or the BVAEB.",
    },
    "versicherung.pension": {
        "de": "Bekommt die Person eine Pension? Wer zahlt die Pension? Zum Beispiel die Pensionsversicherung PVA, "
              "die SVS oder die BVAEB.",
        "en": "Does the person get a pension? Who pays the pension? For example the pension insurance PVA, the SVS "
              "or the BVAEB.",
    },
    "pflege.stufe": {
        "de": "Welche Pflegegeld-Stufe hat die Person jetzt? Es gibt die Stufen 1 bis 7.",
        "en": "Which care level does the person have now? There are levels 1 to 7.",
    },
    "kind.alter": {
        "de": "Wie alt ist das Kind? Bitte in Jahren.",
        "en": "How old is the child? Please in years.",
    },
    "person.geschlecht": {
        "de": "Welches Geschlecht soll im Antrag stehen?",
        "en": "Which gender should be on the form?",
    },
    "reha.form": {
        "de": "Was steht im ärztlichen Dokument? Ambulante oder stationäre Reha?",
        "en": "What does the medical document say? Outpatient or inpatient rehab?",
    },
    "termin.anlass": {
        "de": "Wofür ist der Termin? Zum Beispiel Vorsorge, Kontrolle, Impfung oder Zahnarzt.",
        "en": "What is the appointment for? For example check-up, follow-up, vaccination or dentist.",
    },
    "termin.ort": {
        "de": "Wo soll der Termin sein? Bitte nennen Sie einen Ort oder Bezirk.",
        "en": "Where should the appointment be? Please name a town or district.",
    },
    "termin.zeit": {
        "de": "Wann passt es Ihnen besser? Am Vormittag oder am Nachmittag?",
        "en": "What suits you better? Mornings or afternoons?",
    },
}

# Eingabehilfe für Formularfelder (Angaben ändern, fehlende Angaben); "" = freie Eingabe bzw. Auswahl
MUSTER_HINWEIS: dict[str, dict[str, str]] = {
    "termin.uhrzeit": {"de": "HH:MM", "en": "HH:MM"},
    "person.svnr": {"de": "10 Ziffern", "en": "10 digits"},
    "person.plz": {"de": "4 Ziffern", "en": "4 digits"},
    "bank.iban": {"de": "AT und 18 Ziffern", "en": "AT and 18 digits"},
    "pflege.stufe": {"de": "Zahl von 1 bis 7", "en": "number from 1 to 7"},
    "kind.alter": {"de": "Alter in Jahren", "en": "age in years"},
}
DATUM_HINWEIS = {"de": "TT.MM.JJJJ", "en": "DD.MM.YYYY"}

# Zählwörter für kurze Zusammenfassungen („3 Impfungen“, „1 Angabe“): (Einzahl, Mehrzahl) je Sprache
_ZAEHLWORT: dict[str, dict[str, tuple[str, str]]] = {
    "seite": {"de": ("Seite", "Seiten"), "en": ("page", "pages")},
    "angabe": {"de": ("Angabe", "Angaben"), "en": ("detail", "details")},
    "impfung": {"de": ("Impfung", "Impfungen"), "en": ("vaccination", "vaccinations")},
    "medikament": {"de": ("Medikament", "Medikamente"), "en": ("medicine", "medicines")},
}

SZENARIO_LABEL: dict[str, dict[str, str]] = {
    "pflege": {"de": "Pflege und Betreuung", "en": "Care and support"},
    "gesundheit": {"de": "Gesundheitsförderung und Vorsorge", "en": "Health promotion and prevention"},
    "entlassung": {"de": "Nach dem Spitalsaufenthalt", "en": "After a hospital stay"},
    "kind": {"de": "Angebote rund ums Kind", "en": "Offers for children and families"},
    "unterstuetzung": {"de": "Soziale und finanzielle Unterstützung", "en": "Social and financial support"},
}

# Beispielsätze der Bewertungsszenarien plus Terminvorbereitung.
BEISPIELE: dict[str, dict[str, str]] = {
    "pflege": {
        "de": "Meine Mutter ist chronisch krank und kommt allein nicht mehr zurecht",
        "en": "My mother is chronically ill and can no longer manage on her own",
    },
    "gesundheit": {
        "de": "Ich möchte etwas für meine Gesundheit tun",
        "en": "I would like to do something for my health",
    },
    "entlassung": {
        "de": "Ich habe einen Befund/Entlassungsbrief bekommen – was muss ich jetzt erledigen?",
        "en": "I have received a medical report/discharge letter – what do I need to do now?",
    },
    "kind": {
        "de": "Ich habe ein Kind und möchte wissen, welche Angebote es gibt",
        "en": "I have a child and would like to know which offers are available",
    },
    "unterstuetzung": {
        "de": "Ich kann mir die Miete kaum noch leisten – welche Unterstützung gibt es?",
        "en": "I can barely afford my rent – what support is available?",
    },
    "termin": {
        "de": "Ich brauche einen Termin für eine Vorsorgeuntersuchung",
        "en": "I need an appointment for a check-up",
    },
}

BOX_LABEL: dict[str, dict[str, str]] = {
    "gruen": {"de": "Grüne Box", "en": "green box"},
    "gelb": {"de": "Gelbe Box", "en": "yellow box"},
}

# Bausteine des Anfragetexts für Termine (Formulierung der Person, keine Sachaussage)
ANFRAGE_ANLASS: dict[str, dict[str, str]] = {
    "vorsorge": {"de": "für eine Vorsorgeuntersuchung", "en": "for a preventive check-up"},
    "kontrolle": {"de": "für eine Kontrolluntersuchung", "en": "for a follow-up check"},
    "impfung": {"de": "für eine Impfung", "en": "for a vaccination"},
    "beschwerden": {"de": "wegen aktueller Beschwerden", "en": "because of current complaints"},
    "zahn": {"de": "für eine zahnärztliche Untersuchung", "en": "for a dental appointment"},
    "kind": {"de": "für mein Kind", "en": "for my child"},
    "beratung": {"de": "für ein Beratungsgespräch", "en": "for a consultation"},
}
ANFRAGE_ZEIT: dict[str, dict[str, str]] = {
    "vormittags": {"de": " Am besten passt mir vormittags.", "en": " Mornings suit me best."},
    "nachmittags": {"de": " Am besten passt mir nachmittags.", "en": " Afternoons suit me best."},
    "egal": {"de": " Ich bin zeitlich flexibel.", "en": " I am flexible with the time."},
}

STATUS_LABEL: dict[str, dict[str, str]] = {
    "offen": {"de": "offen", "en": "open"},
    "in_arbeit": {"de": "in Arbeit", "en": "in progress"},
    "erledigt": {"de": "erledigt", "en": "done"},
}

# Anzeige der Auswahlwerte (Werte selbst sind die kanonischen Strings aus lotse.slots).
OPTION_LABEL: dict[str, dict[str, dict[str, str]]] = {
    "anliegen.fuer_wen": {
        "selbst": {"de": "für mich selbst", "en": "for myself"},
        "angehoerige": {"de": "für eine Angehörige / einen Angehörigen", "en": "for a relative"},
    },
    "person.geschlecht": {
        "weiblich": {"de": "weiblich", "en": "female"},
        "männlich": {"de": "männlich", "en": "male"},
        "divers": {"de": "divers", "en": "diverse"},
    },
    "person.bundesland": {
        "Wien": {"de": "Wien", "en": "Vienna"},
        "Niederösterreich": {"de": "Niederösterreich", "en": "Lower Austria"},
        "Oberösterreich": {"de": "Oberösterreich", "en": "Upper Austria"},
        "Salzburg": {"de": "Salzburg", "en": "Salzburg"},
        "Tirol": {"de": "Tirol", "en": "Tyrol"},
        "Vorarlberg": {"de": "Vorarlberg", "en": "Vorarlberg"},
        "Kärnten": {"de": "Kärnten", "en": "Carinthia"},
        "Steiermark": {"de": "Steiermark", "en": "Styria"},
        "Burgenland": {"de": "Burgenland", "en": "Burgenland"},
    },
    "versicherung.krankenversicherung": {
        "ÖGK": {"de": "ÖGK", "en": "ÖGK"},
        "SVS": {"de": "SVS", "en": "SVS"},
        "BVAEB": {"de": "BVAEB", "en": "BVAEB"},
        "unbekannt": {"de": "weiß ich nicht", "en": "I don't know"},
    },
    "versicherung.pension": {
        "PVA": {"de": "PVA", "en": "PVA"},
        "SVS": {"de": "SVS", "en": "SVS"},
        "BVAEB": {"de": "BVAEB", "en": "BVAEB"},
        "keine": {"de": "keine Pension", "en": "no pension"},
        "unbekannt": {"de": "weiß ich nicht", "en": "I don't know"},
    },
    "pflege.antragsart": {
        "zuerkennung": {"de": "Erstantrag (Zuerkennung)", "en": "first application"},
        "erhoehung": {"de": "Erhöhung", "en": "increase"},
        "weitergewaehrung": {"de": "Weitergewährung", "en": "continuation"},
    },
    "reha.form": {
        "ambulant": {"de": "ambulant", "en": "outpatient"},
        "stationaer": {"de": "stationär", "en": "inpatient"},
        "nicht_angegeben": {"de": "nicht angegeben", "en": "not stated"},
    },
    "termin.anlass": {
        "vorsorge": {"de": "Vorsorgeuntersuchung", "en": "Preventive check-up"},
        "kontrolle": {"de": "Kontrolle", "en": "Follow-up check"},
        "impfung": {"de": "Impfung", "en": "Vaccination"},
        "beschwerden": {"de": "Beschwerden", "en": "Complaints"},
        "zahn": {"de": "Zahnarzt", "en": "Dentist"},
        "kind": {"de": "Kinderärztin/Kinderarzt", "en": "Paediatrician"},
        "beratung": {"de": "Beratung", "en": "Advice"},
    },
    "termin.zeit": {
        "vormittags": {"de": "vormittags", "en": "mornings"},
        "nachmittags": {"de": "nachmittags", "en": "afternoons"},
        "egal": {"de": "egal", "en": "no preference"},
    },
}

# Beschriftung der Antwortknöpfe, wo sie von der Anzeige abweicht (Frage ist eine Ja/Nein-Frage).
KNOPF_LABEL: dict[str, dict[str, dict[str, str]]] = {
    "pflege.antragsart": {
        "zuerkennung": {"de": "Nein – Erstantrag", "en": "No – first application"},
        "erhoehung": {"de": "Ja – Erhöhung", "en": "Yes – increase"},
        "weitergewaehrung": {"de": "Weitergewährung", "en": "Continuation"},
    },
    "termin.zeit": {
        "vormittags": {"de": "Vormittags", "en": "Mornings"},
        "nachmittags": {"de": "Nachmittags", "en": "Afternoons"},
        "egal": {"de": "Egal", "en": "No preference"},
    },
}

# Texte der Oberfläche (werden über /api/texte an die UI geliefert).
UI: dict[str, dict[str, str]] = {
    "titel": {"de": "SV KI-Lotse", "en": "SV AI Navigator"},
    "sprache": {"de": "Sprache", "en": "Language"},
    "stil": {"de": "Darstellung", "en": "Style"},
    "einfach": {"de": "Einfach", "en": "Simple"},
    "ausfuehrlich": {"de": "Ausführlich", "en": "Detailed"},
    "modus": {"de": "Modus", "en": "Mode"},
    "modus_regelbasiert": {"de": "regelbasiert", "en": "rule-based"},
    "modus_ki": {"de": "KI", "en": "AI"},
    "modus_titel_regelbasiert": {"de": "Antworten entstehen regelbasiert aus den lokalen Quellen.",
                                 "en": "Answers are built rule-based from the local sources."},
    "modus_titel_ki": {"de": "Ein Sprachmodell formuliert – nur aus belegten Quellen, mit Prüfung jeder Ausgabe.",
                       "en": "A language model phrases answers – only from cited sources, every output is checked."},
    "hochladen_hilfe": {"de": "PDF, Textdatei oder Foto (JPG, PNG, WebP), z. B. Entlassungsbrief oder Impfpass",
                        "en": "PDF, text file or photo (JPG, PNG, WebP), e.g. discharge letter or vaccination record"},
    "grenze_titel": {"de": "Medizinische Grenze", "en": "Medical limit"},
    "grenze_hinweis": {
        "de": "Der Lotse stellt keine Diagnosen, deutet keine Befunde, bewertet keine gesundheitlichen Risiken "
              "und empfiehlt keine Therapien, Medikamente oder Dosierungen. Gesundheitliche Fragen klären Sie mit "
              "Ihrer Ärztin oder Ihrem Arzt; telefonische Gesundheitsberatung: 1450.",
        "en": "The navigator does not diagnose, interpret findings, assess health risks or recommend treatments, "
              "medicines or dosages. Please discuss health questions with your doctor; telephone health advice: 1450.",
    },
    "chat_titel": {"de": "Gespräch", "en": "Conversation"},
    "chat_label": {"de": "Ihre Nachricht", "en": "Your message"},
    "chat_platzhalter": {"de": "Beschreiben Sie Ihre Situation …", "en": "Describe your situation …"},
    "senden": {"de": "Senden", "en": "Send"},
    "sie": {"de": "Sie", "en": "You"},
    "lotse": {"de": "Lotse", "en": "Navigator"},
    "angaben": {"de": "Ihre Angaben", "en": "Your details"},
    "angabe_hinterlegt": {"de": "hinterlegt", "en": "stored"},
    "naechster": {"de": "Nächster Schritt", "en": "Next step"},
    "zustaendig": {"de": "Zuständige Stelle", "en": "Responsible body"},
    "zustaendig_offen": {"de": "hängt von Ihrer Angabe ab", "en": "depends on your answer"},
    "quellen": {"de": "Quellen", "en": "Sources"},
    "fundstelle": {"de": "Fundstelle", "en": "Reference"},
    "stand": {"de": "Stand", "en": "As of"},
    "stand_unbekannt": {"de": "Stand unbekannt", "en": "date unknown"},
    "extern_badge": {"de": "extern – nicht lokal geprüft", "en": "external – not checked locally"},
    "formular": {"de": "Formular", "en": "Form"},
    "entwurf_laden": {"de": "Entwurf herunterladen (PDF)", "en": "Download draft (PDF)"},
    "fehlend": {"de": "Noch selbst im PDF zu ergänzen", "en": "Still to be completed in the PDF"},
    "unterlagen": {"de": "Unterlagen", "en": "Documents to enclose"},
    "schritte": {"de": "Schritte", "en": "Steps"},
    "voraussetzungen": {"de": "Voraussetzungen", "en": "Requirements"},
    "dokument_zitat": {"de": "In Ihrem Dokument steht", "en": "Your document states"},
    "status_offen": {"de": "offen", "en": "open"},
    "status_in_arbeit": {"de": "in Arbeit", "en": "in progress"},
    "status_erledigt": {"de": "erledigt", "en": "done"},
    "status_aendern": {"de": "Status ändern", "en": "Change status"},
    "verlauf": {"de": "Verlauf", "en": "History"},
    "laedt": {"de": "Einen Moment …", "en": "One moment …"},
    "fehler": {"de": "Es ist ein Fehler aufgetreten. Bitte versuchen Sie es erneut.",
               "en": "Something went wrong. Please try again."},
    "unterschrift_hinweis": {"de": "Unterschrift und Einreichung erfolgen durch Sie. Nichts wird automatisch versendet.",
                             "en": "You sign and submit. Nothing is sent automatically."},
    "region": {"de": "Nur in", "en": "Only in"},
    "grenze_antwort": {"de": "Hinweis zur medizinischen Grenze", "en": "Note on the medical limit"},
    "aus_dokument": {"de": "aus Dokument", "en": "from document"},
    "aus_gespraech": {"de": "aus dem Gespräch", "en": "from the conversation"},
    "aus_ortsangabe": {"de": "aus Ihrer Ortsangabe", "en": "from the place you named:"},
    "aus_aenderung": {"de": "von Ihnen geändert", "en": "changed by you"},
    "seite": {"de": "S.", "en": "p."},
    "szenario_pflege": {"de": "Pflege", "en": "Care"},
    "szenario_gesundheit": {"de": "Gesundheit", "en": "Health"},
    "szenario_entlassung": {"de": "Nach dem Spital", "en": "After hospital"},
    "szenario_kind": {"de": "Kind", "en": "Child"},
    "demo_synthetisch": {"de": "Synthetischer Entlassungsbrief", "en": "Synthetic discharge letter"},
    "demo_sv_box": {"de": "Entlassungsbefund (SV-Box)", "en": "Discharge report (SV box)"},
    "demo_impfpass": {"de": "Synthetischer Impfpass", "en": "Synthetic vaccination record"},
    "demo_foto": {"de": "Foto eines Entlassungsbriefs (KI)", "en": "Photo of a discharge letter (AI)"},
    "seite_eine": {"de": "Seite", "en": "page"},
    "antwortmoeglichkeiten": {"de": "Antwortmöglichkeiten", "en": "Answer options"},
    "quelle": {"de": "Quelle", "en": "Source"},
    "skip_link": {"de": "Zur Eingabe springen", "en": "Skip to input"},
    "weitere_sprachen": {"de": "Weitere Sprachen", "en": "More languages"},
    "nur_ki": {"de": "nur im KI-Modus", "en": "AI mode only"},
    "weitere_sprachen_hinweis": {"de": "Weitere Sprachen gibt es nur im KI-Modus. Zitate bleiben im Original.",
                                 "en": "More languages are only available in AI mode. Quotes stay in the original."},
    "nutzen_titel": {"de": "Warum das hilft", "en": "Why this helps"},
    "einrichtungen_titel": {"de": "Wo Sie Angebote finden", "en": "Where to find services"},
    "oesterreichweit": {"de": "österreichweit", "en": "throughout Austria"},
    "regional_titel": {"de": "In Ihrem Bundesland", "en": "In your province"},
    "termin_vorbereiten": {"de": "Termin vorbereiten", "en": "Prepare appointment"},
    "termin_titel": {"de": "Termin", "en": "Appointment"},
    "termin_ort": {"de": "Ort", "en": "Place"},
    "termin_zeit": {"de": "Tageszeit", "en": "Time of day"},
    "termin_wo": {"de": "Wo Sie den Termin bekommen", "en": "Where to get the appointment"},
    "termin_hinweise": {"de": "Gut zu wissen", "en": "Good to know"},
    "termin_suche": {"de": "Suchen und buchen", "en": "Search and book"},
    "termin_anfrage": {"de": "Text für Ihre Terminanfrage", "en": "Text for your appointment request"},
    "termin_kein_buchen": {"de": "Der Lotse bucht nicht selbst. Sie vereinbaren den Termin direkt mit der Stelle.",
                           "en": "The navigator does not book for you. You arrange the appointment directly."},
    "termin_eintragen": {"de": "Vereinbarten Termin eintragen", "en": "Enter the booked appointment"},
    "termin_speichern": {"de": "Termin speichern", "en": "Save appointment"},
    "datum": {"de": "Datum", "en": "Date"},
    "uhrzeit": {"de": "Uhrzeit", "en": "Time"},
    "ics_laden": {"de": "In Kalender eintragen (.ics)", "en": "Add to calendar (.ics)"},
    "termin_status_vorbereitet": {"de": "vorbereitet", "en": "prepared"},
    "termin_status_vereinbart": {"de": "vereinbart", "en": "booked"},
    "termin_status_erledigt": {"de": "erledigt", "en": "done"},
    "termin_als_erledigt": {"de": "Als erledigt markieren", "en": "Mark as done"},
    "kopieren": {"de": "Text kopieren", "en": "Copy text"},
    "kopiert": {"de": "Text kopiert", "en": "Text copied"},
    "kopieren_fehler": {"de": "Kopieren nicht möglich – bitte den Text markieren und kopieren.",
                        "en": "Copying failed – please select and copy the text."},
    "szenario_unterstuetzung": {"de": "Geld & Unterstützung", "en": "Money & support"},
    "szenario_termin": {"de": "Arzttermin", "en": "Doctor's appointment"},
    "dokumente_titel": {"de": "Ihre Dokumente", "en": "Your documents"},
    "seiten": {"de": "Seiten", "en": "pages"},
    "transkribiert_hinweis": {"de": "Vom Foto abgeschrieben (KI). Bitte mit dem Original vergleichen.",
                              "en": "Transcribed from a photo (AI). Please compare with the original."},
    "impfungen_titel": {"de": "Laut Ihrem Impfpass dokumentiert", "en": "Documented in your vaccination record"},
    "impfung": {"de": "Impfung", "en": "Vaccination"},
    "dokument": {"de": "Dokument", "en": "Document"},
    "impfungen_hinweis": {
        "de": "Nur abgeschrieben, keine Bewertung. Welche Impfung Sie brauchen, klären Sie mit Ihrer Ärztin oder "
              "Ihrem Arzt.",
        "en": "Copied only, not assessed. Please ask your doctor which vaccinations you need.",
    },
    "medikamente_titel": {"de": "Erstattungsstatus der genannten Medikamente",
                          "en": "Reimbursement status of the listed medicines"},
    "medikamente_hinweis": {
        "de": "Nur der Erstattungsstatus laut Erstattungskodex – keine Empfehlung zu Einnahme, Wechsel oder Dosierung.",
        "en": "Reimbursement status from the reimbursement code only – no advice on taking, switching or dosage.",
    },
    "eko_nicht_gefunden": {"de": "im Erstattungskodex nicht gefunden", "en": "not found in the reimbursement code"},
    "eko_beispiel": {"de": "z. B.", "en": "e.g."},
    "eko_eintraege": {"de": "{n} Einträge", "en": "{n} entries"},
    "eko_eintrag_eins": {"de": "1 Eintrag", "en": "1 entry"},
    "box_gruen": {"de": "Grüne Box", "en": "Green box"},
    "box_gelb": {"de": "Gelbe Box", "en": "Yellow box"},
    "kennzeichen": {"de": "Kennzeichen", "en": "Codes"},
    "fall_speichern": {"de": "Fall speichern", "en": "Save case"},
    "fall_laden": {"de": "Fall laden", "en": "Load case"},
    "fall_laden_hilfe": {"de": "Gespeicherte Fall-Datei (.json)", "en": "Saved case file (.json)"},
    "uebersicht": {"de": "Stand", "en": "Progress"},
    "mikro_start": {"de": "Spracheingabe starten", "en": "Start voice input"},
    "mikro_stop": {"de": "Spracheingabe beenden", "en": "Stop voice input"},
    "mikro_aktiv": {"de": "Ich höre zu …", "en": "Listening …"},
    "mikro_fehler": {"de": "Spracheingabe ist gerade nicht möglich.", "en": "Voice input is not available right now."},
    "vorlesen": {"de": "Vorlesen", "en": "Read aloud"},
    "vorlesen_stop": {"de": "Vorlesen beenden", "en": "Stop reading"},
    # --- Oberfläche 2026-11 (Ansichten, Einstellungen, Plan, Leistung) ---
    "nav_label": {"de": "Hauptnavigation", "en": "Main navigation"},
    "plan_titel": {"de": "Mein Plan", "en": "My plan"},
    "einstellungen": {"de": "Einstellungen", "en": "Settings"},
    "schliessen": {"de": "Schließen", "en": "Close"},
    "skip_inhalt": {"de": "Zum Inhalt springen", "en": "Skip to content"},
    "gespraechsverlauf": {"de": "Gesprächsverlauf", "en": "Conversation history"},
    "ansicht_angezeigt": {"de": "Ansicht: {titel}", "en": "View: {titel}"},
    "antwort_da": {"de": "Neue Antwort vom Lotsen.", "en": "New answer from the navigator."},
    "leicht": {"de": "Leichte Sprache", "en": "Easy language"},
    "textgroesse": {"de": "Textgröße", "en": "Text size"},
    "groesse_100": {"de": "Normal", "en": "Normal"},
    "groesse_115": {"de": "Größer", "en": "Larger"},
    "groesse_130": {"de": "Am größten", "en": "Largest"},
    "farbschema": {"de": "Farbschema", "en": "Colour scheme"},
    "farbe_system": {"de": "Wie System", "en": "Same as device"},
    "farbe_hell": {"de": "Hell", "en": "Light"},
    "farbe_dunkel": {"de": "Dunkel", "en": "Dark"},
    "farbe_kontrast": {"de": "Hoher Kontrast", "en": "High contrast"},
    "belege_anzeigen": {"de": "Belege anzeigen", "en": "Show sources"},
    "belege_hilfe": {"de": "Zeigt bei jeder Aussage die Quelle: Gesetz, Seite oder Webseite.",
                     "en": "Shows the source of every statement: law, page or website."},
    "vorlesetempo": {"de": "Vorlesetempo", "en": "Reading speed"},
    "tempo_langsam": {"de": "Langsam", "en": "Slow"},
    "tempo_normal": {"de": "Normal", "en": "Normal"},
    "tempo_schnell": {"de": "Schnell", "en": "Fast"},
    "einstellungen_hinweis": {"de": "Ihre Einstellungen gelten sofort und bleiben auf diesem Gerät gespeichert.",
                              "en": "Your settings apply immediately and are saved on this device."},
    "tastatur_titel": {"de": "Bedienung mit der Tastatur", "en": "Using the keyboard"},
    "tastatur_text": {
        "de": "Tab: zum nächsten Element. Enter: Nachricht senden. Umschalt und Enter: neue Zeile. "
              "Esc: dieses Fenster schließen. Eigene Tastenkürzel gibt es nicht, damit Screenreader ungestört arbeiten.",
        "en": "Tab: next element. Enter: send message. Shift and Enter: new line. "
              "Esc: close this window. There are no extra shortcuts, so screen readers work undisturbed.",
    },
    "worum_geht_es": {"de": "Worum geht es?", "en": "What is it about?"},
    "beispiel_dokumente": {"de": "Beispiel-Dokumente ausprobieren", "en": "Try sample documents"},
    "beispiel_dokumente_hinweis": {"de": "Erfundene Dokumente zum Ausprobieren, keine echten Daten.",
                                   "en": "Made-up documents to try out, no real data."},
    "grenze_kurz": {"de": "Keine Diagnosen und keine medizinischen Ratschläge. Gesundheitsfragen: Ärztin, Arzt oder 1450.",
                    "en": "No diagnoses and no medical advice. Health questions: your doctor or 1450."},
    "fortschritt": {"de": "{erledigt} von {gesamt} Schritten erledigt", "en": "{erledigt} of {gesamt} steps done"},
    "antrag_vorbereiten": {"de": "Antrag vorbereiten", "en": "Prepare application"},
    "details_ansehen": {"de": "Details ansehen", "en": "View details"},
    "erledigt_knopf": {"de": "Erledigt", "en": "Done"},
    "alles_erledigt_kurz": {"de": "Alle Schritte erledigt.", "en": "All steps done."},
    "schritt_erledigt": {"de": "Erledigt: {text}", "en": "Done: {text}"},
    "schritt_wieder_offen": {"de": "Wieder offen: {text}", "en": "Open again: {text}"},
    "danach": {"de": "Danach", "en": "After that"},
    "aendern": {"de": "Ändern", "en": "Change"},
    "speichern": {"de": "Speichern", "en": "Save"},
    "abbrechen": {"de": "Abbrechen", "en": "Cancel"},
    "loeschen": {"de": "Löschen", "en": "Delete"},
    "eintragen": {"de": "Eintragen", "en": "Enter"},
    "bitte_waehlen": {"de": "Bitte wählen", "en": "Please choose"},
    "angaben_leer": {"de": "Noch keine Angaben. Der Lotse übernimmt sie aus dem Gespräch oder aus Dokumenten.",
                     "en": "No details yet. The navigator takes them from the conversation or from documents."},
    "angabe_neu": {"de": "Neuer Wert für {label}", "en": "New value for {label}"},
    "angabe_format": {"de": "Format: {muster}", "en": "Format: {muster}"},
    "angabe_leer_fehler": {"de": "Bitte tragen Sie etwas ein oder wählen Sie „Löschen“.",
                           "en": "Please enter something or choose “Delete”."},
    "angabe_sensibel_hinweis": {"de": "Nur für den Formularentwurf. Wird nicht gespeichert und nicht exportiert.",
                                "en": "Only for the form draft. Not saved and not exported."},
    "fehlende_hilfe": {"de": "Was Sie hier eintragen, steht danach schon im PDF-Entwurf.",
                       "en": "What you enter here is then already filled in the PDF draft."},
    "fehlende_fuer": {"de": "für {formulare}", "en": "for {formulare}"},
    "weitere_moeglichkeiten": {"de": "Weitere Möglichkeiten ({n})", "en": "More options ({n})"},
    "plan_drucken": {"de": "Plan drucken", "en": "Print plan"},
    "plan_vorlesen": {"de": "Plan vorlesen", "en": "Read plan aloud"},
    "plan_leer": {"de": "Ihr Plan ist noch leer. Erzählen Sie im Gespräch, worum es geht. Dann erscheinen hier Ihre "
                        "nächsten Schritte.",
                  "en": "Your plan is still empty. Tell the navigator what it is about. Then your next steps appear here."},
    "zum_gespraech": {"de": "Zum Gespräch", "en": "Go to the conversation"},
    "fall_sichern_hilfe": {"de": "Speichert Ihren Fall als Datei auf diesem Gerät, ohne sensible Angaben.",
                           "en": "Saves your case as a file on this device, without sensitive details."},
    "neuer_fall_frage": {"de": "Einen neuen Fall beginnen? Das bisherige Gespräch wird geschlossen. Mit „Fall speichern“ "
                               "können Sie es vorher sichern.",
                         "en": "Start a new case? The current conversation will be closed. You can keep it first with "
                               "“Save case”."},
    "zurueck_plan": {"de": "Zurück zu Mein Plan", "en": "Back to My plan"},
    "so_gehen_sie_vor": {"de": "So gehen Sie vor", "en": "How to proceed"},
    "belege_titel": {"de": "Belege", "en": "Sources"},
    "angaben_ergaenzen": {"de": "Angaben ergänzen", "en": "Add details"},
    "leistung_fehlt": {"de": "Diese Leistung steht nicht (mehr) in Ihrem Plan.",
                       "en": "This service is not (or no longer) in your plan."},
    "leistungen_liste": {"de": "Alle Leistungen in Ihrem Plan", "en": "All services in your plan"},
    "druck_datum": {"de": "Erstellt am {datum}", "en": "Created on {datum}"},
    # --- Oberfläche 2026-11, drei Bereiche (Gespräch, Mein Plan, Meine Akte) ---
    "akte_titel": {"de": "Meine Akte", "en": "My records"},
    "dokument_hinzufuegen": {"de": "Dokument hinzufügen", "en": "Add document"},
    "beispiele_ausprobieren": {"de": "Beispiele zum Ausprobieren", "en": "Examples to try"},
    "naechster_schritt_titel": {"de": "Ihr nächster Schritt", "en": "Your next step"},
    "zu_meinem_plan": {"de": "Zu meinem Plan", "en": "Go to my plan"},
    "ansehen": {"de": "Ansehen", "en": "View"},
    "termin_oeffnen": {"de": "Termin öffnen", "en": "Open appointment"},
    "mehr_zur_leistung": {"de": "Mehr zu dieser Leistung", "en": "More about this service"},
    "belege_n": {"de": "Belege ({n})", "en": "Sources ({n})"},
    "in_akte_ergaenzen": {"de": "In Meine Akte ergänzen", "en": "Add in My records"},
    "antrag_herunterladen": {"de": "Antrag herunterladen (PDF)", "en": "Download application (PDF)"},
    "neuen_fall_beginnen": {"de": "Neuen Fall beginnen", "en": "Start a new case"},
    "fehlen_noch": {"de": "Für Formulare fehlen noch", "en": "Still missing for forms"},
    "dokumente_leer": {"de": "Noch keine Dokumente. Sie können zum Beispiel einen Entlassungsbrief hinzufügen.",
                       "en": "No documents yet. You can add a discharge letter, for example."},
    "unterlagen_immer": {"de": "Immer nötig", "en": "Always needed"},
    "unterlagen_bedingt": {"de": "Nur wenn es auf Sie zutrifft ({n})", "en": "Only if it applies to you ({n})"},
    "alle_anzeigen": {"de": "Alle {n} anzeigen", "en": "Show all {n}"},
}


def t(key: str, sprache: str, **kw: object) -> str:
    """Engine-Text in der gewünschten Sprache; Platzhalter werden ersetzt."""
    vorlage = _ENGINE[key][sprache if sprache in SPRACHEN else "de"]
    return vorlage.format(**kw) if kw else vorlage


def beide(key: str, **kw: object) -> dict[str, str]:
    """Text in beiden Sprachen. Werte in `kw` dürfen `{de, en}`-Dicts sein."""
    return {sp: t(key, sp, **{k: (v[sp] if isinstance(v, dict) else v) for k, v in kw.items()}) for sp in SPRACHEN}


def t_leicht(key: str, sprache: str, **kw: object) -> str:
    """Engine-Text in Leichter Sprache; ohne eigene Vorlage der übliche Text."""
    if key not in _LEICHT:
        return t(key, sprache, **kw)
    vorlage = _LEICHT[key][sprache if sprache in SPRACHEN else "de"]
    return vorlage.format(**kw) if kw else vorlage


def beide_leicht(key: str, **kw: object) -> dict[str, str] | None:
    """Leichte-Sprache-Text in beiden Sprachen; None, wenn es keine eigene Vorlage gibt (dann gilt `beide`)."""
    if key not in _LEICHT:
        return None
    return {sp: t_leicht(key, sp, **{k: (v[sp] if isinstance(v, dict) else v) for k, v in kw.items()})
            for sp in SPRACHEN}


def frage(slot_id: str, sprache: str, stil: str) -> str:
    """Rückfrage zu einem Slot; in Leichter Sprache die kürzere Fassung aus FRAGE_LEICHT, wenn vorhanden."""
    if stil == "leicht" and slot_id in FRAGE_LEICHT:
        return FRAGE_LEICHT[slot_id][sprache]
    return SLOTS[slot_id].frage[sprache]


def muster_hinweis(slot_id: str, sprache: str) -> str:
    """Eingabeformat eines Slots für Formularfelder („TT.MM.JJJJ“, „10 Ziffern“); "" ohne festes Format."""
    if SLOTS[slot_id].typ == "datum":
        return DATUM_HINWEIS[sprache]
    return MUSTER_HINWEIS.get(slot_id, {}).get(sprache, "")


def stil_label(stil: str, sprache: str) -> str:
    return UI[stil][sprache]


def anzahl(wort: str, n: int) -> dict[str, str]:
    """„1 Seite“ / „3 Seiten“ in beiden Sprachen."""
    return {sp: f"{n} {_ZAEHLWORT[wort][sp][0 if n == 1 else 1]}" for sp in SPRACHEN}


def aufzaehlung(teile: list[str], sprache: str) -> str:
    """„A, B und C“ bzw. „A, B and C“."""
    und = {"de": "und", "en": "and"}[sprache if sprache in SPRACHEN else "de"]
    return f"{', '.join(teile[:-1])} {und} {teile[-1]}" if len(teile) > 1 else "".join(teile)


def wert_anzeige(slot_id: str, wert: str, sprache: str) -> str:
    """Lesbare Anzeige eines Slot-Werts (Auswahlwerte übersetzt)."""
    label = OPTION_LABEL.get(slot_id, {}).get(wert)
    return label[sprache] if label else wert


def knopf_label(slot_id: str, wert: str, sprache: str) -> str:
    label = KNOPF_LABEL.get(slot_id, {}).get(wert)
    return label[sprache] if label else wert_anzeige(slot_id, wert, sprache)


def slot_label(slot_id: str, sprache: str) -> str:
    s = SLOTS.get(slot_id)
    return s.label[sprache] if s else slot_id


def ui_texte() -> dict[str, dict[str, object]]:
    """UI-Texte je Sprache, inklusive Szenario-Beispiele und Statuslabels."""
    return {
        sp: {
            **{k: v[sp] for k, v in UI.items()},
            "beispiele_saetze": {k: v[sp] for k, v in BEISPIELE.items()},
            "status": {k: v[sp] for k, v in STATUS_LABEL.items()},
            "quelle_1450": QUELLE_1450.to_dict(),
        }
        for sp in SPRACHEN
    }


def sprachen(ki: bool) -> list[dict[str, object]]:
    """Wählbare Sprachen; weitere Sprachen nur im KI-Modus."""
    return [
        {"code": code, "name": name, "richtung": richtung(code), "verfuegbar": code in SPRACHEN or ki}
        for code, name in {**SPRACH_NAMEN, **WEITERE_SPRACHEN}.items()
    ]


def richtung(sprache: str) -> str:
    return "rtl" if sprache in RTL else "ltr"
