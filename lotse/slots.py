"""Kanonisches Vokabular für Angaben im Dialog, in Dokumenten und in Formularen.

Dialog (Rückfragen), Dokumentfunktion (Stammdaten) und Formular-Mapping verwenden ausschließlich diese IDs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

SlotTyp = Literal["text", "datum", "auswahl", "ja_nein", "zahl"]

BUNDESLAENDER = [
    "Wien", "Niederösterreich", "Oberösterreich", "Salzburg", "Tirol",
    "Vorarlberg", "Kärnten", "Steiermark", "Burgenland",
]


@dataclass(frozen=True)
class Slot:
    id: str
    label: dict[str, str]
    frage: dict[str, str]
    typ: SlotTyp = "text"
    optionen: tuple[str, ...] = ()
    muster: str = ""  # Regex zur Plausibilitätsprüfung (fullmatch), "" = keine Prüfung
    sensibel: bool = False  # nur im Formular, nie in Logs/Antworttext wiederholen

    def gueltig(self, wert: str) -> bool:
        wert = wert.strip()
        if not wert:
            return False
        if self.typ == "auswahl" and self.optionen:
            return wert in self.optionen
        if self.muster:
            return re.fullmatch(self.muster, wert) is not None
        return True


def _s(id: str, de: str, en: str, frage_de: str, frage_en: str, **kw) -> Slot:
    return Slot(id=id, label={"de": de, "en": en}, frage={"de": frage_de, "en": frage_en}, **kw)


_DATUM = r"\d{2}\.\d{2}\.\d{4}"

SLOTS: dict[str, Slot] = {s.id: s for s in [
    _s("anliegen.fuer_wen", "Für wen", "For whom",
       "Geht es um Sie selbst oder um eine Angehörige bzw. einen Angehörigen?",
       "Is this about yourself or about a relative?",
       typ="auswahl", optionen=("selbst", "angehoerige")),
    _s("person.vorname", "Vorname", "First name",
       "Wie lautet der Vorname der betroffenen Person?", "What is the first name of the person concerned?"),
    _s("person.nachname", "Familienname", "Last name",
       "Wie lautet der Familienname der betroffenen Person?", "What is the last name of the person concerned?"),
    _s("person.geburtsdatum", "Geburtsdatum", "Date of birth",
       "Wann ist die Person geboren (TT.MM.JJJJ)?", "What is the person's date of birth (DD.MM.YYYY)?",
       typ="datum", muster=_DATUM, sensibel=True),
    _s("person.svnr", "Sozialversicherungsnummer", "Social security number",
       "Wie lautet die 10-stellige Sozialversicherungsnummer?", "What is the 10-digit social security number?",
       muster=r"\d{10}", sensibel=True),
    _s("person.geschlecht", "Geschlecht", "Gender",
       "Welches Geschlecht soll im Antrag stehen (weiblich, männlich, divers)?",
       "Which gender should be stated on the form (female, male, diverse)?",
       typ="auswahl", optionen=("weiblich", "männlich", "divers")),
    _s("person.strasse", "Straße", "Street",
       "In welcher Straße wohnt die Person?", "Which street does the person live in?"),
    _s("person.hausnummer", "Hausnummer/Stiege/Tür", "House number",
       "Hausnummer, Stiege und Tür?", "House number, staircase and door?"),
    _s("person.plz", "Postleitzahl", "Postcode",
       "Wie lautet die Postleitzahl?", "What is the postcode?", muster=r"\d{4}"),
    _s("person.ort", "Ort", "City",
       "In welchem Ort wohnt die Person?", "Which city does the person live in?"),
    _s("person.bundesland", "Bundesland", "Federal state",
       "In welchem Bundesland wohnt die Person?", "In which federal state does the person live?",
       typ="auswahl", optionen=tuple(BUNDESLAENDER)),
    _s("person.telefon", "Telefon", "Phone",
       "Unter welcher Telefonnummer ist die Person erreichbar?", "Which phone number can be used?", sensibel=True),
    _s("person.email", "E-Mail", "Email",
       "Welche E-Mail-Adresse soll angegeben werden?", "Which email address should be used?", sensibel=True),
    _s("vertretung.vorname", "Vorname der helfenden Person", "First name of helper",
       "Wie lautet Ihr Vorname (als helfende Person)?", "What is your first name (as the helping person)?"),
    _s("vertretung.nachname", "Familienname der helfenden Person", "Last name of helper",
       "Wie lautet Ihr Familienname?", "What is your last name?"),
    _s("vertretung.beziehung", "Beziehung zur Person", "Relationship",
       "In welcher Beziehung stehen Sie zur Person (z. B. Tochter, Sohn)?",
       "What is your relationship to the person (e.g. daughter, son)?"),
    _s("vertretung.telefon", "Telefon der helfenden Person", "Phone of helper",
       "Unter welcher Nummer sind Sie erreichbar?", "Which phone number can you be reached at?", sensibel=True),
    _s("versicherung.krankenversicherung", "Krankenversicherung", "Health insurance",
       "Bei welchem Träger ist die Person krankenversichert (ÖGK, SVS, BVAEB)?",
       "Which health insurance provider covers the person (ÖGK, SVS, BVAEB)?",
       typ="auswahl", optionen=("ÖGK", "SVS", "BVAEB", "unbekannt")),
    _s("versicherung.pension", "Pension von", "Pension paid by",
       "Bezieht die Person eine Pension – und wenn ja, von PVA, SVS oder BVAEB?",
       "Does the person receive a pension – and if so, from PVA, SVS or BVAEB?",
       typ="auswahl", optionen=("PVA", "SVS", "BVAEB", "keine", "unbekannt")),
    _s("pflege.antragsart", "Antragsart Pflegegeld", "Type of care allowance application",
       "Bezieht die Person schon Pflegegeld? (Nein → Erstantrag, Ja → Erhöhung)",
       "Does the person already receive care allowance? (No → first application, Yes → increase)",
       typ="auswahl", optionen=("zuerkennung", "erhoehung", "weitergewaehrung")),
    _s("pflege.stufe", "Aktuelle Pflegegeldstufe", "Current care level",
       "Welche Pflegegeldstufe (1–7) ist derzeit zuerkannt?", "Which care level (1–7) is currently granted?",
       typ="zahl", muster=r"[1-7]"),
    _s("aufenthalt.krankenhaus", "Krankenhaus", "Hospital",
       "In welchem Krankenhaus war der Aufenthalt?", "Which hospital was the stay in?"),
    _s("aufenthalt.entlassungsdatum", "Entlassungsdatum", "Discharge date",
       "Wann war die Entlassung (TT.MM.JJJJ)?", "When was the discharge (DD.MM.YYYY)?",
       typ="datum", muster=_DATUM),
    _s("reha.form", "Reha-Form laut Dokument", "Rehab type per document",
       "Ist laut ärztlichem Dokument eine ambulante oder stationäre Rehabilitation empfohlen?",
       "According to the medical document, is outpatient or inpatient rehabilitation recommended?",
       typ="auswahl", optionen=("ambulant", "stationaer", "nicht_angegeben")),
    _s("bank.iban", "IBAN", "IBAN",
       "Auf welches Konto (IBAN) soll ein Zuschuss überwiesen werden?",
       "Which account (IBAN) should a refund be paid to?",
       muster=r"AT\d{18}", sensibel=True),
    _s("bank.kontoinhaber", "Kontoinhaber:in", "Account holder",
       "Auf wen lautet das Konto?", "Who is the account holder?"),
    _s("kind.alter", "Alter des Kindes", "Child's age",
       "Wie alt ist das Kind (in Jahren)?", "How old is the child (in years)?", typ="zahl", muster=r"\d{1,2}"),
    # Terminvorbereitung (Use Case 3.3: Hintergrund, Nähe, Tageszeit)
    _s("termin.anlass", "Anlass des Termins", "Reason for the appointment",
       "Worum geht es beim Termin – Vorsorge, Kontrolle, Impfung, Beschwerden, Zahnarzt, Kinderarzt oder Beratung?",
       "What is the appointment for – check-up, follow-up, vaccination, complaints, dentist, paediatrician or advice?",
       typ="auswahl", optionen=("vorsorge", "kontrolle", "impfung", "beschwerden", "zahn", "kind", "beratung")),
    _s("termin.ort", "Gewünschter Ort", "Preferred location",
       "Soll der Termin möglichst in Ihrer Nähe sein – in welchem Ort oder Bezirk?",
       "Should the appointment be close to you – in which town or district?"),
    _s("termin.zeit", "Bevorzugte Tageszeit", "Preferred time of day",
       "Welche Zeiten passen Ihnen – vormittags oder nachmittags?",
       "Which times suit you – mornings or afternoons?",
       typ="auswahl", optionen=("vormittags", "nachmittags", "egal")),
    _s("termin.datum", "Termindatum", "Appointment date",
       "An welchem Tag ist der vereinbarte Termin (TT.MM.JJJJ)?", "On which day is the booked appointment (DD.MM.YYYY)?",
       typ="datum", muster=_DATUM),
    _s("termin.uhrzeit", "Uhrzeit", "Time",
       "Um wie viel Uhr (HH:MM)?", "At what time (HH:MM)?", muster=r"([01]\d|2[0-3]):[0-5]\d"),
]}


def slot(id: str) -> Slot:
    return SLOTS[id]
