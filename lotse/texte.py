"""Alle Texte für Engine und Oberfläche, jeweils Deutsch und Englisch.

Keine Sachaussagen ohne Quelle: Diese Texte führen nur durch den Dialog. Fachliche Inhalte
(Leistungen, Beträge, Stellen) kommen aus Katalog und Wissensbasis mit Quellenangabe.
"""

from __future__ import annotations

from lotse.models import WEITERE_SPRACHEN, Quelle
from lotse.slots import SLOTS

SPRACHEN = ("de", "en")  # Basissprachen: alle Texte liegen in beiden vor
STILE = ("einfach", "ausfuehrlich")
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
        "de": "Ich habe {n} passende Leistungen gefunden, jeweils mit zuständiger Stelle und Quelle. "
              "Am wichtigsten für Sie: {wichtigste}.",
        "en": "I found {n} matching services, each with the responsible body and a source. "
              "Most important for you: {wichtigste}.",
    },
    "gefunden_weitere": {
        "de": "Weitere {n} Angebote stehen in Ihrer Fallakte.",
        "en": "{n} more offers are listed in your case file.",
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
        "de": "Ich habe eine passende Leistung gefunden. Sie steht in Ihrer Fallakte, mit zuständiger Stelle und Quelle.",
        "en": "I found one matching service. It is listed in your case file, with the responsible body and a source.",
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
        "de": "Nächster Schritt: {titel} – {schritt}.",
        "en": "Next step: {titel} – {schritt}.",
    },
    "alles_erledigt": {
        "de": "Alle Schritte in Ihrer Fallakte sind erledigt.",
        "en": "All steps in your case file are done.",
    },
    "notiert": {
        "de": "Notiert: {label} – {wert}.",
        "en": "Noted: {label} – {wert}.",
    },
    "notiert_sensibel": {
        "de": "Notiert: {label}.",
        "en": "Noted: {label}.",
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
        "de": "Ich habe keine weiteren Fragen. Den Formularentwurf laden Sie in der Fallakte herunter.",
        "en": "I have no further questions. You can download the draft form from your case file.",
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
        "de": "Ich habe Ihr Dokument „{name}“ gelesen ({seiten}). Ich übernehme nur ausdrücklich "
              "dokumentierte Empfehlungen und deute keine medizinischen Inhalte.",
        "en": "I have read your document “{name}” ({seiten}). I only take over explicitly documented "
              "recommendations and do not interpret medical content.",
    },
    "dokument_steht": {
        "de": "In Ihrem Dokument steht: „{zitat}“ (S. {seite})",
        "en": "Your document states: “{zitat}” (p. {seite})",
    },
    "dokument_keine_empfehlung": {
        "de": "In diesem Dokument habe ich keine ausdrücklich dokumentierte Empfehlung zu einer Leistung gefunden. "
              "Offene Fragen zum Inhalt klären Sie bitte mit Ihrer Ärztin oder Ihrem Arzt.",
        "en": "I did not find any explicitly documented recommendation for a service in this document. "
              "Please discuss questions about its content with your doctor.",
    },
    "dokument_stammdaten": {
        "de": "Aus dem Dokument übernommen: {labels}. Diese Angaben frage ich nicht noch einmal.",
        "en": "Taken from the document: {labels}. I will not ask for these again.",
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
        "de": "Suchen und vereinbaren: {namen} (Links in der Fallakte).",
        "en": "Search and book: {namen} (links in your case file).",
    },
    "termin_anfrage": {
        "de": "Einen fertigen Text für Ihre Anfrage per Telefon oder E-Mail finden Sie in der Fallakte.",
        "en": "You will find a ready-made text for your request by phone or email in your case file.",
    },
    "termin_sprache_de": {
        "de": "Den Anfragetext habe ich auf Deutsch vorbereitet, damit ihn die Ordination sicher versteht.",
        "en": "I have prepared the request text in German so that the practice will understand it.",
    },
    "termin_datum_tipp": {
        "de": "Sobald Sie einen Termin haben, schreiben Sie mir zum Beispiel „Termin am 12.11.2026 um 10:30“ – dann "
              "trage ich ihn in die Fallakte ein und erstelle einen Kalendereintrag.",
        "en": "As soon as you have an appointment, write for example “appointment on 12.11.2026 at 10:30” – I will "
              "then add it to your case file and create a calendar entry.",
    },
    "termin_vereinbart": {
        "de": "Eingetragen: {titel} am {datum}{uhrzeit}. Den Kalendereintrag (.ics) laden Sie in der Fallakte herunter. "
              "Vereinbart haben Sie den Termin selbst – ich habe ihn nur notiert.",
        "en": "Added: {titel} on {datum}{uhrzeit}. You can download the calendar entry (.ics) from your case file. "
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
        "de": "In Ihrer Fallakte steht noch kein Termin. Schreiben Sie zum Beispiel „Ich möchte einen Arzttermin“, "
              "dann bereite ich ihn mit Ihnen vor.",
        "en": "There is no appointment in your case file yet. Write for example “I would like a doctor's appointment” "
              "and I will prepare it with you.",
    },
    "termin_angebot": {
        "de": "Den Termin kann ich mit Ihnen vorbereiten: Schreiben Sie „Termin vorbereiten“ oder nutzen Sie den Knopf "
              "in der Fallakte.",
        "en": "I can prepare the appointment with you: write “prepare appointment” or use the button in your case file.",
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
    # Weiterverfolgen (Status der Fallakte)
    "status_einleitung": {
        "de": "Stand Ihrer Fallakte: In Ihren wichtigsten Anliegen sind {erledigt} von {gesamt} Schritten erledigt.",
        "en": "Your case file: in your most important matters, {erledigt} of {gesamt} steps are done.",
    },
    "notiert_ort": {
        "de": "Notiert: {label} – {wert} (aus Ihrer Ortsangabe {ort}).",
        "en": "Noted: {label} – {wert} (from the place you named, {ort}).",
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
        "de": "Wenn Sie Ihre Situation beschreiben, lege ich die passenden Leistungen mit Schritten in Ihrer Fallakte an.",
        "en": "If you describe your situation, I will add the matching services with steps to your case file.",
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
        "de": "Ihre Fallakte ist noch leer. Beschreiben Sie Ihre Situation, dann lege ich die passenden Leistungen an.",
        "en": "Your case file is still empty. Describe your situation and I will add the matching services.",
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
    "impfungen_einleitung_impfpass": {
        "de": "Laut Ihrem Impfpass dokumentiert (nur abgeschrieben, keine Bewertung):",
        "en": "Documented in your vaccination record (copied only, not assessed):",
    },
    "impfungen_einleitung": {
        "de": "Laut Ihrem Dokument dokumentierte Impfungen (nur abgeschrieben, keine Bewertung):",
        "en": "Vaccinations documented in your document (copied only, not assessed):",
    },
    "impfung_zeile": {
        "de": "• {impfung}: {datum} (S. {seite})",
        "en": "• {impfung}: {datum} (p. {seite})",
    },
    "impfungen_arzt": {
        "de": "Welche Impfungen Sie brauchen, klären Sie bitte mit Ihrer Ärztin oder Ihrem Arzt.",
        "en": "Please ask your doctor which vaccinations you need.",
    },
    "medikamente_einleitung": {
        "de": "Im Dokument genannte Medikamente – nur der Erstattungsstatus laut Erstattungskodex, keine Empfehlung "
              "zu Einnahme, Wechsel oder Dosierung:",
        "en": "Medicines named in the document – reimbursement status from the reimbursement code only, no advice "
              "on taking, switching or dosage:",
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
    "untertitel": {"de": "Ihr Weg durch die Leistungen der Sozialversicherung",
                   "en": "Your way through social insurance services"},
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
    "hochladen": {"de": "Dokument hochladen", "en": "Upload document"},
    "hochladen_hilfe": {"de": "PDF, Textdatei oder Foto (JPG, PNG, WebP), z. B. Entlassungsbrief oder Impfpass",
                        "en": "PDF, text file or photo (JPG, PNG, WebP), e.g. discharge letter or vaccination record"},
    "neuer_fall": {"de": "Neuer Fall", "en": "New case"},
    "beispiele": {"de": "Beispiele", "en": "Examples"},
    "demo_dokumente": {"de": "Demo-Dokumente", "en": "Demo documents"},
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
    "fallakte_titel": {"de": "Ihre Fallakte", "en": "Your case file"},
    "fallakte_leer": {"de": "Noch keine Leistungen. Beschreiben Sie Ihre Situation oder laden Sie ein Dokument hoch.",
                      "en": "No services yet. Describe your situation or upload a document."},
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
    "lokal_badge": {"de": "lokal belegt", "en": "locally sourced"},
    "formular": {"de": "Formular", "en": "Form"},
    "entwurf_laden": {"de": "Entwurf herunterladen (PDF)", "en": "Download draft (PDF)"},
    "fehlend": {"de": "Noch selbst im PDF zu ergänzen", "en": "Still to be completed in the PDF"},
    "unterlagen": {"de": "Unterlagen", "en": "Documents to enclose"},
    "schritte": {"de": "Schritte", "en": "Steps"},
    "details": {"de": "Details", "en": "Details"},
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
    "foto": {"de": "Foto aufnehmen", "en": "Take photo"},
    "weitere_sprachen": {"de": "Weitere Sprachen", "en": "More languages"},
    "nur_ki": {"de": "nur im KI-Modus", "en": "AI mode only"},
    "weitere_sprachen_hinweis": {"de": "Weitere Sprachen gibt es nur im KI-Modus. Zitate bleiben im Original.",
                                 "en": "More languages are only available in AI mode. Quotes stay in the original."},
    "weitere_angebote": {"de": "Weitere Angebote ({n})", "en": "More services ({n})"},
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
    "ics_laden": {"de": "In den Kalender (.ics)", "en": "Add to calendar (.ics)"},
    "termin_status_vorbereitet": {"de": "vorbereitet", "en": "prepared"},
    "termin_status_vereinbart": {"de": "vereinbart", "en": "booked"},
    "termin_status_erledigt": {"de": "erledigt", "en": "done"},
    "termin_als_erledigt": {"de": "Als erledigt markieren", "en": "Mark as done"},
    "kopieren": {"de": "Text kopieren", "en": "Copy text"},
    "kopiert": {"de": "Text kopiert", "en": "Text copied"},
    "kopieren_fehler": {"de": "Kopieren nicht möglich – bitte den Text markieren und kopieren.",
                        "en": "Copying failed – please select and copy the text."},
    "szenario_unterstuetzung": {"de": "Unterstützung", "en": "Support"},
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
}


def t(key: str, sprache: str, **kw: object) -> str:
    """Engine-Text in der gewünschten Sprache; Platzhalter werden ersetzt."""
    vorlage = _ENGINE[key][sprache if sprache in SPRACHEN else "de"]
    return vorlage.format(**kw) if kw else vorlage


def beide(key: str, **kw: object) -> dict[str, str]:
    """Text in beiden Sprachen. Werte in `kw` dürfen `{de, en}`-Dicts sein."""
    return {sp: t(key, sp, **{k: (v[sp] if isinstance(v, dict) else v) for k, v in kw.items()}) for sp in SPRACHEN}


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
