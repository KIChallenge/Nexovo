"""WCAG 2.2 AA im Browser: axe-core, Zielgröße, Schriftgröße, Reflow, Darstellungsmodi, Semantik.

Ein Durchlauf je (Viewport, Modus) stellt alle Zustände nacheinander in einer Sitzung her
(Start → Pflegefall → Mein Plan → Leistung Pflegegeld → Termin → Dokumente → Einstellungen) und
misst dort einmal; die Tests unten werten die zwischengespeicherten Messwerte aus.
"""

from __future__ import annotations

import re

import pytest

from messung import (
    BRIEF_DATEI,
    DEMO_BRIEF,
    DEMO_IMPFPASS,
    IMPFPASS_DATEI,
    TEXTGROESSE,
    VIEWPORTS,
    ansicht,
    axe_pruefen,
    demo_oder_hochladen,
    einstellung,
    einstellungen_oeffnen,
    hilfen,
    laden,
    nachricht,
    pflegefall,
    route,
    rueckfragen_beantworten,
    ruhe,
    sichtbar,
    termin,
)

pytestmark = pytest.mark.ui

MODI = {
    "standard": {},
    "dunkel": {"kontext": {"color_scheme": "dark"}},  # Farbschema „Wie System“ + System dunkel
    "kontrast": {"einstellungen": [("Farbschema", "Hoher Kontrast")]},
    "a++": {"einstellungen": [("Textgröße", TEXTGROESSE["A++"])]},
    "leicht": {"einstellungen": [("Darstellung", "Leichte Sprache")]},
}
ZUSTAENDE = ["Start", "Gespräch nach Pflegefall", "Mein Plan", "Mein Plan (aufgeklappt)", "Leistung Pflegegeld",
             "Leistung Pflegegeld (aufgeklappt)", "Meine Akte", "Mein Plan mit Termin", "Termin", "Termin (aufgeklappt)",
             "Akte mit Dokumenten", "Akte mit Dokumenten (aufgeklappt)", "Einstellungen"]

# Zielgröße 44×44 px (Designziel) – ausdrücklich erlaubte Ausnahmen
AUSNAHMEN_44 = [
    ("Checkbox/Radio: Kästchen ≥ 24 px, die klickbare Label-Zeile ist ≥ 44 px hoch",
     lambda z: z["typ"] in ("checkbox", "radio") and min(z["b"], z["h"]) >= 24 and z.get("label_h", 0) >= 44),
    ("Quell-URL als Textlink in einer Beleg-Liste (Textlink wie im Fließtext; WCAG 2.5.8 per Abstand erfüllt)",
     lambda z: z["tag"] == "a" and re.match(r"^(https?://|www\.)", z["name"]) is not None),
]

JS_ERREICHBAR = """(el) => {
  el.scrollIntoView({ block: "center", inline: "nearest" });
  const r = el.getBoundingClientRect();
  if (r.width < 1 || r.height < 1) return "nicht sichtbar";
  if (r.left < -1 || r.right > document.documentElement.clientWidth + 1) return `horizontal außerhalb (${Math.round(r.left)}–${Math.round(r.right)} px)`;
  const x = Math.min(Math.max(r.left + r.width / 2, 0), innerWidth - 1);
  const y = Math.min(Math.max(r.top + r.height / 2, 0), innerHeight - 1);
  const oben = document.elementFromPoint(x, y);
  if (!oben || !(el === oben || el.contains(oben) || oben.contains(el) || (el.labels && [...el.labels].some((l) => l.contains(oben)))))
    return `verdeckt durch <${oben ? oben.tagName.toLowerCase() + (oben.className ? "." + String(oben.className).split(" ")[0] : "") : "nichts"}>`;
  return null;
}"""

JS_HINTERGRUND_LUMINANZ = """() => {
  const lum = (c) => {
    const m = c.match(/[\\d.]+/g).map(Number);
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(m[0]) + 0.7152 * f(m[1]) + 0.0722 * f(m[2]);
  };
  for (const el of [document.querySelector("main"), document.body, document.documentElement]) {
    const c = getComputedStyle(el).backgroundColor;
    if (c && !/rgba\\(0, 0, 0, 0\\)|transparent/.test(c)) return lum(c);
  }
  return 1;
}"""


def _primaeraktionen(page, zustand: str) -> dict:
    banner = page.get_by_role("banner")
    nav = page.get_by_role("navigation", name="Hauptnavigation")
    navigation = {f"Navigation „{n}“": nav.get_by_role("link", name=n) for n in ("Gespräch", "Mein Plan", "Meine Akte")}
    hauptaktion = {"Hauptaktion (.hauptaktion)": page.locator(".hauptaktion")}
    kandidaten = {
        "Start": {
            "Textfeld „Ihre Nachricht“": page.get_by_role("textbox", name="Ihre Nachricht"),
            "„Senden“": page.get_by_role("button", name="Senden", exact=True),
            "„Einstellungen“": banner.get_by_role("button", name="Einstellungen"),
            **navigation,
        },
        "Gespräch nach Pflegefall": {"Link „Zu meinem Plan“": page.get_by_role("link", name="Zu meinem Plan"),
                                     **hauptaktion},
        "Mein Plan": {"„Plan drucken“": page.get_by_role("button", name="Plan drucken"), **hauptaktion, **navigation},
        "Meine Akte": {
            "„Fall speichern“": page.get_by_role("link", name="Fall speichern"),
            "„Neuen Fall beginnen“": page.get_by_role("button", name="Neuen Fall beginnen"),
            "„Dokument hinzufügen“": page.locator("label").filter(has_text="Dokument hinzufügen"),
            **navigation,
        },
        "Leistung Pflegegeld": {"„Zurück zu Mein Plan“": page.get_by_role("link", name="Zurück zu Mein Plan"),
                                **hauptaktion},
        "Termin": {"„Zurück zu Mein Plan“": page.get_by_role("link", name="Zurück zu Mein Plan"), **hauptaktion},
    }.get(zustand, {})
    ergebnis = {}
    for name, loc in kandidaten.items():
        loc = sichtbar(loc)
        if not loc.count():
            ergebnis[name] = "nicht vorhanden/sichtbar"
            continue
        ergebnis[name] = loc.evaluate(JS_ERREICHBAR)
    return ergebnis


def _messen(page, zustand: str, modus: str) -> dict:
    hilfen(page)
    erg = {
        "axe": axe_pruefen(page),
        "ziele": page.evaluate("() => window.__messung.ziele(null)"),
        "texte": page.evaluate("() => window.__messung.texte(null)"),
        "layout": page.evaluate("() => window.__messung.ueberlauf()"),
    }
    if modus == "kontrast":
        from axe_playwright_python.sync_playwright import Axe

        r = Axe().run(page, options={"runOnly": {"type": "rule", "values": ["color-contrast-enhanced"]}}).response
        erg["kontrast_7"] = [{"knoten": len(v["nodes"]), "ziele": [n["target"] for n in v["nodes"][:8]]}
                             for v in r["violations"]]
    if modus == "dunkel":
        erg["luminanz"] = page.evaluate(JS_HINTERGRUND_LUMINANZ)
    erg["erreichbar"] = _primaeraktionen(page, zustand)
    # technische Platzhalter dürfen nie als sichtbarer Text erscheinen
    erg["platzhalter"] = page.evaluate(r"""() => {
      const aus = [];
      const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (tw.nextNode()) {
        const t = tw.currentNode, p = t.parentElement;
        if (!p || /^(SCRIPT|STYLE)$/.test(p.tagName) || !window.__messung.textSichtbar(p)) continue;
        const m = t.data.match(/\b(null|undefined|NaN)\b|\[object Object\]|\{\w+\}/);
        if (m) aus.push(`${m[0]} in <${p.tagName.toLowerCase()}>: ${window.__messung.textKurz(p.textContent, 50)}`);
      }
      return aus;
    }""")
    return erg


def _aufklappen_und_messen(page, werte: dict, zustand: str, modus: str) -> None:
    """Misst die Ansicht wie angezeigt und noch einmal mit allen <details> im Hauptbereich geöffnet."""
    werte[zustand] = _messen(page, zustand, modus)
    page.evaluate("() => document.querySelectorAll('main details').forEach((d) => { d.open = true; })")
    page.wait_for_timeout(100)
    werte[f"{zustand} (aufgeklappt)"] = _messen(page, f"{zustand} (aufgeklappt)", modus)


def _durchlaufen(browser, url: str, viewport: str, modus: str) -> dict:
    cfg = MODI[modus]
    ctx = browser.new_context(viewport=VIEWPORTS[viewport], locale="de-AT", **cfg.get("kontext", {}))
    page = ctx.new_page()
    page.set_default_timeout(20000)
    werte: dict[str, dict] = {}
    try:
        laden(page, url)
        for gruppe, option in cfg.get("einstellungen", []):
            einstellung(page, gruppe, option)
        werte["Start"] = _messen(page, "Start", modus)
        pflegefall(page)
        werte["Gespräch nach Pflegefall"] = _messen(page, "Gespräch nach Pflegefall", modus)
        ansicht(page, "Mein Plan")
        _aufklappen_und_messen(page, werte, "Mein Plan", modus)
        route(page, "#/leistung/pflegegeld")
        _aufklappen_und_messen(page, werte, "Leistung Pflegegeld", modus)
        ansicht(page, "Meine Akte")
        werte["Meine Akte"] = _messen(page, "Meine Akte", modus)
        ansicht(page, "Gespräch")
        a = termin(page)
        ansicht(page, "Mein Plan")
        werte["Mein Plan mit Termin"] = _messen(page, "Mein Plan", modus)
        route(page, f"#/termin/{a['termine'][0]['id']}")
        _aufklappen_und_messen(page, werte, "Termin", modus)
        ansicht(page, "Gespräch")
        demo_oder_hochladen(page, DEMO_BRIEF, BRIEF_DATEI)
        demo_oder_hochladen(page, DEMO_IMPFPASS, IMPFPASS_DATEI)
        ansicht(page, "Meine Akte")
        _aufklappen_und_messen(page, werte, "Akte mit Dokumenten", modus)
        einstellungen_oeffnen(page)
        werte["Einstellungen"] = _messen(page, "Einstellungen", modus)
    finally:
        ctx.close()
    return werte


@pytest.fixture(scope="session")
def durchlauf(browser, lotse_url):
    cache: dict = {}

    def holen(viewport: str, modus: str = "standard") -> dict:
        key = (viewport, modus)
        if key not in cache:
            try:
                cache[key] = _durchlaufen(browser, lotse_url, viewport, modus)
            except Exception as err:  # noqa: BLE001 – Fehler des Durchlaufs in jedem Test zeigen
                cache[key] = err
        if isinstance(cache[key], Exception):
            raise AssertionError(f"Durchlauf {viewport}/{modus} gescheitert: {cache[key]}") from cache[key]
        return cache[key]

    return holen


def _bericht(probleme: list[str]) -> str:
    return "\n".join(probleme[:60]) + (f"\n… und {len(probleme) - 60} weitere" if len(probleme) > 60 else "")


# ---------------------------------------------------------------------------
# axe-core
# ---------------------------------------------------------------------------

AXE_FAELLE = [(v, "standard") for v in VIEWPORTS] + [
    (v, m) for m in ("dunkel", "kontrast", "a++", "leicht") for v in ("desktop", "schmal_320")]


@pytest.mark.parametrize(("viewport", "modus"), AXE_FAELLE, ids=[f"{v}-{m}" for v, m in AXE_FAELLE])
def test_axe_wcag22_aa_ohne_verstoesse(durchlauf, viewport, modus):
    werte = durchlauf(viewport, modus)
    probleme = [f"{z}: {v['regel']} ({v['impact']}, {v['knoten']}×) {v['ziele']}"
                for z, m in werte.items() for v in m["axe"]["verstoesse"]]
    assert set(werte) == set(ZUSTAENDE)
    assert not probleme, _bericht(probleme)


@pytest.mark.parametrize("viewport", ["desktop", "schmal_320"])
def test_hoher_kontrast_mindestens_7_zu_1(durchlauf, viewport):
    werte = durchlauf(viewport, "kontrast")
    probleme = [f"{z}: color-contrast-enhanced {v}" for z, m in werte.items() for v in m["kontrast_7"]]
    assert not probleme, _bericht(probleme)


@pytest.mark.parametrize("viewport", ["desktop", "schmal_320"])
def test_dunkles_farbschema_folgt_dem_system(durchlauf, viewport):
    werte = durchlauf(viewport, "dunkel")
    hell = {z: round(m["luminanz"], 3) for z, m in werte.items() if m["luminanz"] > 0.2}
    assert not hell, f"Hintergrund trotz prefers-color-scheme: dark hell: {hell}"


# ---------------------------------------------------------------------------
# Zielgröße, Schriftgröße, Reflow
# ---------------------------------------------------------------------------

GROESSEN_FAELLE = [(v, "standard") for v in VIEWPORTS] + [("schmal_320", "a++"), ("desktop", "leicht")]


@pytest.mark.parametrize(("viewport", "modus"), GROESSEN_FAELLE, ids=[f"{v}-{m}" for v, m in GROESSEN_FAELLE])
def test_zielgroesse_mindestens_24px(durchlauf, viewport, modus):
    """WCAG 2.5.8 (AA): Ziele ≥ 24×24 px; Ausnahmen laut WCAG: Links im Fließtext und ausreichender Abstand."""
    werte = durchlauf(viewport, modus)
    probleme = [f"{zst}: <{z['tag']}> „{z['name']}“ {z['b']}×{z['h']} px"
                for zst, m in werte.items() for z in m["ziele"]["liste_unter_24px"] if not z.get("abstand_ok")]
    assert not probleme, _bericht(probleme)


@pytest.mark.parametrize(("viewport", "modus"), GROESSEN_FAELLE, ids=[f"{v}-{m}" for v, m in GROESSEN_FAELLE])
def test_zielgroesse_designziel_44px(durchlauf, viewport, modus):
    """Designziel des Projekts: Bedienelemente ≥ 44×44 px, Ausnahmen nur laut AUSNAHMEN_44."""
    werte = durchlauf(viewport, modus)
    probleme = []
    for zst, m in werte.items():
        for z in m["ziele"]["liste_unter_44px"]:
            if not any(pruef(z) for _, pruef in AUSNAHMEN_44):
                probleme.append(f"{zst}: <{z['tag']} {z['typ']}> „{z['name']}“ {z['b']}×{z['h']} px")
    assert not probleme, _bericht(probleme)


@pytest.mark.parametrize(("viewport", "modus"), GROESSEN_FAELLE, ids=[f"{v}-{m}" for v, m in GROESSEN_FAELLE])
def test_kein_sichtbarer_text_unter_16px(durchlauf, viewport, modus):
    werte = durchlauf(viewport, modus)
    probleme = [f"{zst}: {b['px']} px <{b['tag']} class={b['klasse']!r}> „{b['text']}“"
                for zst, m in werte.items() for b in m["texte"]["beispiele_unter_16px"]]
    gesamt = sum(m["texte"]["unter_16px"] for m in werte.values())
    assert not gesamt, f"{gesamt} Textelemente < 16 px:\n" + _bericht(probleme)


REFLOW_FAELLE = [("schmal_320", "standard"), ("zoom_400", "standard"), ("schmal_320", "a++"), ("schmal_320", "leicht")]


@pytest.mark.parametrize(("viewport", "modus"), REFLOW_FAELLE, ids=[f"{v}-{m}" for v, m in REFLOW_FAELLE])
def test_reflow_ohne_horizontales_scrollen(durchlauf, viewport, modus):
    """WCAG 1.4.10: bei 320 CSS-px Breite (bzw. 400 % Zoom) kein horizontales Scrollen."""
    werte = durchlauf(viewport, modus)
    probleme = [f"{z}: {m['layout']['horizontal_px']} px Überlauf, {m['layout']['beispiele'][:3]}"
                for z, m in werte.items() if m["layout"]["horizontal_px"] > 0 or m["layout"]["elemente_rechts_ausserhalb"]]
    assert not probleme, _bericht(probleme)


@pytest.mark.parametrize(("viewport", "modus"), REFLOW_FAELLE + [("desktop", "standard"), ("mobil_390", "standard")],
                         ids=[f"{v}-{m}" for v, m in REFLOW_FAELLE + [("desktop", "standard"), ("mobil_390", "standard")]])
def test_primaeraktionen_erreichbar_und_nicht_verdeckt(durchlauf, viewport, modus):
    """Hauptaktionen sind sichtbar, liegen in der Breite und werden nicht von fixen Leisten verdeckt."""
    werte = durchlauf(viewport, modus)
    probleme = [f"{z}: {name}: {fehler}" for z, m in werte.items() for name, fehler in m["erreichbar"].items() if fehler]
    assert not probleme, _bericht(probleme)


@pytest.mark.parametrize("viewport", ["desktop", "schmal_320"])
def test_keine_technischen_platzhalter_im_text(durchlauf, viewport):
    """Kein sichtbares „null“, „undefined“, „NaN“, „[object Object]“ oder unersetzter „{platzhalter}“."""
    werte = durchlauf(viewport, "standard")
    probleme = [f"{z}: {p}" for z, m in werte.items() for p in m["platzhalter"]]
    assert not probleme, _bericht(probleme)


# ---------------------------------------------------------------------------
# Darstellungsmodi
# ---------------------------------------------------------------------------


def test_forced_colors_raender_und_fokus_bleiben(neue_seite, lotse_url):
    page = neue_seite("desktop", forced_colors="active")
    laden(page, lotse_url)
    pflegefall(page)
    assert page.evaluate("matchMedia('(forced-colors: active)').matches")
    hilfen(page)
    ohne_rand = page.evaluate("""() => {
      const aus = [];
      const sel = 'button, [role=button], [role=switch], [role=radio], input, select, textarea, nav a, a.knopf, a[class*=knopf], a[class*=button]';
      for (const el of document.querySelectorAll(sel)) {
        if (!window.__messung.gerendert(el) || window.__messung.visuellVersteckt(el)) continue;
        const cs = getComputedStyle(el);
        const rand = ['Top', 'Right', 'Bottom', 'Left'].some((s) => cs['border' + s + 'Style'] !== 'none' && parseFloat(cs['border' + s + 'Width']) >= 1);
        if (!rand && cs.outlineStyle === 'none') aus.push(`<${el.tagName.toLowerCase()}> ${window.__messung.name(el)}`);
      }
      return aus;
    }""")
    assert not ohne_rand, f"Bedienelemente ohne Rahmen im forced-colors-Modus: {ohne_rand[:20]}"
    # Fokus muss als outline sichtbar sein (box-shadow wird im forced-colors-Modus entfernt)
    page.evaluate("() => { const b = document.body; b.setAttribute('tabindex', '-1'); b.focus(); b.removeAttribute('tabindex'); }")
    for _ in range(12):
        page.keyboard.press("Tab")
        info = page.evaluate("() => window.__messung.fokusInfo(null)")
        if info is None:
            break  # Dokumentende
        assert info["fokus_px"] >= 2, f"Fokus im forced-colors-Modus nicht sichtbar: {info}"


def test_reduzierte_bewegung(neue_seite, lotse_url):
    page = neue_seite("desktop", reduced_motion="reduce")
    laden(page, lotse_url)
    pflegefall(page)
    ansicht(page, "Mein Plan")
    bewegt = page.evaluate("""() => {
      const aus = [];
      const dauer = (s) => Math.max(...s.split(',').map((x) => parseFloat(x) * (x.trim().endsWith('ms') ? 0.001 : 1)));
      for (const el of document.querySelectorAll('*')) {
        const cs = getComputedStyle(el);
        if (cs.animationName !== 'none' && dauer(cs.animationDuration) > 0.01) aus.push('animation ' + el.tagName + '.' + el.className);
        if (dauer(cs.transitionDuration) > 0.01) aus.push('transition ' + el.tagName + '.' + el.className);
      }
      if (getComputedStyle(document.documentElement).scrollBehavior === 'smooth') aus.push('scroll-behavior: smooth');
      return aus;
    }""")
    assert not bewegt, f"Bewegung trotz prefers-reduced-motion: {bewegt[:15]}"


def test_rtl_arabisch_mit_gerenderter_vorlage(neue_seite, lotse_url):
    """Arabisch gibt es nur im KI-Modus; hier liefert eine Vorlage (abgefangene API-Antworten) die Richtung rtl."""
    import json
    import urllib.request

    page = neue_seite("mobil_390")
    de = json.load(urllib.request.urlopen(lotse_url + "api/texte?sprache=de"))
    mit_ki = dict(de, ki=True, sprachen=[dict(s, verfuegbar=True) for s in de["sprachen"]])
    ar_texte = dict(mit_ki, sprache="ar")

    def texte(route_, request):
        sprache = re.search(r"sprache=(\w+)", request.url)
        route_.fulfill(json=ar_texte if sprache and sprache.group(1) == "ar" else mit_ki)

    def einstellungen(route_, request):
        body = request.post_data_json or {}
        if body.get("sprache") != "ar":
            route_.continue_()
            return
        sid = re.search(r"/api/sitzung/(\w+)/", request.url).group(1)
        stand = json.load(urllib.request.urlopen(f"{lotse_url}api/sitzung/{sid}"))
        route_.fulfill(json=dict(stand, sprache="ar", richtung="rtl"))

    page.route(re.compile(r".*/api/texte\?.*"), texte)
    page.route(re.compile(r".*/api/sitzung/\w+/einstellungen$"), einstellungen)
    laden(page, lotse_url)
    pflegefall(page)
    dialog = einstellungen_oeffnen(page)
    arabisch = dialog.get_by_role("radiogroup", name="Sprache").get_by_role("radio", name="العربية")
    if not arabisch.count() or arabisch.is_disabled():
        pytest.skip("Arabisch ist im Einstellungsdialog ohne KI-Modus nicht wählbar – RTL nur mit KI prüfbar")
    arabisch.check()
    page.wait_for_timeout(300)
    ruhe(page)
    page.keyboard.press("Escape")
    richtung = page.evaluate("() => [document.documentElement.dir, getComputedStyle(document.querySelector('main')).direction]")
    assert "rtl" in richtung, richtung
    hilfen(page)
    assert page.evaluate("() => window.__messung.ueberlauf().horizontal_px") == 0
    probleme = [v["regel"] for v in axe_pruefen(page)["verstoesse"]]
    assert not probleme, probleme


# ---------------------------------------------------------------------------
# Semantik im Accessibility-Tree
# ---------------------------------------------------------------------------

UNBENANNT = re.compile(r"^\s*- (button|link|textbox|checkbox|radio|switch|combobox|tab|slider|spinbutton|menuitem)"
                       r"(\s*\[[^\]]*\])*:?\s*$", re.M)


def _ohne_namen(page) -> list[str]:
    return [m.group(0).strip() for m in UNBENANNT.finditer(page.locator("body").aria_snapshot())]


def _ueberschriften(page, ebene: int) -> list[str]:
    return [h.inner_text().strip() for h in page.get_by_role("heading", level=ebene).all() if h.is_visible()]


def test_landmarken_ueberschriften_und_namen(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    baum = page.locator("body").aria_snapshot()
    assert "- banner" in baum and '- navigation "Hauptnavigation"' in baum and "- main" in baum, baum[:800]
    assert page.get_by_role("banner").get_by_role("heading", level=1).count() == 0, "App-Name im Kopf darf kein h1 sein"
    assert _ueberschriften(page, 1) == ["Gespräch"]
    assert not _ohne_namen(page)

    pflegefall(page)
    assert page.get_by_role("log").count() == 1
    assert "Ihr nächster Schritt" in _ueberschriften(page, 2) + _ueberschriften(page, 3)
    assert not _ohne_namen(page), _ohne_namen(page)

    ansicht(page, "Mein Plan")
    assert _ueberschriften(page, 1) == ["Mein Plan"]
    assert not _ohne_namen(page), _ohne_namen(page)

    ansicht(page, "Meine Akte")
    assert _ueberschriften(page, 1) == ["Meine Akte"]
    h = _ueberschriften(page, 2) + _ueberschriften(page, 3)
    assert {"Ihre Angaben", "Für Formulare fehlen noch", "Ihre Dokumente"} <= set(h), h
    assert not _ohne_namen(page), _ohne_namen(page)

    route(page, "#/leistung/pflegegeld")
    h1 = _ueberschriften(page, 1)
    assert len(h1) == 1 and "Pflegegeld" in h1[0], h1
    assert {"Zuständige Stelle", "Unterlagen"} <= set(_ueberschriften(page, 2)), _ueberschriften(page, 2)
    page.locator("summary").filter(has_text="Mehr zu dieser Leistung").click()
    h3 = _ueberschriften(page, 3)
    reihenfolge = ["Warum das hilft", "In Ihrem Bundesland", "So gehen Sie vor", "Formular", "Wo Sie Angebote finden"]
    vorhanden = [r for r in reihenfolge if r in h3]
    assert {"Warum das hilft", "So gehen Sie vor", "Formular"} <= set(vorhanden), h3
    assert [x for x in h3 if x in reihenfolge] == vorhanden, f"Reihenfolge der Abschnitte: {h3}"
    assert not _ohne_namen(page), _ohne_namen(page)


def test_navigation_aria_current(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    nav = page.get_by_role("navigation", name="Hauptnavigation")
    links = {n: sichtbar(nav.get_by_role("link", name=n)) for n in ("Gespräch", "Mein Plan", "Meine Akte")}
    assert links["Gespräch"].get_attribute("aria-current") == "page"
    assert links["Mein Plan"].get_attribute("aria-current") is None
    pflegefall(page)
    for ziel in ("Mein Plan", "Meine Akte"):
        ansicht(page, ziel)
        assert [n for n, lk in links.items() if lk.get_attribute("aria-current") == "page"] == [ziel]
    # Unteransicht Leistung: die Navigation zeigt „Mein Plan“ als aktuell
    route(page, "#/leistung/pflegegeld")
    assert [n for n, lk in links.items() if lk.get_attribute("aria-current")] == ["Mein Plan"]


def test_chat_log_und_live_region_mit_ansage(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    a = pflegefall(page)
    log = page.get_by_role("log")
    assert log.count() == 1
    assert a and a.get("ansage"), "Antwort ohne `ansage` (Backend-Vertrag)"
    region = page.locator('[aria-live="polite"], [role="status"]').filter(has_text=a["ansage"])
    assert region.count() >= 1, f"Live-Region enthält die Ansage nicht: {a['ansage']!r}"
    assert log.get_by_role("listitem").count() >= 2
    for ziel in ("Mein Plan", "Meine Akte"):
        ansicht(page, ziel)
        page.wait_for_timeout(300)
        assert page.locator('[aria-live="polite"], [role="status"]').filter(has_text=ziel).count() >= 1, \
            f"Routenwechsel zu „{ziel}“ wird nicht angesagt"


def test_einstellungen_dialog_semantik(neue_seite, lotse_url):
    page = neue_seite("desktop")
    laden(page, lotse_url)
    dialog = einstellungen_oeffnen(page)
    assert dialog.is_visible()
    for gruppe, mindestens in [("Sprache", 2), ("Darstellung", 3), ("Textgröße", 3), ("Farbschema", 4), ("Vorlesetempo", 3)]:
        g = dialog.get_by_role("radiogroup", name=gruppe)
        assert g.count() == 1, f"Radiogruppe „{gruppe}“ fehlt"
        radios = g.get_by_role("radio")
        assert radios.count() >= mindestens, gruppe
        assert sum(1 for r in radios.all() if r.is_checked()) == 1, f"„{gruppe}“: genau eine Option gewählt"
    darst = dialog.get_by_role("radiogroup", name="Darstellung")
    for name in ("Einfach", "Ausführlich", "Leichte Sprache"):
        assert darst.get_by_role("radio", name=name, exact=True).count() == 1, name
    farben = dialog.get_by_role("radiogroup", name="Farbschema")
    for name in ("Wie System", "Hell", "Dunkel", "Hoher Kontrast"):
        assert farben.get_by_role("radio", name=name, exact=True).count() == 1, name
    sprache = dialog.get_by_role("radiogroup", name="Sprache")
    assert sprache.get_by_role("radio", name="Deutsch").is_checked()
    assert sprache.get_by_role("radio", name="English").is_enabled()
    weitere = [r for r in sprache.get_by_role("radio").all() if r.is_disabled()]
    assert weitere, "weitere Sprachen ohne KI nicht als deaktiviert erkennbar"
    assert "KI" in dialog.inner_text(), "Hinweis „nur im KI-Modus“ fehlt"
    # Modus-Anzeige und voller Grenztext mit Quelle stehen im Dialog
    import json
    import urllib.request

    t = json.load(urllib.request.urlopen(lotse_url + "api/texte"))["texte"]
    inhalt = re.sub(r"\s+", " ", dialog.inner_text())
    assert "regelbasiert" in inhalt, "Modus fehlt im Einstellungen-Dialog"
    assert re.sub(r"\s+", " ", t["grenze_hinweis"]).strip() in inhalt, "voller Grenztext fehlt im Dialog"
    assert t["quelle_1450"]["titel"] in inhalt and t["quelle_1450"]["fundstelle"] in inhalt
    schalter = dialog.get_by_role("switch", name="Belege anzeigen")
    assert schalter.count() == 1 and schalter.get_attribute("aria-checked") == "false"
    schalter.click()
    assert schalter.get_attribute("aria-checked") == "true"
    assert "[checked]" in schalter.aria_snapshot()
    # 3.1.2 Sprache von Teilen: Sprachnamen tragen ihr eigenes lang-Attribut
    ohne_lang = sprache.get_by_role("radio").evaluate_all("""(radios) => radios.filter((r) => {
        const lab = r.labels && r.labels[0];
        const kandidaten = [r, lab, lab && lab.querySelector('[lang]')].filter(Boolean);
        const lang = kandidaten.map((k) => (k.closest('[lang]') || {}).lang || k.lang).find((l) => l && l !== document.documentElement.lang);
        return !lang && !(lab && /Deutsch/.test(lab.textContent));
    }).map((r) => r.labels && r.labels[0] ? r.labels[0].textContent.trim() : r.value)""")
    assert not ohne_lang, f"Sprachnamen ohne lang-Attribut: {ohne_lang}"


# ---------------------------------------------------------------------------
# Weitere Kriterien von WCAG 2.2 AA, die axe nicht abdeckt
# ---------------------------------------------------------------------------


def _ansichten(page) -> list:
    """(Name, Hinweg): Gespräch → Mein Plan → Meine Akte → Leistung (alles aufgeklappt) → Einstellungen."""
    def leistung():
        route(page, "#/leistung/pflegegeld")
        page.evaluate("() => document.querySelectorAll('main details').forEach((d) => { d.open = true; })")

    return [("Gespräch", lambda: None), ("Mein Plan", lambda: ansicht(page, "Mein Plan")),
            ("Meine Akte", lambda: ansicht(page, "Meine Akte")), ("Leistung", leistung),
            ("Einstellungen", lambda: einstellungen_oeffnen(page))]


TEXTABSTAND_CSS = """
* { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; }
p { margin-bottom: 2em !important; }
"""

JS_ABGESCHNITTEN = """() => {
  const aus = [];
  for (const el of document.body.querySelectorAll('*')) {
    if (!window.__messung.gerendert(el) || window.__messung.visuellVersteckt(el)) continue;
    if (!(el.innerText || '').trim() || /^(TEXTAREA|SELECT|INPUT|svg)$/i.test(el.tagName)) continue;
    const cs = getComputedStyle(el);
    const yZu = cs.overflowY === 'hidden' || cs.overflowY === 'clip';
    const xZu = cs.overflowX === 'hidden' || cs.overflowX === 'clip';
    if ((yZu && el.scrollHeight > el.clientHeight + 2) || (xZu && el.scrollWidth > el.clientWidth + 2))
      aus.push(`<${el.tagName.toLowerCase()} class=${String(el.className).slice(0, 30)}> ${window.__messung.textKurz(el.innerText, 40)}`);
  }
  return aus;
}"""


@pytest.mark.parametrize("viewport", ["desktop", "schmal_320"])
def test_textabstaende_1_4_12_ohne_abschneiden(neue_seite, lotse_url, viewport):
    """WCAG 1.4.12: mit erhöhten Zeilen-, Absatz-, Buchstaben- und Wortabständen geht kein Inhalt verloren."""
    page = neue_seite(viewport, bypass_csp=True)
    laden(page, lotse_url)
    pflegefall(page)
    probleme = []
    for name, hinkommen in _ansichten(page):
        hinkommen()
        page.add_style_tag(content=TEXTABSTAND_CSS)
        page.wait_for_timeout(100)
        hilfen(page)
        probleme += [f"{name}: {p}" for p in page.evaluate(JS_ABGESCHNITTEN)]
        ueber = page.evaluate("() => window.__messung.ueberlauf()")
        if ueber["horizontal_px"]:
            probleme.append(f"{name}: {ueber['horizontal_px']} px horizontaler Überlauf {ueber['beispiele'][:2]}")
    assert not probleme, _bericht(probleme)


JS_FOKUS_VERDECKT = """() => {
  let el = document.activeElement;
  if (!el || el === document.body) return null;
  if (window.__messung.visuellVersteckt(el) && el.labels && el.labels[0]) el = el.labels[0];
  // nur der sichtbare Teil im Viewport zählt; dort 5 Punkte prüfen
  const a = el.getBoundingClientRect();
  const r = { left: Math.max(a.left, 0), top: Math.max(a.top, 0), right: Math.min(a.right, innerWidth), bottom: Math.min(a.bottom, innerHeight) };
  if (r.right <= r.left || r.bottom <= r.top) return window.__messung.name(document.activeElement) + " (außerhalb des Viewports)";
  const punkte = [[.5, .5], [.15, .15], [.85, .15], [.15, .85], [.85, .85]];
  let sichtbar = 0;
  for (const [fx, fy] of punkte) {
    const x = r.left + (r.right - r.left) * fx, y = r.top + (r.bottom - r.top) * fy;
    const o = document.elementFromPoint(x, y);
    if (o && (o === el || el.contains(o) || o.contains(el) || (document.activeElement.labels && [...document.activeElement.labels].some((l) => l.contains(o))))) sichtbar++;
  }
  return sichtbar ? null : window.__messung.name(document.activeElement) || document.activeElement.tagName;
}"""


@pytest.mark.parametrize("viewport", ["mobil_390", "zoom_400"])
def test_fokus_nicht_verdeckt_2_4_11(neue_seite, lotse_url, viewport):
    """WCAG 2.4.11: kein per Tab erreichtes Element liegt vollständig unter Kopf- oder Tab-Leiste."""
    page = neue_seite(viewport)
    laden(page, lotse_url)
    pflegefall(page)
    verdeckt = []
    for ansicht_name in ("Gespräch", "Mein Plan", "Meine Akte"):
        ansicht(page, ansicht_name)
        hilfen(page)
        page.evaluate("() => { const b = document.body; b.setAttribute('tabindex', '-1'); b.focus(); b.removeAttribute('tabindex'); }")
        gesehen = set()
        for _ in range(400):
            page.keyboard.press("Tab")
            info = page.evaluate("() => window.__messung.fokusInfo(null)")
            if info is None or info["id"] in gesehen:
                break
            gesehen.add(info["id"])
            treffer = page.evaluate(JS_FOKUS_VERDECKT)
            if treffer:
                verdeckt.append(f"{ansicht_name}: {treffer}")
    assert not verdeckt, _bericht(verdeckt)


JS_NICHT_TEXT_KONTRAST = """() => {
  const farbe = (c) => { const m = (c || '').match(/[\\d.]+/g); if (!m) return null; const [r, g, b, a = 1] = m.map(Number); return { r, g, b, a }; };
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const k = (x, y) => { const [h, d] = [lum(x), lum(y)].sort((p, q) => q - p); return (h + 0.05) / (d + 0.05); };
  const hinter = (el) => { for (let a = el.parentElement; a; a = a.parentElement) { const c = farbe(getComputedStyle(a).backgroundColor); if (c && c.a > 0.5) return c; } return { r: 255, g: 255, b: 255, a: 1 }; };
  const aus = [];
  const sel = 'button, input:not([type=checkbox]):not([type=radio]):not([type=file]):not([type=hidden]), select, textarea, [role=switch]';
  for (const el of document.querySelectorAll(sel)) {
    if (!window.__messung.gerendert(el) || window.__messung.visuellVersteckt(el)) continue;
    const cs = getComputedStyle(el);
    const hg = hinter(el);
    const eigen = farbe(cs.backgroundColor);
    let best = eigen && eigen.a > 0.5 ? k(eigen, hg) : 1;
    for (const s of ['Top', 'Right', 'Bottom', 'Left']) {
      if (cs['border' + s + 'Style'] === 'none' || parseFloat(cs['border' + s + 'Width']) < 1) continue;
      const rand = farbe(cs['border' + s + 'Color']);
      if (rand && rand.a > 0.5) best = Math.max(best, k(rand, hg));
    }
    const linkartig = el.tagName === 'BUTTON' && cs.textDecorationLine.includes('underline');
    // Schalter: die sichtbare Spur ist ein Kindelement mit eigenem Rand
    for (const kind of el.querySelectorAll('*')) {
      if (best >= 3) break;
      const kc = getComputedStyle(kind);
      const rand = farbe(kc.borderTopColor);
      if (kc.borderTopStyle !== 'none' && parseFloat(kc.borderTopWidth) >= 1 && rand && rand.a > 0.5) best = Math.max(best, k(rand, eigen && eigen.a > 0.5 ? eigen : hg));
    }
    if (best < 3 && !linkartig) aus.push(`<${el.tagName.toLowerCase()}> „${window.__messung.name(el)}“ ${best.toFixed(2)}:1`);
  }
  return aus;
}"""

JS_FOKUS_KONTRAST = """() => {
  const el = document.activeElement;
  const farbe = (c) => { const m = (c || '').match(/[\\d.]+/g); if (!m) return null; const [r, g, b, a = 1] = m.map(Number); return { r, g, b, a }; };
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const k = (x, y) => { const [h, d] = [lum(x), lum(y)].sort((p, q) => q - p); return (h + 0.05) / (d + 0.05); };
  let ziel = el;
  if (window.__messung.visuellVersteckt(el) && el.labels && el.labels[0]) ziel = el.labels[0];
  const cs = getComputedStyle(ziel);
  if (cs.outlineStyle === 'none') return null;
  let hg = { r: 255, g: 255, b: 255 };
  for (let a = ziel.parentElement; a; a = a.parentElement) { const c = farbe(getComputedStyle(a).backgroundColor); if (c && c.a > 0.5) { hg = c; break; } }
  const wert = k(farbe(cs.outlineColor), hg);
  return wert < 3 ? `${window.__messung.name(el)} ${wert.toFixed(2)}:1` : null;
}"""


@pytest.mark.parametrize("modus", ["standard", "dunkel", "kontrast"])
def test_nicht_text_kontrast_1_4_11(neue_seite, lotse_url, modus):
    """WCAG 1.4.11: Grenzen von Bedienelementen und die Fokusanzeige mit ≥ 3:1 gegen den Hintergrund."""
    page = neue_seite("desktop", **MODI[modus].get("kontext", {}))
    laden(page, lotse_url)
    for gruppe, option in MODI[modus].get("einstellungen", []):
        einstellung(page, gruppe, option)
    pflegefall(page)
    probleme = []
    for name, hinkommen in _ansichten(page):
        hinkommen()
        hilfen(page)
        probleme += [f"{name}: Grenze {p}" for p in page.evaluate(JS_NICHT_TEXT_KONTRAST)]
        for _ in range(60):
            page.keyboard.press("Tab")
            fehler = page.evaluate(JS_FOKUS_KONTRAST)
            if fehler:
                probleme.append(f"{name}: Fokusanzeige {fehler}")
    assert not probleme, _bericht(sorted(set(probleme)))


def test_name_enthaelt_sichtbare_beschriftung_2_5_3(neue_seite, lotse_url):
    from axe_playwright_python.sync_playwright import Axe

    page = neue_seite("desktop")
    laden(page, lotse_url)
    pflegefall(page)
    probleme = []
    for name, hinkommen in _ansichten(page):
        hinkommen()
        r = Axe().run(page, options={"runOnly": {"type": "rule", "values": ["label-content-name-mismatch"]}}).response
        probleme += [f"{name}: {n['target']}" for v in r["violations"] for n in v["nodes"]]
    assert not probleme, _bericht(probleme)


def test_eingabezweck_1_3_5_nur_fuer_eigene_daten(neue_seite, lotse_url):
    """Autocomplete nur, wenn die Angaben die Person am Gerät betreffen (nicht für Angehörige)."""
    page = neue_seite("desktop")
    laden(page, lotse_url)
    pflegefall(page)  # „Meine Mutter …“ → für eine Angehörige
    ansicht(page, "Meine Akte")
    page.get_by_role("button", name="Eintragen Vorname").click()
    assert page.get_by_role("textbox", name=re.compile("Vorname")).get_attribute("autocomplete") == "off"
    selbst = neue_seite("desktop")
    laden(selbst, lotse_url)
    a = rueckfragen_beantworten(selbst, nachricht(selbst, "Ich brauche Pflegegeld für mich selbst"))
    if not any(x["slot"] == "anliegen.fuer_wen" and x.get("wert_roh", "") == "selbst" for x in a["angaben"]):
        pytest.skip("Regelmodus hat „für mich selbst“ nicht als Angabe übernommen")
    ansicht(selbst, "Meine Akte")
    selbst.get_by_role("button", name="Eintragen Vorname").click()
    assert selbst.get_by_role("textbox", name=re.compile("Vorname")).get_attribute("autocomplete") == "given-name"
