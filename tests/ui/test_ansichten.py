"""Ansichten „Gespräch“, „Mein Plan“, „Meine Akte“, Leistung und Termin (KISS-Struktur) und Erhalt aller Funktionen."""

from __future__ import annotations

import io
import json
import re
import unicodedata
from datetime import date

import pytest

from messung import (
    BRIEF_DATEI,
    DEMO_BRIEF,
    DEMO_DISCLOSURES,
    DEMO_IMPFPASS,
    IMPFPASS_DATEI,
    REPO,
    ansicht,
    datei_eingabe,
    demo,
    demo_oder_hochladen,
    dokument_hinzufuegen,
    einstellung,
    einstellungen_oeffnen,
    ist_api_post,
    laden,
    mit_antwort,
    nachricht,
    pflegefall,
    route,
    ruhe,
    sichtbar,
    termin,
)

pytestmark = pytest.mark.ui

# Öffentliches Musterbeispiel einer österreichischen SV-Nummer (Prüfziffer gültig), keine echte Person
MUSTER_SVNR = "1237010180"

KACHELN = {"Pflege": "pflege", "Nach dem Spital": "entlassung", "Gesundheit": "gesundheit", "Kind": "kind",
           "Geld & Unterstützung": "unterstuetzung", "Arzttermin": "termin"}
NAV = {"Gespräch": "#/gespraech", "Mein Plan": "#/plan", "Meine Akte": "#/akte"}


def texte(lotse_url: str) -> dict:
    import urllib.request

    return json.load(urllib.request.urlopen(lotse_url + "api/texte"))["texte"]


def abschnitt(page, titel, exact: bool = True):
    """Innerster sichtbarer Abschnitt (section/aside/region/details), der die Überschrift `titel` enthält."""
    kopf = page.get_by_role("heading", name=titel, exact=exact)
    return page.locator("section, aside, [role=region], details").filter(has=kopf).filter(visible=True).last


def aufklappen(page, text):
    """Öffnet den sichtbaren <details>-Bereich mit dieser Zusammenfassung (Text oder Regex); liefert ihn zurück."""
    summary = sichtbar(page.locator("summary").filter(has_text=text))
    details = summary.locator("xpath=..")
    if details.get_attribute("open") is None:
        summary.click()
    return details


def stand(page, lotse_url: str, sid: str) -> dict:
    return page.request.get(f"{lotse_url}api/sitzung/{sid}").json()


def buendel(a: dict, leistung_id: str) -> dict:
    return next(b for b in a["buendel"] if b["leistung_id"] == leistung_id)


def gedrueckt(loc) -> bool:
    return any(loc.get_attribute(a) == "true" for a in ("aria-pressed", "aria-checked")) or (
        loc.evaluate("(el) => el.checked === true"))


def hauptaktionen(page) -> list[str]:
    return page.locator(".hauptaktion").evaluate_all(
        "(els) => els.filter((e) => e.checkVisibility() && e.getClientRects().length).map((e) => e.textContent.trim())")


def formular_von(feld):
    return feld.locator("xpath=ancestor::form[1]")


def angabe_eintragen(page, label: str, wert: str):
    """Fehlende Angabe über „Eintragen <label>“ in „Meine Akte“ setzen; liefert die HTTP-Antwort."""
    page.get_by_role("button", name=f"Eintragen {label}").click()
    feld = page.get_by_role("textbox", name=re.compile(re.escape(label)))
    feld.fill(wert)
    with page.expect_response(ist_api_post) as info:
        formular_von(feld).get_by_role("button", name="Speichern").click()
    ruhe(page)
    return info.value


def termin_oeffnen(page, a: dict) -> dict:
    """Aus „Mein Plan“ über die Termin-Aufgabe in die Termin-Ansicht; liefert den Termin."""
    tm = a["termine"][0]
    ansicht(page, "Mein Plan")
    # Termin als Aufgabe: Link „#/termin/<id>“ oder – als nächster Schritt – Knopf „Termin öffnen“
    link = page.locator(f'a[href="#/termin/{tm["id"]}"]').or_(page.get_by_role("button", name="Termin öffnen"))
    sichtbar(link).click()
    sichtbar(page.get_by_role("heading", level=1, name=re.compile("^Termin"))).wait_for()
    ruhe(page)
    return tm


# ---------------------------------------------------------------------------
# KISS-Prüfungen
# ---------------------------------------------------------------------------


def test_kiss_navigation_und_kopfzeile(neue_seite, lotse_url):
    page = neue_seite("mobil_390")
    laden(page, lotse_url)
    nav = page.get_by_role("navigation", name="Hauptnavigation")
    links = nav.get_by_role("link")
    assert links.count() == 3
    for (name, ziel), link in zip(NAV.items(), links.all()):
        assert link.inner_text().strip().startswith(name) and link.get_attribute("href") == ziel
    banner = page.get_by_role("banner")
    bedienbar = banner.locator("a[href], button, input, select, textarea, summary, [tabindex]:not([tabindex='-1'])")
    assert [e.inner_text().strip() for e in bedienbar.all()] == ["Einstellungen"], "Kopfzeile: nur „Einstellungen“"


def test_kiss_genau_eine_hauptaktion_je_ansicht(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    gefunden = {"Gespräch (leer)": hauptaktionen(page)}
    a = nachricht(page, "Meine Mutter kommt allein nicht mehr zurecht")
    assert a["rueckfrage"]
    gefunden["Gespräch (Rückfrage)"] = hauptaktionen(page)
    a = pflegefall(page)
    gefunden["Gespräch (Fall)"] = hauptaktionen(page)
    ansicht(page, "Mein Plan")
    gefunden["Mein Plan"] = hauptaktionen(page)
    ansicht(page, "Meine Akte")
    gefunden["Meine Akte"] = hauptaktionen(page)
    route(page, "#/leistung/pflegegeld")
    gefunden["Leistung Pflegegeld"] = hauptaktionen(page)
    route(page, "#/leistung/pflegeberatung")
    gefunden["Leistung Pflegeberatung"] = hauptaktionen(page)
    ansicht(page, "Gespräch")
    tm = termin_oeffnen(page, termin(page))
    gefunden[f"Termin {tm['anlass_label']}"] = hauptaktionen(page)
    falsch = {k: v for k, v in gefunden.items() if len(v) != 1}
    assert not falsch, f"nicht genau eine sichtbare .hauptaktion: {falsch}"
    assert "Senden" in gefunden["Gespräch (leer)"][0]
    assert "Antrag herunterladen" in gefunden["Leistung Pflegegeld"][0]
    assert "Termin vorbereiten" in gefunden["Leistung Pflegeberatung"][0]
    assert "Dokument hinzufügen" in gefunden["Meine Akte"][0]
    assert re.search("Text kopieren|Kalender", gefunden[f"Termin {tm['anlass_label']}"][0])


def test_kiss_gespraech_ohne_leistungskarten_mit_naechstem_schritt(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    gespraech = page.locator("#ansicht-gespraech, main section:visible").first
    assert page.get_by_role("group", name="Worum geht es?").is_visible()
    assert page.get_by_role("group", name="Worum geht es?").get_by_role("button").count() == len(KACHELN)
    a = pflegefall(page)
    assert not page.get_by_role("group", name="Worum geht es?").is_visible()
    box = abschnitt(page, "Ihr nächster Schritt")
    # hervorgehobener nächster Schritt + höchstens 2 weitere Aufgaben
    assert box.get_by_role("listitem").count() <= 2
    primaer = [b for b in a["buendel"] if b["primaer"]]
    assert primaer[0]["titel"] in box.inner_text()
    eintrag = next(e for e in a["fallakte"]["eintraege"] if e["leistung_id"] == primaer[0]["leistung_id"])
    naechster = next(s for s in eintrag["schritte"] if s["id"] == eintrag["naechster_schritt"])
    assert naechster["text"] in box.inner_text()
    assert box.get_by_role("link", name="Zu meinem Plan").get_attribute("href") == "#/plan"
    # keine Leistungskarten: höchstens die ≤ 3 Aufgaben nennen Leistungen, keine Stellen/Formulare/Unterlagen
    text = gespraech.inner_text()
    genannt = [b["titel"] for b in a["buendel"] if b["titel"] in text]
    assert len(genannt) <= 3, genannt
    assert "Zuständige Stelle" not in text and "Unterlagen" not in text
    # nur EIN Vorlesen-Knopf (letzte Antwort)
    assert page.get_by_role("button", name=re.compile("^Vorlesen")).filter(visible=True).count() == 1
    # Quellen im Gespräch standardmäßig verborgen
    quellen = [q["titel"] for q in a.get("quellen", []) if q["titel"] in page.get_by_role("log").inner_text()]
    assert not quellen, f"Quellen sichtbar, obwohl „Belege anzeigen“ aus ist: {quellen}"


# ---------------------------------------------------------------------------
# Gespräch
# ---------------------------------------------------------------------------


def test_kacheln_senden_die_bisherigen_beispielsaetze(neue_seite, lotse_url):
    saetze = texte(lotse_url)["beispiele_saetze"]
    for name, key in KACHELN.items():
        page = neue_seite("mobil_390")
        laden(page, lotse_url)
        gruppe = page.get_by_role("group", name="Worum geht es?")
        knopf = gruppe.get_by_role("button", name=re.compile("^" + re.escape(name)))
        with page.expect_request(lambda r: r.url.endswith("/nachricht")) as anfrage:
            knopf.click()
        assert anfrage.value.post_data_json["text"] == saetze[key], name
        ruhe(page)
        assert page.get_by_role("log").get_by_text(saetze[key]).count() >= 1
        page.context.close()


def test_neuen_fall_beginnen_in_der_akte(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    alt = pflegefall(page)
    ansicht(page, "Meine Akte")
    page.once("dialog", lambda d: d.accept())  # Rückfrage per window.confirm, weil der Fall Inhalt hat
    neu = mit_antwort(page, page.get_by_role("button", name="Neuen Fall beginnen").click)
    assert neu["sitzung_id"] != alt["sitzung_id"] and not neu["buendel"]
    if page.evaluate("location.hash") not in ("", "#/gespraech"):
        ansicht(page, "Gespräch")
    assert page.get_by_role("group", name="Worum geht es?").is_visible()


def test_demo_dokumente_und_ki_hinweis(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    aufklappen(page, DEMO_DISCLOSURES[0])
    for name in (DEMO_BRIEF, DEMO_IMPFPASS):
        assert sichtbar(page.get_by_role("button", name=name)).is_enabled(), name
    foto = sichtbar(page.get_by_role("button", name=re.compile("Foto eines Entlassungsbriefs")))
    hinweis = foto.inner_text() + (foto.get_attribute("title") or "") + foto.evaluate("(el) => el.parentElement.textContent")
    assert foto.is_disabled() and "nur im KI-Modus" in hinweis
    a = demo(page, DEMO_BRIEF)
    assert a["dokumente"] and a["medikamente"]
    a = demo_oder_hochladen(page, DEMO_IMPFPASS, IMPFPASS_DATEI)
    assert len(a["dokumente"]) == 2 and a["impfungen"]


def test_dokument_hinzufuegen_ein_knopf_fuer_datei_und_foto(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    eingabe = datei_eingabe(page, "Dokument hinzufügen")
    assert eingabe.get_attribute("type") == "file"
    accept = eingabe.get_attribute("accept")
    assert all(x in accept for x in (".pdf", ".txt", "image/")), accept
    a = dokument_hinzufuegen(page, BRIEF_DATEI)
    assert [d["name"] for d in a["dokumente"]] == [BRIEF_DATEI.name]
    ansicht(page, "Meine Akte")
    assert BRIEF_DATEI.name in abschnitt(page, "Ihre Dokumente").inner_text()
    # in „Meine Akte“ ist „Dokument hinzufügen“ die Hauptaktion
    a = dokument_hinzufuegen(page, IMPFPASS_DATEI)
    assert IMPFPASS_DATEI.name in [d["name"] for d in a["dokumente"]]


def test_mikrofon_nur_mit_web_speech(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    hat = page.evaluate("() => 'SpeechRecognition' in window || 'webkitSpeechRecognition' in window")
    mikro = page.get_by_role("button", name=re.compile("Spracheingabe"))
    assert (mikro.filter(visible=True).count() > 0) == hat
    ohne = neue_seite("desktop")
    ohne.add_init_script("delete window.SpeechRecognition; delete window.webkitSpeechRecognition;")
    laden(ohne, lotse_url)
    assert ohne.get_by_role("button", name=re.compile("Spracheingabe")).filter(visible=True).count() == 0


def _vorgelesen(page, aktion) -> list[dict]:
    """Äußerungen, die `aktion` an speechSynthesis übergibt (Mitschrift aus conftest)."""
    vorher = page.evaluate("window.__gesprochen.length")
    aktion()
    page.wait_for_timeout(100)
    return page.evaluate("(n) => window.__gesprochen.slice(n)", vorher)


def test_vorlesen_ganze_antwort_tempo_und_stopp(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    a = nachricht(page, "Meine Mutter kommt allein nicht mehr zurecht")
    assert a["rueckfrage"]
    knopf = sichtbar(page.get_by_role("button", name=re.compile("^Vorlesen")))
    teile = _vorgelesen(page, knopf.click)
    text = " ".join(t["text"] for t in teile)
    assert teile and all(t["lang"].startswith("de") for t in teile)
    assert a["rueckfrage"]["frage"] in text, "Rückfrage wird nicht mit vorgelesen"
    assert not re.search(r"\[\d+\]", text), "Quellenmarker werden mitgelesen"
    assert gedrueckt(knopf)
    abgebrochen = page.evaluate("window.__abgebrochen")
    knopf.click()
    assert page.evaluate("window.__abgebrochen") > abgebrochen
    assert not gedrueckt(knopf)
    raten = {}
    for tempo in ("Langsam", "Normal", "Schnell"):
        einstellung(page, "Vorlesetempo", tempo)
        teile = _vorgelesen(page, knopf.click)
        assert len({t["rate"] for t in teile}) == 1
        raten[tempo] = teile[0]["rate"]
        knopf.click()
    assert raten["Langsam"] < raten["Normal"] < raten["Schnell"], raten
    pflegefall(page)
    assert page.get_by_role("button", name=re.compile("^Vorlesen")).filter(visible=True).count() == 1
    ansicht(page, "Mein Plan")
    plan = " ".join(t["text"] for t in _vorgelesen(page, page.get_by_role("button", name="Plan vorlesen").click))
    assert "Pflegegeld" in plan


def test_medizinische_grenze_im_dialog_und_im_gespraech(neue_seite, lotse_url):
    page = neue_seite("mobil_390")
    laden(page, lotse_url)
    t = texte(lotse_url)
    inhalt = re.sub(r"\s+", " ", einstellungen_oeffnen(page).inner_text())
    assert re.sub(r"\s+", " ", t["grenze_hinweis"]).strip() in inhalt
    assert t["quelle_1450"]["titel"] in inhalt and t["quelle_1450"]["fundstelle"] in inhalt
    assert "regelbasiert" in inhalt
    page.keyboard.press("Escape")
    a = nachricht(page, "Ist mein Befund schlimm?")
    assert a["grenze"], "medizinische Frage nicht als Grenzfall erkannt"
    assert re.search("Ärztin|Arzt|1450", page.get_by_role("log").get_by_role("listitem").last.inner_text())


# ---------------------------------------------------------------------------
# Mein Plan
# ---------------------------------------------------------------------------


def _aktion(b: dict) -> str:
    if b.get("formular"):
        return "Antrag vorbereiten"
    if b.get("termin_anlass"):
        return "Termin vorbereiten"
    return "Details ansehen"


def test_plan_ein_naechster_schritt_hoechstens_zwei_aufgaben_und_weitere(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    a = pflegefall(page)
    ansicht(page, "Mein Plan")
    main = page.get_by_role("main")
    primaer = [b for b in a["buendel"] if b["primaer"]]
    weitere = [b for b in a["buendel"] if not b["primaer"]]
    schritt = abschnitt(page, "Ihr nächster Schritt")
    assert primaer[0]["titel"] in schritt.inner_text()
    eintrag = next(e for e in a["fallakte"]["eintraege"] if e["leistung_id"] == primaer[0]["leistung_id"])
    naechster = next(s for s in eintrag["schritte"] if s["id"] == eintrag["naechster_schritt"])
    assert naechster["text"] in schritt.inner_text()
    aktionen = [n for n in ("Antrag vorbereiten", "Termin vorbereiten", "Details ansehen")
                if schritt.get_by_role("button", name=n).or_(schritt.get_by_role("link", name=n)).count()]
    assert aktionen == [_aktion(primaer[0])]
    sichtbare_titel = [b["titel"] for b in primaer if b["titel"] in main.inner_text()]
    assert sichtbare_titel == [b["titel"] for b in primaer][:3], "Plan: nächster Schritt + höchstens 2 Aufgaben"
    weiter = page.locator("details").filter(has=page.locator("summary", has_text=f"Weitere Möglichkeiten ({len(weitere)})"))
    assert weiter.count() == 1 and weiter.get_attribute("open") is None, "„Weitere Möglichkeiten“ eingeklappt"
    aufklappen(page, "Weitere Möglichkeiten")
    links = weiter.get_by_role("link")
    assert sorted(lk.get_attribute("href") for lk in links.all()) == sorted(
        f"#/leistung/{b['leistung_id']}" for b in weitere)
    assert page.get_by_role("button", name="Plan drucken").is_visible()
    assert page.get_by_role("button", name="Plan vorlesen").is_visible()


def test_plan_erledigt_umschalten(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    a = pflegefall(page)
    ansicht(page, "Mein Plan")
    knopf = page.get_by_role("main").get_by_role("button", name="Erledigt", exact=True).first
    assert knopf.get_attribute("aria-pressed") == "false"
    mit_antwort(page, knopf.click)
    eintrag = next(e for e in stand(page, lotse_url, a["sitzung_id"])["fallakte"]["eintraege"]
                   if e["leistung_id"] == "pflegegeld")
    assert any(s["status"] == "erledigt" for s in eintrag["schritte"])
    assert page.evaluate("() => document.activeElement !== document.body")


def test_termin_vorbereiten_aus_der_leistung(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    pflegefall(page)
    route(page, "#/leistung/pflegeberatung")
    a = mit_antwort(page, sichtbar(page.locator(".hauptaktion")).click)
    assert a["termine"] or (a.get("rueckfrage") and a["rueckfrage"]["slot"].startswith("termin."))


# ---------------------------------------------------------------------------
# Meine Akte
# ---------------------------------------------------------------------------


def test_angabe_aendern_validieren_und_loeschen(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    a = pflegefall(page)
    sid = a["sitzung_id"]
    ansicht(page, "Meine Akte")
    angaben = abschnitt(page, "Ihre Angaben")
    angaben.get_by_role("button", name="Ändern Bundesland").click()
    auswahl = page.get_by_role("combobox", name=re.compile("Bundesland"))
    assert auswahl.is_visible()
    assert formular_von(auswahl).get_by_role("button", name="Abbrechen").is_visible()
    auswahl.select_option("Niederösterreich")
    mit_antwort(page, formular_von(auswahl).get_by_role("button", name="Speichern").click)
    assert any(x["slot"] == "person.bundesland" and x["wert"] == "Niederösterreich"
               for x in stand(page, lotse_url, sid)["angaben"])
    assert "Niederösterreich" in abschnitt(page, "Ihre Angaben").inner_text()
    assert page.evaluate("() => document.activeElement !== document.body")
    # Fehlende Angabe mit ungültigem Wert: Meldung, aria-invalid und aria-describedby
    antwort = angabe_eintragen(page, "Postleitzahl", "12")
    assert antwort.status == 400
    plz = page.get_by_role("textbox", name=re.compile("Postleitzahl"))
    assert plz.get_attribute("aria-invalid") == "true"
    beschreibung = plz.get_attribute("aria-describedby") or ""
    meldung = " ".join(page.locator(f"#{i}").inner_text() for i in beschreibung.split() if i)
    assert meldung.strip(), "Fehlermeldung nicht über aria-describedby verknüpft"
    assert page.evaluate("() => document.activeElement !== document.body")
    formular_von(plz).get_by_role("button", name="Abbrechen").click()
    # Löschen entfernt die Angabe
    abschnitt(page, "Ihre Angaben").get_by_role("button", name="Ändern Bundesland").click()
    mit_antwort(page, page.get_by_role("button", name="Löschen").click)
    assert not any(x["slot"] == "person.bundesland" for x in stand(page, lotse_url, sid)["angaben"])


@pytest.mark.daten
def test_fehlende_angaben_fuellen_das_pdf_und_sensible_bleiben_verdeckt(neue_seite, lotse_url):
    from pypdf import PdfReader

    page = neue_seite("desktop")
    laden(page, lotse_url)
    pflegefall(page)
    ansicht(page, "Meine Akte")
    assert abschnitt(page, "Für Formulare fehlen noch").is_visible()
    assert angabe_eintragen(page, "Straße", "Musterweg").status == 200
    a = angabe_eintragen(page, "Sozialversicherungsnummer", MUSTER_SVNR).json()
    assert any(x["slot"] == "person.svnr" for x in a["angaben"])
    assert MUSTER_SVNR not in page.locator("body").inner_text(), "sensibler Wert sichtbar"
    assert MUSTER_SVNR not in page.content(), "sensibler Wert im DOM"
    url = buendel(a, "pflegegeld")["formular"]["url"]
    pdf = page.request.get(lotse_url.rstrip("/") + url)
    assert pdf.status == 200 and pdf.body().startswith(b"%PDF")
    werte = {str(f.get("/V", "")) for f in (PdfReader(io.BytesIO(pdf.body())).get_fields() or {}).values()}
    assert "Musterweg" in werte


def test_akte_dokumente_impfungen_und_erstattungsstatus(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    demo_oder_hochladen(page, DEMO_BRIEF, BRIEF_DATEI)
    a = demo_oder_hochladen(page, DEMO_IMPFPASS, IMPFPASS_DATEI)
    ansicht(page, "Meine Akte")
    dok = abschnitt(page, "Ihre Dokumente")
    assert BRIEF_DATEI.name in dok.inner_text() and IMPFPASS_DATEI.name in dok.inner_text()
    impf = aufklappen(page, re.compile("Impfpass"))
    tabelle = impf.get_by_role("table")
    assert [c.inner_text().strip() for c in tabelle.get_by_role("columnheader").all()] == ["Impfung", "Datum", "Fundstelle"]
    assert tabelle.get_by_role("row").count() == len(a["impfungen"]) + 1
    eko = aufklappen(page, re.compile("Erstattungsstatus"))
    for m in a["medikamente"]:
        assert m["name_dokument"] in eko.inner_text()


def test_erstattungsstatus_zeigt_varianten(neue_seite, lotse_url):
    """Vorlage: gemischte Boxen werden je Variante mit Anzahl und Beispiel angezeigt."""
    page = neue_seite("desktop")

    def mit_varianten(route_, request):
        antwort = route_.fetch()
        daten = antwort.json()
        if daten.get("medikamente"):
            m = daten["medikamente"][0]
            m["eko"] = dict(m["eko"] or {}, einheitlich=False, box="", kennzeichen=[], anzahl=3, varianten=[
                {"box": "gruen", "kennzeichen": [], "anzahl": 2, "beispiel": {"name": "Testin 10 mg Tabl.", "pzn": "1000001"}},
                {"box": "gelb", "kennzeichen": ["RE1"], "anzahl": 1, "beispiel": {"name": "Testin 40 mg Tabl.", "pzn": "1000003"}},
            ])
        route_.fulfill(response=antwort, json=daten)

    page.route(re.compile(r".*/api/sitzung/\w+/(demo/entlassungsbrief_synthetisch\.txt|dokument)$"), mit_varianten)
    page.route(re.compile(r".*/api/sitzung/\w+$"), mit_varianten)
    laden(page, lotse_url)
    demo_oder_hochladen(page, DEMO_BRIEF, BRIEF_DATEI)
    ansicht(page, "Meine Akte")
    eko = aufklappen(page, re.compile("Erstattungsstatus")).inner_text()
    for erwartet in ("Grüne Box", "Gelbe Box", "RE1", "2 Einträge", "1 Eintrag", "Testin 40 mg Tabl."):
        assert erwartet in eko, erwartet


def test_fall_speichern_und_laden(neue_seite, lotse_url, tmp_path):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    a = pflegefall(page)
    ansicht(page, "Meine Akte")
    with page.expect_download() as dl:
        page.get_by_role("link", name="Fall speichern").click()
    ziel = tmp_path / "fall.json"
    dl.value.save_as(ziel)
    assert json.loads(ziel.read_text(encoding="utf-8"))
    neu = neue_seite("desktop")
    laden(neu, lotse_url)
    ansicht(neu, "Meine Akte")
    b = mit_antwort(neu, lambda: datei_eingabe(neu, "Fall laden").set_input_files(str(ziel)))
    assert [x["leistung_id"] for x in b["buendel"] if x["primaer"]] == [
        x["leistung_id"] for x in a["buendel"] if x["primaer"]]
    ansicht(neu, "Mein Plan")
    assert buendel(a, "pflegegeld")["titel"] in abschnitt(neu, "Ihr nächster Schritt").inner_text()


# ---------------------------------------------------------------------------
# Leistung
# ---------------------------------------------------------------------------


@pytest.mark.daten
def test_leistung_aufbau_hauptaktion_pdf_und_mehr(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    a = pflegefall(page)
    b = buendel(a, "pflegegeld")
    route(page, "#/leistung/pflegegeld")
    main = page.get_by_role("main")
    assert b["kurz"] in main.inner_text()
    stelle = abschnitt(page, "Zuständige Stelle")
    assert b["stelle"]["name"] in stelle.inner_text()
    haupt = sichtbar(page.locator(".hauptaktion"))
    href = haupt.get_attribute("href")
    assert "Antrag herunterladen" in haupt.inner_text() and "leistung=pflegegeld" in href
    r = page.request.get(lotse_url.rstrip("/") + href)
    assert r.status == 200 and r.headers["content-type"].startswith("application/pdf") and r.body().startswith(b"%PDF")
    assert abschnitt(page, "Unterlagen").get_by_role("checkbox").count() >= 1
    mehr = page.locator("details").filter(has=page.locator("summary", has_text="Mehr zu dieser Leistung"))
    assert mehr.count() == 1 and mehr.get_attribute("open") is None
    belege = page.locator("details").filter(has=page.locator("summary", has_text=f"Belege ({len(b['quellen'])})"))
    assert belege.count() == 1 and belege.get_attribute("open") is None
    aufklappen(page, "Mehr zu dieser Leistung")
    assert b["nutzen"] in mehr.inner_text()
    ergaenzen = mehr.get_by_role("link", name=re.compile("ergänzen"))
    assert ergaenzen.count() >= 1 and ergaenzen.first.get_attribute("href").startswith("#/akte")
    aufklappen(page, re.compile(r"^Belege \("))
    assert b["quellen"][0]["titel"] in belege.inner_text()
    assert page.get_by_role("link", name="Zurück zu Mein Plan").count() >= 1


def test_leistung_unterlagen_und_schrittstatus_bleiben_gespeichert(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    a = pflegefall(page)
    sid = a["sitzung_id"]
    route(page, "#/leistung/pflegegeld")
    box = abschnitt(page, "Unterlagen").get_by_role("checkbox").first
    assert not box.is_checked()
    mit_antwort(page, box.check)
    assert buendel(stand(page, lotse_url, sid), "pflegegeld")["unterlagen"][0]["status"] == "erledigt"
    mehr = aufklappen(page, "Mehr zu dieser Leistung")
    in_arbeit = mehr.get_by_role("radio", name="In Arbeit").first
    mit_antwort(page, in_arbeit.click)
    eintrag = next(e for e in stand(page, lotse_url, sid)["fallakte"]["eintraege"] if e["leistung_id"] == "pflegegeld")
    assert eintrag["schritte"][0]["status"] == "in_arbeit"
    ansicht(page, "Mein Plan")
    route(page, "#/leistung/pflegegeld")
    assert abschnitt(page, "Unterlagen").get_by_role("checkbox").first.is_checked()
    mehr = aufklappen(page, "Mehr zu dieser Leistung")
    assert mehr.get_by_role("radio", name="In Arbeit").first.is_checked()


def test_leichte_sprache_zeigt_leicht_text(neue_seite, lotse_url):
    katalog = json.loads((REPO / "lotse" / "data" / "leistungen.json").read_text(encoding="utf-8"))
    eintraege = katalog if isinstance(katalog, list) else katalog.get("leistungen", katalog)
    eintraege = list(eintraege.values()) if isinstance(eintraege, dict) else eintraege
    leicht = next(x for x in eintraege if x["id"] == "pflegegeld")["leicht"]["de"]
    page = neue_seite("desktop")
    laden(page, lotse_url)
    einstellung(page, "Darstellung", "Leichte Sprache")
    a = pflegefall(page)
    assert a["stil"] == "leicht"
    route(page, "#/leistung/pflegegeld")
    assert re.sub(r"\s+", " ", leicht) in re.sub(r"\s+", " ", page.get_by_role("main").inner_text())


def test_englisch_umschalten(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    einstellung(page, "Sprache", "English")
    page.wait_for_timeout(300)
    ruhe(page)
    assert page.evaluate("document.documentElement.lang").startswith("en")
    assert page.get_by_role("button", name="Send", exact=True).count() >= 1


# ---------------------------------------------------------------------------
# Belege und Termin
# ---------------------------------------------------------------------------


def test_belege_standardmaessig_verborgen_und_einschaltbar(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    a = nachricht(page, "Was regelt das ASVG zur Rezeptgebühr?")
    log = page.get_by_role("log")
    assert a["quellen"], "Wissensantwort ohne Quellen"
    # aus: weder [n]-Verweise noch Quellenliste (Fundstelle, Stand) im Gespräch
    assert not re.search(r"\[\d+\]", log.inner_text()) and "Fundstelle" not in log.inner_text()
    schalter = einstellungen_oeffnen(page).get_by_role("switch", name="Belege anzeigen")
    schalter.click()
    page.keyboard.press("Escape")
    assert re.search(r"\[\d+\]", log.inner_text()), "[n]-Verweise fehlen bei eingeschalteten Belegen"
    if "Fundstelle" not in log.inner_text():
        aufklappen(page, re.compile(r"^(Belege|Quellen)"))
    assert "Fundstelle" in log.inner_text() and a["quellen"][0]["titel"] in log.inner_text()
    # in Leistung und Termin: Quellen im eingeklappten Bereich „Belege (N)“
    pflegefall(page)
    route(page, "#/leistung/pflegegeld")
    assert page.locator("summary").filter(has_text=re.compile(r"^Belege \(\d+\)")).filter(visible=True).count() == 1


def test_termin_ansicht_kopieren_datum_ics_erledigt(neue_seite, lotse_url):
    page = neue_seite("desktop", permissions=["clipboard-read", "clipboard-write"])
    laden(page, lotse_url)
    a = termin(page)
    tm = termin_oeffnen(page, a)
    assert tm["anlass_label"] in sichtbar(page.get_by_role("heading", level=1)).inner_text()
    page.get_by_role("button", name="Text kopieren").click()
    page.wait_for_timeout(300)
    assert "Text kopiert" in page.get_by_role("main").inner_text()
    assert page.evaluate("navigator.clipboard.readText()") == tm["anfrage_text"]
    page.get_by_label("Datum").fill("2026-12-01")
    page.get_by_label("Uhrzeit").fill("09:30")
    a = mit_antwort(page, page.get_by_role("button", name="Termin speichern").click)
    assert a["termine"][0]["status"] == "vereinbart" and a["termine"][0]["datum"] == "01.12.2026"
    ics = sichtbar(page.get_by_role("link", name=re.compile(r"\.ics")))
    assert "hauptaktion" in (ics.get_attribute("class") or "")
    r = page.request.get(lotse_url.rstrip("/") + ics.get_attribute("href"))
    assert r.status == 200 and "text/calendar" in r.headers["content-type"]
    assert "BEGIN:VCALENDAR" in r.text() and "DTSTART" in r.text()
    a = mit_antwort(page, page.get_by_role("button", name="Als erledigt markieren").click)
    assert a["termine"][0]["status"] == "erledigt"
    assert aufklappen(page, re.compile(r"^Belege \(")).inner_text()
    assert aufklappen(page, re.compile(r"^So gehen Sie vor")).get_by_role("listitem").count() >= 1


# ---------------------------------------------------------------------------
# Funktionserhalt: jede bisherige Funktion über höchstens 2 Schritte
# ---------------------------------------------------------------------------

# (Funktion der alten Oberfläche, Weg in der neuen Oberfläche, Prüfung am Ziel)
# Weg-Schritte: ("nav", Ansicht) | ("route", Hash) | ("auf", Summary-Text/Regex) | ("dialog",)
FUNKTIONEN = [
    ("Nachricht senden, Rückfrage-Antworten, Vorlesen", [],
     lambda p: p.get_by_role("button", name="Senden", exact=True).is_visible()
     and p.get_by_role("button", name=re.compile("^Vorlesen")).filter(visible=True).count() == 1),
    ("Dokument hochladen / Foto aufnehmen", [],
     lambda p: p.locator("label").filter(has_text="Dokument hinzufügen").filter(visible=True).count() >= 1),
    ("Nächster Schritt", [], lambda p: p.get_by_role("heading", name="Ihr nächster Schritt").is_visible()),
    ("Sprache, Darstellung, Leichte Sprache, Textgröße, Farbschema, Vorlesetempo", [("dialog",)],
     lambda p: p.get_by_role("dialog", name="Einstellungen").get_by_role("radiogroup").count() >= 5),
    ("Modus-Anzeige und medizinische Grenze mit Quelle", [("dialog",)],
     lambda p: "regelbasiert" in p.get_by_role("dialog").inner_text() and "1450" in p.get_by_role("dialog").inner_text()),
    ("Quellen zu jeder Aussage (Schalter „Belege anzeigen“)", [("dialog",)],
     lambda p: p.get_by_role("switch", name="Belege anzeigen").is_visible()),
    ("Fortschritt und Schritte der Fallakte", [("nav", "Mein Plan")],
     lambda p: p.get_by_role("heading", name="Ihr nächster Schritt").is_visible()),
    ("Weitere Angebote", [("nav", "Mein Plan"), ("auf", "Weitere Möglichkeiten")],
     lambda p: p.locator('details[open] a[href^="#/leistung/"]').count() >= 1),
    ("Leistung: Kurztext, zuständige Stelle, Kontakt, Formular-Download, Unterlagen-Checkliste",
     [("nav", "Mein Plan"), ("route", "#/leistung/pflegegeld")],
     lambda p: p.locator(".hauptaktion").filter(visible=True).count() == 1
     and p.get_by_role("heading", name="Zuständige Stelle").is_visible()
     and p.get_by_role("checkbox").filter(visible=True).count() >= 1),
    ("Leistung: Nutzen, Details, Voraussetzungen, Region, Einrichtungen, Schritte mit Status",
     [("route", "#/leistung/pflegegeld"), ("auf", "Mehr zu dieser Leistung")],
     lambda p: p.get_by_role("radio", name="In Arbeit").filter(visible=True).count() >= 1),
    ("Leistung: Belege", [("route", "#/leistung/pflegegeld"), ("auf", re.compile(r"^Belege \("))],
     lambda p: p.locator("details[open]").filter(has=p.locator("summary", has_text="Belege")).count() >= 1),
    ("Angaben ansehen und ändern, fehlende Angaben", [("nav", "Meine Akte")],
     lambda p: p.get_by_role("button", name="Ändern Bundesland").is_visible()
     and p.get_by_role("heading", name="Für Formulare fehlen noch").is_visible()),
    ("Fall speichern, Fall laden, Neuer Fall", [("nav", "Meine Akte")],
     lambda p: p.get_by_role("link", name="Fall speichern").is_visible()
     and p.locator("label").filter(has_text="Fall laden").filter(visible=True).count() == 1
     and p.get_by_role("button", name="Neuen Fall beginnen").is_visible()),
]


@pytest.mark.parametrize("funktion", FUNKTIONEN, ids=[f[0][:40] for f in FUNKTIONEN])
def test_funktion_in_hoechstens_zwei_schritten(neue_seite, lotse_url, funktion):
    name, weg, pruefung = funktion
    assert len(weg) <= 2, f"„{name}“ braucht {len(weg)} Schritte"
    page = neue_seite("mobil_390")
    laden(page, lotse_url)
    pflegefall(page)
    for schritt in weg:
        if schritt[0] == "nav":
            ansicht(page, schritt[1])
        elif schritt[0] == "route":
            route(page, schritt[1])
        elif schritt[0] == "auf":
            aufklappen(page, schritt[1])
        elif schritt[0] == "dialog":
            einstellungen_oeffnen(page)
    assert pruefung(page), f"„{name}“ nach {weg} nicht erreichbar"


def test_funktion_termin_und_dokumente_in_hoechstens_zwei_schritten(neue_seite, lotse_url):
    """Termin-Karte (Plan → Termin) und Dokumente/Impfungen/Erstattungsstatus (Akte → aufklappen)."""
    page = neue_seite("mobil_390")
    laden(page, lotse_url)
    a = termin(page)
    termin_oeffnen(page, a)  # Schritt 1: Mein Plan, Schritt 2: Termin-Aufgabe
    assert page.get_by_role("button", name="Text kopieren").is_visible()
    assert page.get_by_label("Datum").is_visible() and page.get_by_role("button", name="Termin speichern").is_visible()
    ansicht(page, "Gespräch")
    demo_oder_hochladen(page, DEMO_BRIEF, BRIEF_DATEI)
    demo_oder_hochladen(page, DEMO_IMPFPASS, IMPFPASS_DATEI)
    ansicht(page, "Meine Akte")  # Schritt 1
    assert aufklappen(page, re.compile("Impfpass")).get_by_role("table").is_visible()  # Schritt 2
    assert aufklappen(page, re.compile("Erstattungsstatus")).inner_text()


# ---------------------------------------------------------------------------
# Druck
# ---------------------------------------------------------------------------


@pytest.mark.daten
def test_druckansicht_und_pdf(neue_seite, lotse_url, tmp_path):
    from pypdf import PdfReader

    page = neue_seite("desktop")
    laden(page, lotse_url)
    a = pflegefall(page)
    ansicht(page, "Meine Akte")
    assert angabe_eintragen(page, "Sozialversicherungsnummer", MUSTER_SVNR).status == 200
    ansicht(page, "Mein Plan")
    page.emulate_media(media="print")
    assert not page.get_by_role("navigation", name="Hauptnavigation").is_visible()
    assert not page.get_by_role("log").is_visible()
    assert not page.get_by_role("textbox", name="Ihre Nachricht").is_visible()
    assert page.get_by_role("banner").get_by_role("button", name="Einstellungen").filter(visible=True).count() == 0
    assert page.get_by_role("button").filter(visible=True).count() == 0, "Bedienknöpfe im Druck sichtbar"
    text = page.locator("body").inner_text()
    primaer = [b for b in a["buendel"] if b["primaer"]]
    for b in primaer:
        assert b["titel"] in text and b["stelle"]["name"] in text
    assert "Unterlagen" in text and MUSTER_SVNR not in text
    heute = date.today()
    assert heute.strftime("%d.%m.%Y") in text or f"{heute.day}.{heute.month}.{heute.year}" in text
    ziel = tmp_path / "plan.pdf"
    page.pdf(path=str(ziel), format="A4")
    pdf = PdfReader(str(ziel))
    assert len(pdf.pages) >= 1
    # NFKC: Ligaturen (ﬂ, ﬁ) und zerlegte Umlaute aus der PDF-Textextraktion vereinheitlichen
    pdf_text = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", " ".join(p.extract_text() or "" for p in pdf.pages)))
    assert primaer[0]["titel"] in pdf_text and primaer[0]["stelle"]["name"] in pdf_text
    assert MUSTER_SVNR not in pdf_text
    page.emulate_media(media="screen")
    assert page.get_by_role("navigation", name="Hauptnavigation").is_visible()
