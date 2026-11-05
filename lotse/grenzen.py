"""Medizinische Grenze: Anfragen vor jeder Verarbeitung prüfen, generierte Antworten nachkontrollieren (de + en).

Der Lotse stellt keine Diagnosen, interpretiert keine Befunde, bewertet keine Risiken und gibt keine
Therapie-, Medikamenten- oder Dosierungsempfehlungen. Administrative Fragen (Antrag, Stelle, Kosten,
Bewilligung) bleiben erlaubt – auch wenn sie medizinische Wörter enthalten.
"""

from __future__ import annotations

import re

from lotse.models import Grenzentscheidung

# Leistungs-IDs aus dem Katalog, die je Kategorie als administrative Alternative angeboten werden können.
ALTERNATIVEN: dict[str, list[str]] = {
    "diagnose": ["gesundheitsberatung_1450"],
    "befund": [],
    "risiko": ["vorsorgeuntersuchung", "brustkrebs_frueherkennung"],
    "therapie": ["rehabilitation"],
    "medikament": ["rezeptgebuehrenbefreiung"],
    "dosis": ["gesundheitsberatung_1450"],
}

_ARZT_DE = "Ihre behandelnde Ärztin oder Ihr behandelnder Arzt"
_ARZT_EN = "your treating doctor"
_1450_DE = "Bei akuten Beschwerden hilft die telefonische Gesundheitsberatung 1450 rund um die Uhr weiter (ÖGK-Serviceratgeber 2026, PDF-S. 42)."
_1450_EN = "For acute symptoms, the health advice line 1450 helps around the clock (ÖGK service guide 2026, PDF p. 42)."

ANTWORTEN: dict[str, dict[str, str]] = {
    "diagnose": {
        "de": "Eine Diagnose kann und darf ich nicht stellen – das kann nur eine Ärztin oder ein Arzt nach einer Untersuchung. "
              f"{_1450_DE} Gern helfe ich Ihnen, einen Arzttermin vorzubereiten oder die passende Anlaufstelle zu finden.",
        "en": "I cannot and must not make a diagnosis – only a doctor can do that after an examination. "
              f"{_1450_EN} I am happy to help you prepare a doctor's appointment or find the right place to go.",
    },
    "befund": {
        "de": f"Befunde und Messwerte interpretiere ich nicht – bitte besprechen Sie sie mit {_ARZT_DE}. "
              "Was ich tun kann: Empfehlungen, die im Dokument ausdrücklich stehen (z. B. „Rehabilitation empfohlen“), wörtlich mit Seitenangabe herausziehen "
              "und Ihnen die nächsten organisatorischen Schritte zeigen – Antrag, zuständige Stelle, Unterlagen.",
        "en": f"I do not interpret medical findings or test values – please discuss them with {_ARZT_EN}. "
              "What I can do: quote recommendations that are explicitly written in the document (e.g. \"rehabilitation recommended\") with the page number "
              "and show you the next administrative steps – application, responsible body, documents.",
    },
    "risiko": {
        "de": f"Eine persönliche Einschätzung Ihres Erkrankungsrisikos darf ich nicht geben – das gehört in ein Gespräch mit {_ARZT_DE}. "
              "Ich kann Ihnen aber die offiziellen Vorsorgeangebote der Sozialversicherung erklären, etwa die kostenlose Vorsorgeuntersuchung "
              "und Früherkennungsprogramme – mit Quellen, ohne individuelle Bewertung. Familiäre Erkrankungen können Sie dort im Fragebogen angeben.",
        "en": f"I must not give a personal assessment of your risk of illness – that belongs in a conversation with {_ARZT_EN}. "
              "I can, however, explain the official prevention offers of the social insurance, such as the free preventive check-up "
              "and screening programmes – with sources, without an individual assessment. You can note family illnesses in the check-up questionnaire.",
    },
    "therapie": {
        "de": f"Ob eine Behandlung, Operation oder Rehabilitation für Sie medizinisch nötig ist, entscheidet {_ARZT_DE}. "
              "Wenn eine Maßnahme in einem ärztlichen Dokument bereits empfohlen ist, helfe ich Ihnen gern weiter: "
              "welcher Antrag nötig ist, welche Stelle zuständig ist und welche Unterlagen Sie brauchen.",
        "en": f"Whether a treatment, operation or rehabilitation is medically necessary for you is decided by {_ARZT_EN}. "
              "If a measure is already recommended in a medical document, I am glad to help: "
              "which application is needed, which body is responsible and which documents you need.",
    },
    "medikament": {
        "de": "Medikamente kann ich weder empfehlen noch auswählen – bitte fragen Sie Ihre Ärztin, Ihren Arzt oder Ihre Apotheke. "
              "Administrativ helfe ich gern: zum Beispiel, ob ein bestimmtes Medikament laut Erstattungskodex bewilligt werden muss, "
              "oder bei Fragen zur Rezeptgebühr und deren Befreiung.",
        "en": "I can neither recommend nor choose medicines – please ask your doctor or pharmacy. "
              "I am glad to help with the administrative side: for example, whether a specific medicine needs approval according to the reimbursement code, "
              "or with questions about the prescription charge and exemptions.",
    },
    "dosis": {
        "de": "Bitte ändern, beenden oder dosieren Sie Medikamente nicht ohne ärztliche Rücksprache – dazu kann und darf ich nichts sagen. "
              f"Wenden Sie sich an {_ARZT_DE} oder an Ihre Apotheke. {_1450_DE}",
        "en": "Please do not change, stop or dose medicines without consulting a doctor – I cannot and must not advise on this. "
              f"Contact {_ARZT_EN} or your pharmacy. {_1450_EN}",
    },
}

# Gemeinsame Wortgruppen
_PERSON_DE = r"(ich|er|sie|mein\w*\s+\w+)"
_PERSON_EN = r"(i|he|she|my\s+\w+)"
# „…mittel“ ohne Hilfs-, Verkehrs-, Lebens-, Haushalts- und Fördermittel
_MEDI_DE = (r"(medikament\w*|tablette\w*|pille\w*|kapsel\w*|arznei\w*|präparat\w*|insulin|cortison|kortison|antibiotik\w*|blutverdünn\w*"
            r"|tropfen|spritze\w*|schmerzmittel|\w+(?<!hilfs)(?<!verkehrs)(?<!lebens)(?<!haushalts)(?<!förder)mittel)")
_NEHMEN = r"(?<!anspruch )(nehmen|einnehmen)"  # nicht „in Anspruch nehmen“
_MEDI_EN = r"(medication|medicine|medicines|drugs?|pills?|tablets?|capsules?|painkillers?|antibiotics?|insulin|cream)"
_THERAPIE_DE = (r"(reha\w*|rehabilitation|operation|op|chemo\w*|bestrahlung\w*|strahlentherapie|physiotherapie|psychotherapie|therapie|behandlung"
                r"|kur|dialyse|ergotherapie|logopädie|stent|bypass|implantat)")
_THERAPIE_EN = r"(rehab\w*|rehabilitation|surgery|operation|chemo\w*|chemotherapy|radiotherapy|therapy|treatment|physio\w*|dialysis)"
_KRANKHEIT_DE = (r"(\w*krebs|diabetes|zucker|demenz|alzheimer|parkinson|depression\w*|burn-?out|corona|covid|grippe|migräne|tumor|herzinfarkt"
                 r"|schlaganfall|thrombose|\w+entzündung|\w+infektion|\w+krankheit|\w+erkrankung|allergie|asthma|rheuma|arthrose|bandscheibenvorfall|borreliose)")
_KRANKHEIT_EN = (r"(cancer|diabetes|dementia|alzheimer\w*|parkinson\w*|depression|covid|flu|tumou?r|infection|disease|stroke|heart attack|allergy"
                 r"|asthma|arthritis|condition|illness|disorder)")
# Spezifische Mess- und Bildgebungsbegriffe (immer medizinisch) und allgemeine Begriffe (auch administrativ gebraucht)
_LABOR_SPEZ = (r"(laborwert\w*|blutwert\w*|tumormarker|psa\w*|cholesterin\w*|blutzucker\w*|hba1c|crp|leberwert\w*|nierenwert\w*"
               r"|blutbild|blutdruck\w*|röntgen\w*|mrt|ct|ultraschall\w*|icd[\w.-]*)")
_LABOR_ALLG = r"(befund\w*|ergebnis\w*|\w*wert|\w*werte)"
_LABOR_DE = rf"({_LABOR_SPEZ}|{_LABOR_ALLG})"
_BEWERTUNG = (r"(gut|schlecht|normal|schlimm|bedenklich|gefährlich|auffällig|unauffällig|in ordnung|ok|okay|zu hoch|zu niedrig|erhöht"
              r"|besorgniserregend)")

_REGELN: list[tuple[str, list[str]]] = [
    ("dosis", [
        r"\b(dosis|dosierung)\b[^.?!]{0,40}\b(erhöh\w*|verringer\w*|reduzier\w*|änder\w*|anpass\w*|verdoppel\w*|halbier\w*|steiger\w*|senk\w*)",
        r"\b(erhöh\w*|verringer\w*|reduzier\w*|änder\w*|anpass\w*|verdoppel\w*|halbier\w*|steiger\w*|senk\w*)\b[^.?!]{0,40}\b(dosis|dosierung)\b",
        r"\b(doppelte|halbe|höhere|niedrigere)\s+dosis\b",
        r"\bwie\s?viele?\b[^.?!]{0,30}\b(tabletten?|kapseln?|tropfen|mg|milligramm|ml|hübe|sprühstöße)\b",
        r"\bwelche\s+(dosis|dosierung)\b",
        r"\b(dosis|dosierung)\b[^.?!]{0,40}\b(soll|sollte|darf|kann|muss)\s+ich\b",
        rf"\bwie\s+oft\s+(darf|soll|kann|muss)\s+ich\b[^.?!]{{0,30}}\b({_MEDI_DE}|das|davon|sie|es)\s+({_NEHMEN}|spritzen)\b",
        rf"\b{_MEDI_DE}\b[^.?!]{{0,30}}\b(absetzen|abzusetzen|weglassen|wegzulassen|reduzieren|verringern|erhöhen|verdoppeln|halbieren|pausieren|unterbrechen)\b",
        rf"\b(darf|kann|soll|sollte)\s+ich\b[^.?!]{{0,30}}\b(weniger|mehr)\s+(davon\s+|{_MEDI_DE}\s+)?{_NEHMEN}\b",
        r"\b\d+([.,]\d+)?\s?(mg|milligramm|ml|tabletten?)\b[^.?!]{0,30}\b(zu viel|zuviel|zu wenig|zuwenig|in ordnung|okay|ok|normal|gefährlich)\b",
        r"\b(increase|reduce|lower|raise|double|halve|change|adjust|skip)\b[^.?!]{0,30}\b(dose|dosage)\b",
        r"\b(dose|dosage)\b[^.?!]{0,30}\b(increase|reduce|lower|raise|double|halve|change|adjust)\b",
        r"\bhow\s+(many|much)\b[^.?!]{0,30}\b(pills?|tablets?|capsules?|mg|milligrams?|ml|drops)\b",
        r"\bwhat\s+(dose|dosage)\b",
        r"\b(dose|dosage)\b[^.?!]{0,40}\b(should|can|may|must)\s+i\b",
        r"\bhow\s+often\s+(can|should|may|must)\s+i\s+take\b",
        r"\b(stop|quit|stopping|quitting)\s+taking\b",
        rf"\b(can|should|may)\s+i\s+(stop|quit|pause|skip)\b[^.?!]{{0,30}}\b{_MEDI_EN}\b",
        r"\b(come|wean)\s+off\b",
    ]),
    ("medikament", [
        rf"\bwelche[snrm]?\s+{_MEDI_DE}\b[^.?!]{{0,40}}\b(soll|sollte|kann|könnte|darf|empfehlen|empfiehlst|hilft|helfen|wirkt|wirken|nehmen|einnehmen)\b",
        rf"\b(empfehlen|empfiehlst|empfehlt|raten|rätst)\s+(sie|du|ihr)\s+(mir\s+)?(ein|eine|einen|das|die|den|ein anderes)?\s*{_MEDI_DE}",
        rf"\bwas\s+(soll|sollte|kann|könnte|darf)\s+ich\b[^.?!]{{0,30}}\b(gegen|bei|für)\b[^.?!]{{0,40}}\b({_NEHMEN}|schlucken)\b",
        r"\b(ist|wäre)\s+\w+\s+(wirksamer|verträglicher|stärker)\s+als\b",
        rf"\b(ist|wäre)\s+\w+\s+besser\s+als\s+\w+[^.?!]{{0,30}}\b{_MEDI_DE}",
        # „X und Y zusammen nehmen“ – nicht für Geldleistungen („Pflegegeld und … gleichzeitig“)
        r"\b(?!\w*(geld|bonus|beihilfe|leistung|karenz|pension|rente|zuschuss)\b)\w+\s+(und|mit)\s+"
        r"(?!\w*(geld|bonus|beihilfe|leistung|karenz|pension|rente|zuschuss)\b)\w+\s+(zusammen|gleichzeitig|gemeinsam)\s+(nehmen|einnehmen)\b",
        rf"\b{_MEDI_DE}\b[^.?!]{{0,30}}\b(zusammen|gleichzeitig|gemeinsam)\s+(mit\s+\w+\s+)?(nehmen|einnehmen)\b",
        r"\bwechselwirkung\w*",
        rf"\b(alternative|ersatz)\s+(zu|für)\s+(meinem|meinen|meiner|dem|den|der)?\s*{_MEDI_DE}",
        rf"\bwhich\s+{_MEDI_EN}\b[^.?!]{{0,40}}\b(should|can|could|would|is best|best|recommend|to take|works)\b",
        r"\bwhat\s+(should|can|could)\s+i\s+take\s+(for|against)\b",
        rf"\b(recommend|suggest)\b[^.?!]{{0,20}}\b{_MEDI_EN}",
        r"\b(can|may|should)\s+i\s+take\s+\w+\s+(with|together with|and)\s+(?!me\b)\w+",
        r"\binteractions?\b",
        r"\bis\s+\w+\s+(stronger|more effective)\s+than\b",
    ]),
    ("therapie", [
        rf"\b(brauche|benötige|bräuchte|braucht|benötigt)\s+{_PERSON_DE}\s+(wirklich\s+|überhaupt\s+|denn\s+|noch\s+|unbedingt\s+|eigentlich\s+)?(eine?n?\s+)?{_THERAPIE_DE}\b(?!-)",
        # „Brauche ich wegen meiner Krebserkrankung wirklich eine Reha?“ – Notwendigkeitsfrage mit Begründung dazwischen
        rf"\b(brauche|benötige|bräuchte|braucht|benötigt)\s+{_PERSON_DE}\s+(wegen|aufgrund)\s+(meiner|seiner|ihrer|der)\s+[\wäöüß-]+\s+(wirklich\s+|überhaupt\s+|denn\s+|noch\s+|unbedingt\s+|eigentlich\s+)?(eine?n?\s+)?{_THERAPIE_DE}\b(?!-)",
        # Krankheitsbegründung + Notwendigkeit + Maßnahme; schwach, damit „… brauche ich einen Antrag für die Reha“ durchgeht
        rf"~\b(wegen|aufgrund)\s+(meiner|seiner|ihrer|der)\s+(\w*diagnose|\w*erkrankung|\w*krankheit|befunde?|werte|{_KRANKHEIT_DE})\b[^.?!]{{0,40}}\b(brauche|benötige|bräuchte|braucht|benötigt|nötig|notwendig|sinnvoll)\b[^.?!]{{0,30}}\b{_THERAPIE_DE}\b(?!-)",
        rf"~\b(wegen|aufgrund)\s+(meiner|seiner|ihrer|der)\s+(\w*diagnose|\w*erkrankung|\w*krankheit|befunde?|werte|{_KRANKHEIT_DE})\b[^.?!]{{0,40}}\b{_THERAPIE_DE}\b[^.?!]{{0,30}}\b(nötig|notwendig|sinnvoll|ratsam)\b",
        rf"\b(soll|sollte)\s+{_PERSON_DE}\s+(mich\s+|sich\s+)?(operieren|bestrahlen|behandeln)\s+lassen\b",
        rf"\b(soll|sollte)\s+{_PERSON_DE}\s+(die\s+|eine?n?\s+)?{_THERAPIE_DE}\s+(machen|beginnen|antreten|abbrechen|durchführen|beenden)\b",
        rf"\bwelche\s+{_THERAPIE_DE}\b[^.?!]{{0,40}}\b(beste|besser|richtig|sinnvoll|empfehlen|empfiehlst)\b",
        rf"\bist\s+(eine?\s+)?{_THERAPIE_DE}\s+(für\s+(mich|ihn|sie|mein\w*\s+\w+)\s+)?(sinnvoll|nötig|notwendig|ratsam|angebracht|empfehlenswert)\b",
        r"\b(ambulant|stationär)\w*\s+oder\s+(ambulant|stationär)\w*\b[^.?!]{0,30}\b(besser|sinnvoller|richtig)\b",
        rf"\b(do|does)\s+{_PERSON_EN}\s+(really\s+|actually\s+)?need\s+(a\s+|an\s+|the\s+)?{_THERAPIE_EN}\b",
        rf"\bshould\s+{_PERSON_EN}\s+(have|get|do|undergo|start|stop)\s+(a\s+|an\s+|the\s+)?{_THERAPIE_EN}\b",
        rf"\b(because of|due to|given)\s+(my|his|her)\s+(diagnosis|condition|illness|results?)\b[^.?!]{{0,40}}\b(need|{_THERAPIE_EN})\b",
        rf"\bwhich\s+(treatment|therapy)\b[^.?!]{{0,30}}\b(best|better|right|should)\b",
        rf"\bis\s+(a\s+|an\s+)?{_THERAPIE_EN}\s+(really\s+)?(necessary|needed|advisable|a good idea)\b",
    ]),
    ("risiko", [
        r"\b(mein|meine|meinem|meinen|sein|seine|ihr|ihre)\s+(persönliche[sn]?\s+|individuelle[sn]?\s+|eigene[sn]?\s+)?\w*risiko\b",
        rf"\b(habe|hab|hätte|hat)\s+{_PERSON_DE}\s+(ein\s+)?(erhöhtes|höheres|hohes|großes|geringes)\s+\w*risiko\b",
        rf"\b(bin|ist)\s+{_PERSON_DE}\s+(auch\s+|dadurch\s+|deshalb\s+|jetzt\s+)?(erblich\s+|genetisch\s+|familiär\s+)?(gefährdet|vorbelastet|risikopatient\w*)",
        rf"\bwie\s+(wahrscheinlich|hoch|groß)\s+ist\s+(es|die\s+wahrscheinlichkeit|die\s+gefahr|das\s+risiko),?\s+dass\s+{_PERSON_DE}\b"
        rf"[^.?!]{{0,40}}\b({_KRANKHEIT_DE}|krank\w*|erkrank\w*|bekomm\w*|kriege?)\b",
        rf"\b(werde|wird)\s+{_PERSON_DE}\s+(auch\s+|später\s+|einmal\s+)?(\w+\s+)?{_KRANKHEIT_DE}\s+(bekommen|kriegen)\b",
        r"\b(ist|sind)\s+\w+\s+(vererbbar|erblich)\b",
        r"\b(my|his|her)\s+(personal\s+|own\s+|individual\s+)?(\w+\s+)?risk\b",
        rf"\b(am|is)\s+{_PERSON_EN}\s+(at\s+(a\s+)?(high\s+|higher\s+|increased\s+|elevated\s+|greater\s+)?risk|likely\s+to\s+(get|develop))\b",
        r"\bhow\s+likely\s+(is\s+it\s+that\s+)?(am\s+)?(i|he|she)\b[^.?!]{0,30}\b(get|develop|have)\b",
        r"\b(chance|odds|likelihood|probability)\s+(of|that)\s+(me\s+|i\s+|my\s+\w+\s+)?(getting|developing|get|develop|will)\b",
        rf"\bwill\s+(i|he|she)\s+(also\s+)?(get|develop)\s+(\w+\s+)?{_KRANKHEIT_EN}\b",
        r"\bis\s+\w+(\s+cancer)?\s+(hereditary|inherited|genetic)\b",
    ]),
    ("befund", [
        rf"\bwas\s+(bedeutet|bedeuten|heißt|heisst|sagt|sagen)\b[^.?!]{{0,60}}\b{_LABOR_SPEZ}\b",
        rf"~\bwas\s+(bedeutet|bedeuten|heißt|heisst|sagt|sagen)\b[^.?!]{{0,60}}\b{_LABOR_ALLG}\b",
        rf"\bist\s+(mein|meine|der|die|das|dieser|dieses|diese)\s+(\w+\s+)?{_LABOR_SPEZ}\s+(\w+\s+)?{_BEWERTUNG}\b",
        rf"~\bist\s+(mein|meine|der|die|das|dieser|dieses|diese)\s+(\w+\s+)?{_LABOR_ALLG}\s+(\w+\s+)?{_BEWERTUNG}\b",
        rf"\b(erklär\w*|interpretier\w*|deute|deuten|übersetz\w*|analysier\w*|bewerte|bewerten|beurteil\w*)\s+(sie\s+|du\s+)?(mir\s+)?(bitte\s+)?(meinen|meine|mein|den|die|das|diesen|diese|dieses)\s+(\w+\s+)?{_LABOR_DE}\b",
        r"\b(ist|sind)\s+(das|es|dies|der knoten|die werte)\s+(gutartig|bösartig|krebs|ein tumor|gefährlich|schlimm|harmlos|normal)\b",
        r"\bwhat\s+(does|do)\s+(my|the|this|these)\s+(\w+\s+){0,2}(results?|findings?|report|values?|levels?|scan|x-ray|mri|ct|blood test|lab\w*|diagnosis)\s+mean\b",
        r"\bis\s+(my|this|the)\s+(\w+\s+){0,2}(results?|values?|levels?|findings?|scan|x-ray|reading)\s+(normal|bad|good|ok|okay|dangerous|worrying|too high|too low|high|low)\b",
        r"\b(interpret|explain|analy[sz]e|read)\s+(my|the|this|these)\s+(\w+\s+){0,2}(results?|findings?|report|scan|x-ray|mri|blood test|lab\w*|values?)\b",
        r"\bis\s+(it|this|that)\s+(benign|malignant|cancer|a tumou?r|serious|dangerous)\b",
    ]),
    ("diagnose", [
        r"\bwas\s+(habe|hab|hat)\s+(ich|er|sie)(\s+denn|\s+wohl|\s+bloß|\s+nur)?\s*(\?|$)",
        r"\bwas\s+fehlt\s+(mir|ihm|ihr)\b",
        r"\bworan\s+(leide|leidet|erkrankt|liegt)\b",
        r"\bwelche\s+krankheit\s+(habe|hab|hat|könnte)\b",
        rf"\b(habe|hab|hat|hätte)\s+{_PERSON_DE}\s+(vielleicht\s+|wohl\s+|etwa\s+|eventuell\s+|möglicherweise\s+|vermutlich\s+|wahrscheinlich\s+)?(eine?n?\s+)?{_KRANKHEIT_DE}\b",
        rf"\b(könnte|kann)\s+(es|das)\s+(\w+\s+){{0,3}}{_KRANKHEIT_DE}\s+sein\b",
        r"\bist\s+das\s+(ein|eine)?\s*(symptom|anzeichen|zeichen)\s+(für|von)\b",
        r"\b(stell|erstell|gib|geben)\w*\s+(sie\s+|du\s+)?(mir\s+)?(eine\s+)?diagnose\b",
        r"\b(schmerz\w*|fieber|husten|schwindel\w*|übelkeit|ausschlag|knoten|atemnot|durchfall|erbrechen|juckreiz|herzrasen|kopfweh|bauchweh)\b"
        r"[^?]{0,80}\b(was\s+(ist|kann|könnte)\s+(das|es)|woher\s+(kommt|kommen)|was\s+habe\s+ich|was\s+fehlt|ist\s+das\s+(schlimm|gefährlich|harmlos))",
        rf"\bdo\s+(i|you think i|he|she|my\s+\w+)\s+(have|has)\s+(a\s+|an\s+)?(\w+\s+)?{_KRANKHEIT_EN}\b",
        r"\bwhat\s+(do|could|might)\s+i\s+have\b(?!\s+to\b)",
        r"\bwhat('s| is)\s+wrong\s+with\s+(me|him|her)\b",
        r"\bdiagnos(e|is)\s+(me|my|this)\b",
        r"\bis\s+(this|it)\s+(a\s+)?(sign|symptom)\s+of\b",
        rf"\bcould\s+(it|this)\s+be\s+(a\s+|an\s+)?(\w+\s+)?{_KRANKHEIT_EN}\b",
        r"\b(pain|fever|cough|dizz\w*|nausea|rash|lump|headache)\b[^?]{0,80}\bwhat\s+(is|could)\s+(it|this|that)\b",
    ]),
]
# Muster mit „~“ sind schwach: Sie greifen nicht, wenn die Frage erkennbar administrativ ist.
_VERWALTUNG = re.compile(
    r"\b(antrag\w*|beantrag\w*|pflegegeld\w*|formular\w*|zuständig\w*|rezeptgebühr\w*|fahrtkosten|bewillig\w*|anspruch\w*|unterlagen"
    r"|frist\w*|bescheid\w*|erstatt\w*|zuschuss\w*|application|apply|form|approval|entitle\w*|allowance|deadline)\b")
_KOMPILIERT = [(kategorie, [(re.compile(m.lstrip("~")), m.startswith("~")) for m in muster]) for kategorie, muster in _REGELN]


def _normalisiere(text: str) -> str:
    return " ".join(text.lower().replace("’", "'").split())


def pruefe_anfrage(text: str) -> Grenzentscheidung:
    """Blockiert medizinische Beurteilungen; alles andere ist erlaubt und läuft weiter."""
    t = _normalisiere(text)
    verwaltung = _VERWALTUNG.search(t) is not None
    for kategorie, muster in _KOMPILIERT:
        if any(m.search(t) for m, schwach in muster if not (schwach and verwaltung)):
            return Grenzentscheidung(erlaubt=False, kategorie=kategorie, antwort=dict(ANTWORTEN[kategorie]))
    return Grenzentscheidung(erlaubt=True)


# --- Nachkontrolle generierter Antworten ------------------------------------------------------

_ANTWORT_REGELN: list[tuple[str, list[str]]] = [
    ("diagnose", [
        r"\bsie\s+haben\s+(vermutlich|wahrscheinlich|wohl|vielleicht|möglicherweise|eventuell|offenbar|offensichtlich|sicher|bestimmt)\b"
        r"(?!\s+(einen\s+|keinen\s+|den\s+|das\s+)?(anspruch|recht|möglichkeit|die möglichkeit|zeit|bereits|schon|noch))",
        rf"\b(das|es|dies)\s+(klingt|deutet|spricht|sieht)\s+(nach|auf|für|aus wie)\s+(ein\s+|eine[nmrs]?\s+)?(\w+\s+)?{_KRANKHEIT_DE}\b",
        r"\bihre\s+(beschwerden|symptome)\s+(deuten|sprechen|weisen)\b",
        rf"\b(es|das)\s+handelt\s+sich\s+(vermutlich\s+|wahrscheinlich\s+|wohl\s+)?um\s+(eine?n?\s+)?(\w+\s+)?{_KRANKHEIT_DE}\b",
        r"\byou\s+(probably|likely|may|might|could)\s+(have|be suffering from)\b(?!\s+(a\s+|the\s+)?(right|entitlement|claim|time|already|to\b))",
        rf"\b(this|it)\s+(sounds|looks)\s+like\s+(a\s+|an\s+)?(\w+\s+)?{_KRANKHEIT_EN}\b",
        r"\byour\s+symptoms\s+(suggest|indicate|point to)\b",
    ]),
    ("befund", [
        rf"\bihr(e)?\s+{_LABOR_DE}\s+(ist|sind|liegt|liegen|zeigt|zeigen|bedeutet)\s+(\w+\s+)?(normal|unauffällig|auffällig|erhöht|zu hoch|zu niedrig|gut|schlecht|bedenklich|harmlos)\b",
        r"\b(der|ihr)\s+befund\s+(bedeutet|zeigt|heißt),?\s+dass\b",
        r"\byour\s+(results?|findings?|values?|levels?|scan|x-ray|report)\s+(is|are|shows?|indicates?|means?)\s+(\w+\s+)?(normal|abnormal|high|low|elevated|fine|good|bad|concerning|harmless)\b",
    ]),
    ("therapie", [
        r"\b(aufgrund|wegen)\s+(ihrer|ihres|der)\s+(diagnose|erkrankung|krankheit|befunde?s?|werte)\s+(benötigen|brauchen|sollten|müssen)\s+sie\b",
        rf"\bsie\s+(benötigen|brauchen)\s+(dringend\s+|unbedingt\s+)?(eine?n?\s+)?{_THERAPIE_DE}\b(?![-\w])",
        rf"\bich\s+(empfehle|rate)\s+(ihnen\s+)?(zu\s+)?(eine[rnm]?\s+)?{_THERAPIE_DE}\b(?![-\w])",
        r"\b(based on|because of|due to|given)\s+your\s+(diagnosis|condition|illness|results?|findings)\s*,?\s+you\s+(need|should|must|require)\b",
        rf"\byou\s+(need|require|should have|should get)\s+(a\s+|an\s+)?{_THERAPIE_EN}\b(?![-\w])",
        rf"\bi\s+(recommend|suggest|advise)\s+(a\s+|an\s+)?{_THERAPIE_EN}\b(?![-\w])",
    ]),
    ("medikament", [
        r"\b(nehmen|probieren|versuchen)\s+sie\b[^.]{0,40}\b(medikament\w*|tablette\w*|schmerzmittel|blutdruckmittel|schlafmittel|beruhigungsmittel"
        r"|präparat\w*|ibuprofen|paracetamol|aspirin|antibiotik\w*|salbe|tropfen|kapsel\w*|insulin|cortison|kortison)",
        r"\bich\s+(empfehle|rate\s+zu|würde\s+ihnen)\b[^.]{0,30}\b(medikament\w*|tablette\w*|schmerzmittel|präparat\w*|ibuprofen|paracetamol|aspirin|antibiotik\w*)",
        r"\b(das|ein)\s+(geeignete[sn]?|passende[sn]?|beste[sn]?)\s+(medikament|präparat|schmerzmittel)\s+(für\s+sie|wäre|ist)\b",
        r"\b(take|try)\s+(some\s+)?(ibuprofen|paracetamol|aspirin|antibiotics?|painkillers?|medication|medicine|pills?|tablets?)\b",
        r"\bi\s+(recommend|suggest)\s+(taking|using|the medication|a painkiller|ibuprofen|paracetamol)\b",
    ]),
    ("dosis", [
        r"\b\d+([.,]\d+)?\s?(mg|milligramm|µg|mcg|ml|tabletten?|kapseln?|tropfen|einheiten|hübe)\b[^.]{0,30}\b(täglich|pro tag|am tag|morgens|abends|mittags|stündlich|\d+\s?(x|mal))\b",
        r"\b(einmal|zweimal|dreimal|viermal|\d+\s?(x|mal))\s+(täglich|am tag|pro tag)\b[^.]{0,20}\b\d+([.,]\d+)?\s?(mg|ml|tabletten?|tropfen)\b",
        r"\b(erhöhen|reduzieren|verringern|halbieren|verdoppeln|senken|ändern)\s+sie\s+(die\s+)?(dosis|dosierung|einnahme)\b",
        r"\b(dosis|dosierung)\b[^.]{0,30}\b(zu\s+)?(erhöhen|reduzieren|verringern|halbieren|verdoppeln|senken|steigern)\b",
        r"\b(setzen|lassen)\s+sie\s+(das|die|ihr|ihre|den)\s+(\w+\s+)?(medikament\w*|tablette\w*|präparat\w*|insulin|\w*mittel)\s+(ab|weg)\b",
        r"\bsie\s+(sollten|können|dürfen|müssen)\s+(das|die|ihr|ihre)\s+(\w+\s+)?(medikament\w*|tablette\w*|präparat\w*|insulin)\s+(absetzen|weglassen|reduzieren|erhöhen|verdoppeln|halbieren)\b",
        r"\b(increase|reduce|lower|double|halve)\s+(your|the)\s+(dose|dosage)\b",
        r"\b(dose|dosage)\b[^.]{0,30}\b(increased|reduced|lowered|doubled|halved)\b",
        r"\bstop\s+taking\b",
        r"\btake\s+\d+([.,]\d+)?\s?(mg|ml|tablets?|pills?|capsules?|drops)\b",
        r"\b\d+\s?(mg|ml)\b[^.]{0,20}\b(daily|a day|per day|twice|three times|every \d+ hours)\b",
    ]),
    ("risiko", [
        r"\bihr\s+(persönliches\s+|individuelles\s+)?\w*risiko\b[^.]{0,30}\b(ist|liegt|beträgt|steigt|sinkt)\s+(\w+\s+)?(erhöht|hoch|höher|gering|niedrig|stark|deutlich)\b",
        r"\bsie\s+haben\s+(ein\s+)?(deutlich\s+)?(erhöhtes|hohes|geringes|niedriges)\s+\w*risiko\b",
        r"\bsie\s+sind\s+(erblich\s+|genetisch\s+|familiär\s+)?(vorbelastet|gefährdet|risikopatient\w*)\b",
        r"\byour\s+(personal\s+|individual\s+)?(\w+\s+)?risk\s+(of\s+(a\s+|an\s+)?\w+(\s+\w+)?\s+)?(is|increases|rises)\b",
        r"\byou\s+(are|'re)\s+at\s+(a\s+)?(high|higher|increased|low|elevated)\s+risk\b",
        r"\byou\s+have\s+(a|an)\s+(high|higher|increased|elevated|low)\s+risk\b",
    ]),
]
_ANTWORT_KOMPILIERT = [(kategorie, [re.compile(m) for m in muster]) for kategorie, muster in _ANTWORT_REGELN]
# Verneinte Aussagen („die Dosis nicht zu erhöhen“, "do not stop taking") sind Hinweise, keine Empfehlungen.
_VERNEINUNG = re.compile(r"\b(nicht|nie|niemals|keinesfalls|keine[nmrs]?|not|never|don't|do not)\b")


def pruefe_antwort(text: str) -> list[str]:
    """Verstöße in generiertem Text als „kategorie: „Fundstelle““; leere Liste = unbedenklich."""
    t = _normalisiere(text)
    verstoesse: list[str] = []
    for kategorie, muster in _ANTWORT_KOMPILIERT:
        for m in muster:
            for treffer in m.finditer(t):
                umfeld = t[max(0, treffer.start() - 25):treffer.end() + 8]  # „Ändern Sie die Dosis nicht …“
                if _VERNEINUNG.search(umfeld):
                    continue
                eintrag = f"{kategorie}: „{treffer.group(0)}“"
                if eintrag not in verstoesse:
                    verstoesse.append(eintrag)
                break
    return verstoesse
