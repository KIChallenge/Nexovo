"""Alle Texte für Engine und Oberfläche, jeweils Deutsch und Englisch.

Keine Sachaussagen ohne Quelle: Diese Texte führen nur durch den Dialog. Fachliche Inhalte
(Leistungen, Beträge, Stellen) kommen aus Katalog und Wissensbasis mit Quellenangabe.
"""

from __future__ import annotations

from lotse.models import Quelle
from lotse.slots import SLOTS

SPRACHEN = ("de", "en")
STILE = ("einfach", "ausfuehrlich")

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
        "de": "Ich habe {n} passende Leistungen gefunden. Sie stehen in Ihrer Fallakte, jeweils mit zuständiger Stelle und Quelle.",
        "en": "I found {n} matching services. They are listed in your case file, each with the responsible body and a source.",
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
        "de": "Dieses Dokument konnte ich nicht lesen. Bitte laden Sie eine PDF- oder Textdatei hoch.",
        "en": "I could not read this document. Please upload a PDF or text file.",
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
}

SZENARIO_LABEL: dict[str, dict[str, str]] = {
    "pflege": {"de": "Pflege und Betreuung", "en": "Care and support"},
    "gesundheit": {"de": "Gesundheitsförderung und Vorsorge", "en": "Health promotion and prevention"},
    "entlassung": {"de": "Nach dem Spitalsaufenthalt", "en": "After a hospital stay"},
    "kind": {"de": "Angebote rund ums Kind", "en": "Offers for children and families"},
}

# Beispielsätze der vier Bewertungsszenarien.
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
}

# Beschriftung der Antwortknöpfe, wo sie von der Anzeige abweicht (Frage ist eine Ja/Nein-Frage).
KNOPF_LABEL: dict[str, dict[str, dict[str, str]]] = {
    "pflege.antragsart": {
        "zuerkennung": {"de": "Nein – Erstantrag", "en": "No – first application"},
        "erhoehung": {"de": "Ja – Erhöhung", "en": "Yes – increase"},
        "weitergewaehrung": {"de": "Weitergewährung", "en": "Continuation"},
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
    "hochladen_hilfe": {"de": "PDF oder Textdatei, z. B. Entlassungsbrief", "en": "PDF or text file, e.g. discharge letter"},
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
    "seite": {"de": "S.", "en": "p."},
    "szenario_pflege": {"de": "Pflege", "en": "Care"},
    "szenario_gesundheit": {"de": "Gesundheit", "en": "Health"},
    "szenario_entlassung": {"de": "Nach dem Spital", "en": "After hospital"},
    "szenario_kind": {"de": "Kind", "en": "Child"},
    "demo_synthetisch": {"de": "Synthetischer Entlassungsbrief", "en": "Synthetic discharge letter"},
    "demo_sv_box": {"de": "Entlassungsbefund (SV-Box)", "en": "Discharge report (SV box)"},
    "antwortmoeglichkeiten": {"de": "Antwortmöglichkeiten", "en": "Answer options"},
    "quelle": {"de": "Quelle", "en": "Source"},
    "skip_link": {"de": "Zur Eingabe springen", "en": "Skip to input"},
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
