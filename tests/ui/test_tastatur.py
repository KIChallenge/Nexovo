"""Bedienung nur mit der Tastatur: Sprunglink, Gespräch, Navigation, Plan, Angaben, Einstellungen, Drucken.

Jeder Tab-Halt muss eine sichtbare Fokusanzeige (outline oder box-shadow ≥ 2 px) haben, und nach
Aktionen darf der Fokus nie auf `body` zurückfallen.
"""

from __future__ import annotations

import re

import pytest

from messung import (
    PFLEGE_SATZ,
    einstellungen_oeffnen,
    fokus,
    fokus_aria,
    hilfen,
    ist_api_post,
    laden,
    ruhe,
    sichtbar,
    tab_zu,
)

pytestmark = pytest.mark.ui

ANTWORTEN = [("Wien", r'button "Wien"'), ("PVA", r'button "PVA"'), ("ÖGK", r'button "ÖGK"'),
             ("Nein", r'button "Nein')]


class Fokuspruefung:
    """Sammelt Halte ohne sichtbare Fokusanzeige und Fokusverluste."""

    def __init__(self, page):
        self.page = page
        self.ohne_anzeige: list[str] = []
        self.verloren: list[str] = []

    def __call__(self, info):
        # info None = Tab hat das Dokumentende überschritten (Fokus im Browser-Rahmen) – kein Fehler
        if info is not None and info["fokus_px"] < 2:
            self.ohne_anzeige.append(f"<{info['tag']}> „{info['name']}“ ({info['fokus_px']} px)")

    def nach_aktion(self, schritt: str):
        ruhe(self.page)
        if fokus(self.page) is None:
            self.verloren.append(f"nach „{schritt}“ liegt der Fokus auf body")

    def tab_zu(self, muster, **kw) -> str:
        return tab_zu(self.page, muster, pruefen=self, **kw)

    def enter(self, schritt: str, api: bool = False):
        if api:
            with self.page.expect_response(ist_api_post, timeout=30000):
                self.page.keyboard.press("Enter")
        else:
            self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(250)
        self.nach_aktion(schritt)

    def bilanz(self):
        assert not self.ohne_anzeige, f"Fokus nicht sichtbar: {self.ohne_anzeige[:15]}"
        assert not self.verloren, f"Fokus verloren: {self.verloren}"


def _h1_fokussiert(page, text: str) -> None:
    info = page.evaluate("() => [document.activeElement.tagName, document.activeElement.textContent.trim()]")
    assert info[0] == "H1" and text in info[1], f"Fokus nach Routenwechsel auf {info}, erwartet h1 „{text}“"


@pytest.mark.parametrize("viewport", ["desktop", "mobil_390"])
def test_kompletter_ablauf_nur_mit_tastatur(neue_seite, lotse_url, viewport):
    page = neue_seite(viewport)
    laden(page, lotse_url)
    hilfen(page)
    f = Fokuspruefung(page)

    # 1. Sprunglink ist der erste Tab-Halt und führt in den Inhalt
    page.keyboard.press("Tab")
    zeile = fokus_aria(page)
    assert zeile.startswith("- link"), f"erster Tab-Halt ist kein Sprunglink: {zeile}"
    assert page.evaluate("() => document.activeElement.getAttribute('href') || ''").startswith("#")
    box = page.evaluate("() => { const r = document.activeElement.getBoundingClientRect(); return [r.top, r.bottom]; }")
    assert box[0] >= 0 and box[1] <= page.viewport_size["height"], f"Sprunglink bei Fokus nicht sichtbar: {box}"
    f(fokus(page))
    f.enter("Sprunglink")
    assert page.evaluate("""() => { const a = document.activeElement; const m = document.querySelector('main');
                                    return Boolean(m && (m.contains(a) || a === m)); }"""), "Sprunglink führt nicht in main"

    # 2. Kachel „Pflege“ per Tastatur
    f.tab_zu(r'button "Pflege')
    with page.expect_response(ist_api_post, timeout=30000) as info:
        page.keyboard.press("Enter")
    a = info.value.json()
    f.nach_aktion("Kachel Pflege")
    assert a.get("rueckfrage"), "Pflege-Kachel ohne Rückfrage"

    # 3. Alle Rückfragen per Tastatur beantworten
    for _ in range(6):
        if not a.get("rueckfrage"):
            break
        labels = [o["label"] for o in a["rueckfrage"]["optionen"]]
        bekannt = next(((n, m) for n, m in ANTWORTEN if any(lbl.startswith(n) for lbl in labels)), None)
        assert bekannt, f"unerwartete Rückfrage {a['rueckfrage']['frage']!r} {labels}"
        f.tab_zu(bekannt[1])
        with page.expect_response(ist_api_post, timeout=30000) as info:
            page.keyboard.press("Enter")
        a = info.value.json()
        f.nach_aktion(f"Antwort {bekannt[0]}")
    assert not a.get("rueckfrage"), "Rückfragen nicht vollständig beantwortet"

    # 4. „Mein Plan“ über die Hauptnavigation
    f.tab_zu(r'link "Mein Plan')
    f.enter("Mein Plan")
    assert page.evaluate("location.hash") == "#/plan"
    _h1_fokussiert(page, "Mein Plan")
    assert "Mein Plan" in page.title()
    page.wait_for_timeout(300)
    assert page.locator('[aria-live="polite"], [role="status"]').filter(has_text="Mein Plan").count() >= 1

    # 5. Ersten nächsten Schritt öffnen (Pflegegeld hat ein Formular → „Antrag vorbereiten“)
    zeile = f.tab_zu(r'button "(Antrag vorbereiten|Termin vorbereiten|Details ansehen)')
    assert "Antrag vorbereiten" in zeile, f"erste Hauptaktion: {zeile}"
    f.enter("Antrag vorbereiten")
    assert page.evaluate("location.hash").startswith("#/leistung/pflegegeld")

    # 6. Formular-Download (Hauptaktion der Leistung „Antrag herunterladen“) erreichen
    f.tab_zu(r'link ".*(herunterladen|PDF)')
    href = page.evaluate("() => document.activeElement.getAttribute('href')")
    assert "/formular/" in href and "leistung=pflegegeld" in href, href
    assert page.evaluate("() => document.activeElement.classList.contains('hauptaktion')")

    # 7. Zurück-Knopf des Browsers: wieder „Mein Plan“, Fokus auf h1
    page.go_back()
    page.wait_for_timeout(400)
    assert page.evaluate("location.hash") == "#/plan"
    _h1_fokussiert(page, "Mein Plan")

    # 8. „Meine Akte“ über die Navigation, Angabe „Bundesland“ ändern
    f.tab_zu(r'link "Meine Akte')
    f.enter("Meine Akte")
    assert page.evaluate("location.hash") == "#/akte"
    _h1_fokussiert(page, "Meine Akte")
    f.tab_zu(r'button "Ändern Bundesland"')
    f.enter("Ändern Bundesland")
    feld = page.evaluate("() => [document.activeElement.tagName, document.activeElement.value || '']")
    if feld[0] != "SELECT":
        f.tab_zu(r"combobox")
    page.keyboard.type("Nieder")
    if page.evaluate("() => document.activeElement.value") != "Niederösterreich":
        page.keyboard.press("Home")
        for _ in range(9):
            if page.evaluate("() => document.activeElement.value") == "Niederösterreich":
                break
            page.keyboard.press("ArrowDown")
    assert page.evaluate("() => document.activeElement.value") == "Niederösterreich"
    f.tab_zu(r'button "Speichern')
    f.enter("Speichern", api=True)
    assert "Niederösterreich" in page.get_by_role("main").inner_text()

    # 9. Einstellungen: Fokusfalle, Textgröße A++, Farbschema Dunkel, Esc gibt Fokus zurück
    f.tab_zu(r'button "Einstellungen"')
    f.enter("Einstellungen öffnen")
    dialog = page.get_by_role("dialog", name="Einstellungen")
    assert dialog.is_visible()
    for _ in range(40):
        page.keyboard.press("Tab")
        assert page.evaluate("() => Boolean(document.activeElement.closest('dialog, [role=dialog]'))"), \
            "Fokus verlässt den offenen Dialog"
    groesse_vorher = page.evaluate("() => parseFloat(getComputedStyle(document.body).fontSize)")
    f.tab_zu(r'radio "A( Normal)?"')
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(200)
    assert re.search(r'radio "A\+\+', fokus_aria(page)) and "[checked]" in fokus_aria(page)
    groesse = page.evaluate("() => parseFloat(getComputedStyle(document.body).fontSize)")
    assert groesse >= groesse_vorher * 1.25, (groesse_vorher, groesse)
    f.tab_zu(r'radio "Wie System"')
    for _ in range(3):
        if re.search(r'radio "Dunkel"', fokus_aria(page)):
            break
        page.keyboard.press("ArrowDown")
    assert re.search(r'radio "Dunkel".*\[checked\]', fokus_aria(page)), fokus_aria(page)
    hintergrund = page.evaluate("""() => { const c = getComputedStyle(document.body).backgroundColor.match(/[\\d.]+/g).map(Number);
                                          return (c[0] + c[1] + c[2]) / 3; }""")
    assert hintergrund < 80, f"Farbschema Dunkel nicht angewendet (Hintergrund {hintergrund})"
    page.keyboard.press("Escape")
    dialog.wait_for(state="hidden")
    assert re.search(r'button "Einstellungen"', fokus_aria(page)), f"Fokus nach Esc: {fokus_aria(page)}"

    # 10. Zurück zu „Mein Plan“; „Plan drucken“ erreichbar und löst den Druck aus
    f.tab_zu(r'link "Mein Plan')
    f.enter("Mein Plan")
    page.evaluate("() => { window.__gedruckt = 0; window.print = () => { window.__gedruckt += 1; }; }")
    f.tab_zu(r'button "Plan drucken"')
    f.enter("Plan drucken")
    assert page.evaluate("window.__gedruckt") == 1
    f.bilanz()


def test_fokus_auf_h1_titel_und_zurueck(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    titel_start = page.title()
    page.get_by_role("textbox", name="Ihre Nachricht").fill(PFLEGE_SATZ)
    with page.expect_response(ist_api_post):
        page.get_by_role("button", name="Senden", exact=True).click()
    ruhe(page)
    nav = page.get_by_role("navigation", name="Hauptnavigation")
    sichtbar(nav.get_by_role("link", name="Mein Plan")).click()
    page.wait_for_timeout(300)
    _h1_fokussiert(page, "Mein Plan")
    assert page.title() != titel_start and "Mein Plan" in page.title()
    page.evaluate("location.hash = '#/leistung/pflegegeld'")
    page.wait_for_timeout(400)
    ruhe(page)
    _h1_fokussiert(page, "Pflegegeld")
    assert "Pflegegeld" in page.title()
    page.go_back()
    page.wait_for_timeout(400)
    _h1_fokussiert(page, "Mein Plan")
    page.go_back()
    page.wait_for_timeout(400)
    _h1_fokussiert(page, "Gespräch")
    assert page.evaluate("location.hash") in ("", "#/gespraech")
    page.go_forward()
    page.wait_for_timeout(400)
    _h1_fokussiert(page, "Mein Plan")


def test_einstellungen_esc_und_fokus_zurueck_bei_mausbedienung(neue_seite, lotse_url):
    page = neue_seite("mobil_390")
    laden(page, lotse_url)
    knopf = sichtbar(page.get_by_role("banner").get_by_role("button", name="Einstellungen"))
    knopf.click()
    dialog = page.get_by_role("dialog", name="Einstellungen")
    dialog.wait_for()
    assert page.evaluate("() => Boolean(document.activeElement.closest('dialog, [role=dialog]'))")
    page.keyboard.press("Escape")
    dialog.wait_for(state="hidden")
    assert page.evaluate("() => document.activeElement.textContent.includes('Einstellungen')")
    # Schließen-Knopf im Dialog (falls vorhanden) gibt den Fokus ebenfalls zurück
    knopf.click()
    dialog.wait_for()
    schliessen = dialog.get_by_role("button", name=re.compile("Schließen|Fertig"))
    if schliessen.count():
        schliessen.first.click()
        dialog.wait_for(state="hidden")
        assert page.evaluate("() => document.activeElement.textContent.includes('Einstellungen')")
