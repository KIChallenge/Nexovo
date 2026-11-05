import pytest

from lotse import grenzen, katalog
from lotse.grenzen import pruefe_anfrage, pruefe_antwort

KATEGORIEN = {"diagnose", "befund", "risiko", "therapie", "medikament", "dosis"}

BLOCKIERT = [
    ("Ich habe seit Tagen Kopfschmerzen und Fieber – was habe ich?", "diagnose"),
    ("Habe ich vielleicht Diabetes, weil ich ständig Durst habe?", "diagnose"),
    ("Hat meine Mutter Demenz, weil sie so vergesslich ist?", "diagnose"),
    ("Do I have cancer? I found a lump.", "diagnose"),
    ("Was bedeutet mein Laborwert HbA1c von 7,2?", "befund"),
    ("Ist mein Befund schlimm?", "befund"),
    ("Erklären Sie mir bitte meinen Röntgenbefund.", "befund"),
    ("What does my MRI result mean?", "befund"),
    ("Is my cholesterol level too high?", "befund"),
    ("Mein Vater hatte Darmkrebs, wie hoch ist mein Risiko?", "risiko"),
    ("Werde ich auch Darmkrebs bekommen?", "risiko"),
    ("Am I at risk of a heart attack?", "risiko"),
    ("Brauche ich wegen meiner Diagnose eine Reha?", "therapie"),
    ("Brauche ich eine Reha?", "therapie"),
    ("Soll ich die Chemo abbrechen?", "therapie"),
    ("Should I have the surgery?", "therapie"),
    ("Welches Medikament soll ich gegen Bluthochdruck nehmen?", "medikament"),
    ("Was kann ich gegen Kopfschmerzen nehmen?", "medikament"),
    ("Kann ich Ibuprofen und Aspirin zusammen nehmen?", "medikament"),
    ("Which painkiller is best for me?", "medikament"),
    ("Kann ich mein Blutdruckmittel absetzen?", "dosis"),
    ("Wie viele Tabletten Ibuprofen darf ich am Tag nehmen?", "dosis"),
    ("Welche Dosis Ibuprofen soll ich nehmen?", "dosis"),
    ("Should I double my insulin dose?", "dosis"),
    ("Can I stop taking my blood pressure pills?", "dosis"),
    # Notwendigkeitsfrage mit zusammengesetztem Krankheitswort (Use-Case-Grenzbeispiel)
    ("Brauche ich wegen meiner Krebserkrankung wirklich eine Reha?", "therapie"),
    ("Ist wegen meiner Herzerkrankung eine Kur notwendig?", "therapie"),
]

ERLAUBT = [
    "Wie beantrage ich eine Reha?",
    "Im Brief steht, Reha wird empfohlen – was muss ich tun?",
    "Muss mein Medikament bewilligt werden?",
    "Muss das Medikament mit der PZN 1234567 bewilligt werden?",
    "Welches Medikament ist laut Erstattungskodex bewilligungspflichtig?",
    "Wer zahlt den Transport zur Bestrahlung?",
    "Meine Mutter ist chronisch krank und kommt allein nicht mehr zurecht. Was kann ich tun?",
    "Ich möchte etwas für meine Gesundheit tun.",
    "Ich habe einen Befund/Entlassungsbrief bekommen – was muss ich jetzt erledigen?",
    "Ich habe ein Kind und möchte wissen, welche Angebote es gibt.",
    "Meine Mutter braucht jetzt Hilfe, was muss ich denn da machen?",
    "Welche Unterlagen brauche ich für das Pflegegeld?",
    "Brauche ich eine Überweisung für die Reha?",
    "Mein Vater hatte Darmkrebs. Welche Vorsorgeuntersuchungen gibt es?",
    "Wie hoch ist das Pflegegeld in Stufe 3?",
    "Wie hoch ist das Risiko, dass mein Antrag abgelehnt wird?",
    "Bin ich von der Rezeptgebühr befreit?",
    "Was habe ich jetzt zu tun?",
    "Was kann ich für meine Mutter in Anspruch nehmen?",
    "Kann ich Pflegegeld und Pflegekarenzgeld gleichzeitig nehmen?",
    "Wie viele Betreuungseinheiten fördert der FSW?",
    "Was bedeutet „Pflegegeldanspruch prüfen“ in meinem Befund?",
    "Kann ich die Kosten für Hilfsmittel von der Steuer absetzen?",
    "Ich habe Diabetes – gibt es ein Programm der ÖGK?",
    "Who pays for transport to radiotherapy?",
    "How do I apply for care allowance for my mother?",
    "My discharge letter recommends rehabilitation – what do I have to do?",
    "Does my medication need approval?",
    "Do I need a referral for the mammography?",
    "Can I take my medication with me on holiday?",
    "Wegen meiner Krebserkrankung muss ich zur Bestrahlung – wer zahlt die Fahrt?",
    "Wegen meiner Erkrankung brauche ich Hilfe zu Hause – welche Angebote gibt es?",
    "Wegen meiner Erkrankung brauche ich einen Antrag für die Reha – wo bekomme ich den?",
]


@pytest.mark.parametrize("text, kategorie", BLOCKIERT)
def test_medizinische_anfragen_werden_abgelehnt(text, kategorie):
    entscheidung = pruefe_anfrage(text)
    assert entscheidung.erlaubt is False
    assert entscheidung.kategorie == kategorie
    assert "Ärztin" in entscheidung.antwort["de"] or "Arzt" in entscheidung.antwort["de"]
    assert "doctor" in entscheidung.antwort["en"]


@pytest.mark.parametrize("text", ERLAUBT)
def test_administrative_anfragen_bleiben_erlaubt(text):
    entscheidung = pruefe_anfrage(text)
    assert entscheidung.erlaubt is True, entscheidung.kategorie
    assert entscheidung.kategorie is None
    assert entscheidung.antwort == {}


def test_risikofrage_bietet_vorsorge_ohne_risikoeinschaetzung_an():
    antwort = pruefe_anfrage("Mein Vater hatte Darmkrebs, wie hoch ist mein Risiko?").antwort
    assert "Vorsorgeuntersuchung" in antwort["de"] and "persönliche Einschätzung" in antwort["de"]
    assert "preventive check-up" in antwort["en"]
    assert set(grenzen.ALTERNATIVEN["risiko"]) == {"vorsorgeuntersuchung", "brustkrebs_frueherkennung"}


def test_diagnose_und_dosis_verweisen_auf_1450():
    for text in ("Was habe ich?", "Should I double my insulin dose?"):
        antwort = pruefe_anfrage(text).antwort
        assert "1450" in antwort["de"] and "1450" in antwort["en"]


def test_alle_kategorien_haben_zweisprachige_antwort_und_gueltige_alternativen():
    assert set(grenzen.ANTWORTEN) == KATEGORIEN == set(grenzen.ALTERNATIVEN)
    ids = {l.id for l in katalog.alle()}
    for kategorie in KATEGORIEN:
        assert grenzen.ANTWORTEN[kategorie]["de"].strip() and grenzen.ANTWORTEN[kategorie]["en"].strip()
        assert set(grenzen.ALTERNATIVEN[kategorie]) <= ids


def test_antwort_ist_kopie_und_aendert_die_vorlage_nicht():
    entscheidung = pruefe_anfrage("Ist mein Befund schlimm?")
    entscheidung.antwort["de"] = "verändert"
    assert pruefe_anfrage("Ist mein Befund schlimm?").antwort["de"] != "verändert"


# --- Nachkontrolle generierter Antworten ------------------------------------------------------

@pytest.mark.parametrize("text, kategorie", [
    ("Sie haben vermutlich eine Lungenentzündung.", "diagnose"),
    ("Das klingt nach einer Blasenentzündung.", "diagnose"),
    ("You probably have the flu.", "diagnose"),
    ("Ihr Blutwert ist zu hoch.", "befund"),
    ("Your results are abnormal.", "befund"),
    ("Aufgrund Ihrer Diagnose benötigen Sie eine Rehabilitation.", "therapie"),
    ("Based on your diagnosis, you need rehabilitation.", "therapie"),
    ("Nehmen Sie am besten Ibuprofen.", "medikament"),
    ("I recommend taking paracetamol.", "medikament"),
    ("Nehmen Sie zweimal täglich 400 mg.", "dosis"),
    ("Ich empfehle Ihnen, die Dosis zu erhöhen [1].", "dosis"),
    ("Setzen Sie das Blutdruckmittel ab.", "dosis"),
    ("Take 2 tablets three times a day.", "dosis"),
    ("Ihr Risiko für Darmkrebs ist deutlich erhöht.", "risiko"),
    ("Sie sind erblich vorbelastet.", "risiko"),
    ("You are at high risk of a stroke.", "risiko"),
])
def test_pruefe_antwort_findet_verstoesse(text, kategorie):
    verstoesse = pruefe_antwort(text)
    assert any(v.startswith(f"{kategorie}:") for v in verstoesse), verstoesse


@pytest.mark.parametrize("text", [
    "In Ihrem Entlassungsbrief wird eine ambulante Rehabilitation empfohlen (S. 3). Ich zeige Ihnen den Antrag.",
    "Laut Erstattungskodex ist das Medikament bewilligungspflichtig (gelbe Box).",
    "IBUPROFEN 400 mg Filmtabletten, 30 Stück: grüne Box.",
    "Sie haben vermutlich Anspruch auf eine Befreiung, wenn Ihr Einkommen unter der Grenze liegt.",
    "Bitte ändern Sie die Dosis nicht ohne ärztliche Rücksprache.",
    "Ob eine Reha nötig ist, entscheidet Ihre Ärztin oder Ihr Arzt.",
    "Für die Reha brauchen Sie eine ärztliche Begründung.",
    "Sie brauchen eine Reha-Bewilligung der Krankenversicherung.",
    "Nehmen Sie Kontakt mit der ÖGK auf oder nutzen Sie öffentliche Verkehrsmittel.",
    "Ein persönliches Risiko kann ich nicht beurteilen.",
    "Your doctor decides whether a treatment is needed.",
    "Do not stop taking your medication without asking your doctor.",
])
def test_pruefe_antwort_laesst_administrative_texte_durch(text):
    assert pruefe_antwort(text) == []


def test_eigene_grenz_antworten_und_katalogtexte_sind_unbedenklich():
    for antwort in grenzen.ANTWORTEN.values():
        assert pruefe_antwort(antwort["de"]) == [] and pruefe_antwort(antwort["en"]) == []
    for l in katalog.alle():
        for feld in [l.titel, l.kurz, l.details, *l.schritte, *l.unterlagen, *l.voraussetzungen]:
            for sprache in ("de", "en"):
                assert pruefe_antwort(feld[sprache]) == [], (l.id, sprache)
                assert pruefe_anfrage(feld[sprache]).erlaubt, (l.id, sprache)
