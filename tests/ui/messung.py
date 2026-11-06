"""Messung von Bedienbarkeit und Barrierefreiheit der Oberfläche (vorher/nachher).

Aufruf (Server läuft bereits, regelbasiert):

    .venv/bin/python tests/ui/messung.py --url http://127.0.0.1:8123 --out docs/ux/messung_nachher.json

Braucht `playwright`, `axe-playwright-python` und `LOTSE_UI_BROWSER` (Pfad zu Chromium, siehe
requirements-dev.txt). Die Zustände werden über die sichtbare Oberfläche hergestellt (Rollen und
Namen), damit dieselbe Messung für die alte Fallakten-Oberfläche und die neue Oberfläche mit Ansichten
(„Gespräch“, „Mein Plan“, Leistung) funktioniert. Jeder Zustand läuft in einem frischen
Browser-Kontext, damit kein gespeicherter Zustand (localStorage) mitgemessen wird.

Die Funktionen hier nutzen auch die Tests unter tests/ui/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

VIEWPORTS: dict[str, dict] = {
    "desktop": {"width": 1440, "height": 900},
    "mobil_390": {"width": 390, "height": 844},
    "schmal_320": {"width": 320, "height": 640},
    # 400 % Zoom eines 1280×1024-Fensters = 320×256 CSS-Pixel (WCAG 1.4.10)
    "zoom_400": {"width": 320, "height": 256},
}

WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]

PFLEGE_SATZ = "Meine Mutter kommt allein nicht mehr zurecht"
TERMIN_SATZ = "Ich möchte einen Arzttermin."
DEMO_BRIEF = "Synthetischer Entlassungsbrief"
DEMO_IMPFPASS = "Synthetischer Impfpass"
# Aufklapper mit den Demo-Dokumenten (KISS-Fassung zuerst, dann die erste neue Fassung)
DEMO_DISCLOSURES = ("Beispiele zum Ausprobieren", "Beispiel-Dokumente ausprobieren")
REPO = Path(__file__).resolve().parents[2]
BEISPIELE = REPO / "examples"
BRIEF_DATEI = BEISPIELE / "entlassungsbrief_synthetisch.txt"
IMPFPASS_DATEI = BEISPIELE / "impfpass_synthetisch.txt"

# ---------------------------------------------------------------------------
# JavaScript-Hilfen (werden per page.evaluate eingespielt; CDP umgeht die CSP der Seite)
# ---------------------------------------------------------------------------

JS_HILFEN = r"""
(() => {
  if (window.__messung) return;
  const M = {};
  window.__messung = M;
  M.ids = new WeakMap();
  M.naechsteId = 1;
  M.id = (el) => { if (!M.ids.has(el)) M.ids.set(el, M.naechsteId++); return M.ids.get(el); };

  // Visuell versteckt (sr-only-Muster): clip, clip-path oder 1-px-Kasten mit overflow hidden
  M.visuellVersteckt = (el) => {
    for (let a = el; a && a !== document.body; a = a.parentElement) {
      const cs = getComputedStyle(a);
      if (cs.clip && cs.clip !== "auto" && /rect\(0/.test(cs.clip)) return true;
      if (cs.clipPath && /inset\(50%/.test(cs.clipPath)) return true;
      const r = a.getBoundingClientRect();
      if ((r.width <= 1 || r.height <= 1) && cs.overflow !== "visible" && cs.display !== "contents") return true;
    }
    return false;
  };

  M.gerendert = (el) => {
    if (!el || !el.isConnected) return false;
    if (!el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  M.cache = new Map();
  M.textSichtbar = (el) => {
    if (M.cache.has(el)) return M.cache.get(el);
    let ok = M.gerendert(el) && !M.visuellVersteckt(el);
    if (ok) {
      const r = el.getBoundingClientRect();
      // außerhalb der Seite (z. B. Sprunglink vor dem Fokus)
      if (r.bottom + window.scrollY <= 0 || r.right + window.scrollX <= 0) ok = false;
    }
    M.cache.set(el, ok);
    return ok;
  };

  M.textKurz = (s, n = 60) => (s || "").replace(/\s+/g, " ").trim().slice(0, n);

  M.name = (el) => {
    const al = el.getAttribute("aria-label");
    if (al) return M.textKurz(al);
    const lb = el.getAttribute("aria-labelledby");
    if (lb) {
      const t = lb.split(/\s+/).map((i) => document.getElementById(i)).filter(Boolean).map((x) => x.textContent).join(" ");
      if (t.trim()) return M.textKurz(t);
    }
    if (el.labels && el.labels.length) return M.textKurz([...el.labels].map((l) => l.textContent).join(" "));
    const t = el.innerText || el.textContent || el.value || el.title || el.getAttribute("placeholder") || "";
    return M.textKurz(t);
  };

  M.SEL_INTERAKTIV = 'a[href], button, input:not([type="hidden"]), select, textarea, summary, ' +
    '[role="button"], [role="link"], [role="checkbox"], [role="radio"], [role="switch"], [role="tab"], ' +
    '[role="menuitem"], [role="option"], [tabindex]:not([tabindex="-1"])';

  const BLOCK = /^(block|flex|grid|list-item|table|table-cell|table-row|flow-root)/;
  M.inlineLink = (el) => {
    if (el.tagName !== "A") return false;
    const cs = getComputedStyle(el);
    if (!cs.display.startsWith("inline") || cs.display === "inline-block" || cs.display === "inline-flex") return false;
    let block = el.parentElement;
    while (block && !BLOCK.test(getComputedStyle(block).display)) block = block.parentElement;
    if (!block) return false;
    const rest = (block.innerText || "").replace(el.innerText || "", "").replace(/\s+/g, "");
    return rest.length >= 3;
  };

  M.schattenPx = (wert) => {
    if (!wert || wert === "none") return 0;
    let max = 0;
    const teile = wert.split(/,(?![^(]*\))/);
    for (const t of teile) {
      if (/rgba\([^)]*,\s*0\)/.test(t)) continue;
      const laengen = (t.replace(/rgba?\([^)]*\)|#[0-9a-f]+/gi, "").match(/-?[\d.]+px/g) || []).map(parseFloat);
      if (laengen.length >= 4) max = Math.max(max, laengen[3]);
    }
    return max;
  };

  M.fokusPx = (el) => {
    const kandidaten = [el];
    if (M.visuellVersteckt(el) && el.labels) kandidaten.push(...el.labels);
    let px = 0;
    for (const k of kandidaten) {
      for (const pseudo of [null, "::before", "::after"]) {
        const cs = getComputedStyle(k, pseudo);
        if (cs.outlineStyle !== "none") px = Math.max(px, parseFloat(cs.outlineWidth) || 0);
        px = Math.max(px, M.schattenPx(cs.boxShadow));
      }
    }
    return px;
  };

  M.istNachrichtenfeld = (el) => {
    if (!el || !/^(TEXTAREA|INPUT)$/.test(el.tagName)) return false;
    return /Ihre Nachricht|Your message/i.test(M.name(el));
  };

  M.fokusInfo = (bereichSel) => {
    const el = document.activeElement;
    if (!el || el === document.body || el === document.documentElement) return null;
    const bereich = bereichSel ? document.querySelector(bereichSel) : null;
    return {
      id: M.id(el), tag: el.tagName.toLowerCase(), rolle: el.getAttribute("role") || "",
      name: M.name(el), fokus_px: M.fokusPx(el), nachrichtenfeld: M.istNachrichtenfeld(el),
      im_bereich: Boolean(bereich && bereich.contains(el)),
    };
  };

  M.textelemente = (wurzel) => {
    const liste = [];
    const SKIP = /^(SCRIPT|STYLE|NOSCRIPT|OPTION|OPTGROUP|TEMPLATE|TITLE|HEAD)$/;
    for (const el of (wurzel || document.body).querySelectorAll("*")) {
      if (SKIP.test(el.tagName)) continue;
      let text = "";
      for (const n of el.childNodes) if (n.nodeType === 3) text += n.data;
      if (!/\S/.test(text)) continue;
      if (!M.textSichtbar(el)) continue;
      liste.push({ el, px: parseFloat(getComputedStyle(el).fontSize), text: M.textKurz(text, 50) });
    }
    return liste;
  };

  M.texte = (bereichSel) => {
    const wurzel = bereichSel ? document.querySelector(bereichSel) : document.body;
    if (!wurzel) return null;
    const liste = M.textelemente(wurzel);
    const verteilung = {};
    for (const x of liste) { const k = String(Math.round(x.px * 10) / 10); verteilung[k] = (verteilung[k] || 0) + 1; }
    const klein = liste.filter((x) => x.px < 16);
    return {
      gesamt: liste.length,
      unter_16px: klein.length,
      unter_14px: liste.filter((x) => x.px < 14).length,
      kleinste_px: liste.length ? Math.min(...liste.map((x) => x.px)) : null,
      verteilung_px: verteilung,
      beispiele_unter_16px: klein.slice(0, 25).map((x) => ({ px: x.px, tag: x.el.tagName.toLowerCase(), klasse: M.textKurz(x.el.className && x.el.className.baseVal === undefined ? x.el.className : "", 40), text: x.text })),
    };
  };

  M.woerter = (bereichSel) => {
    const wurzel = bereichSel ? document.querySelector(bereichSel) : document.body;
    if (!wurzel) return null;
    let n = 0;
    const tw = document.createTreeWalker(wurzel, NodeFilter.SHOW_TEXT);
    while (tw.nextNode()) {
      const t = tw.currentNode;
      const p = t.parentElement;
      if (!p || /^(SCRIPT|STYLE|NOSCRIPT|OPTION|OPTGROUP|TEMPLATE|TITLE)$/.test(p.tagName)) continue;
      if (!M.textSichtbar(p)) continue;
      const w = t.data.match(/\S+/g);
      if (w) n += w.filter((x) => /[\p{L}\p{N}]/u.test(x)).length;
    }
    return n;
  };

  M.ziele = (bereichSel) => {
    const wurzel = bereichSel ? document.querySelector(bereichSel) : document.body;
    if (!wurzel) return null;
    const gesehen = new Set();
    const ziele = [];
    const inline = [];
    for (const el of wurzel.querySelectorAll(M.SEL_INTERAKTIV)) {
      let ziel = el;
      let ersatz = null;
      if (!M.gerendert(el) || M.visuellVersteckt(el)) {
        // versteckte Datei-Eingaben: das sichtbare Label ist das Ziel
        const lab = el.labels && [...el.labels].find((l) => M.gerendert(l) && !M.visuellVersteckt(l));
        if (!lab) continue;
        ziel = lab; ersatz = "label";
      }
      if (gesehen.has(ziel)) continue;
      gesehen.add(ziel);
      const r = ziel.getBoundingClientRect();
      const eintrag = {
        tag: el.tagName.toLowerCase(), typ: el.getAttribute("type") || el.getAttribute("role") || "",
        name: M.name(el), b: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10,
        // Seitenkoordinaten (für die Abstands-Ausnahme von WCAG 2.5.8)
        x: Math.round((r.left + scrollX) * 10) / 10, y: Math.round((r.top + scrollY) * 10) / 10,
        ersatz, deaktiviert: Boolean(el.disabled),
      };
      if (el.type === "checkbox" || el.type === "radio") {
        const lab = el.closest("label") || (el.labels && el.labels[0]);
        if (lab) { const lr = lab.getBoundingClientRect(); eintrag.label_h = Math.round(lr.height * 10) / 10; eintrag.label_b = Math.round(lr.width * 10) / 10; }
      }
      if (M.inlineLink(el)) inline.push(eintrag); else ziele.push(eintrag);
    }
    const unter24 = ziele.filter((z) => z.b < 24 || z.h < 24);
    const unter44 = ziele.filter((z) => z.b < 44 || z.h < 44);
    // WCAG 2.5.8, Ausnahme „Abstand“: ein Kreis mit 24 px Durchmesser um die Mitte des zu kleinen Ziels
    // schneidet kein anderes Ziel und keinen Kreis eines anderen zu kleinen Ziels.
    const alle = [...ziele, ...inline];
    const mitte = (z) => [z.x + z.b / 2, z.y + z.h / 2];
    const zuKlein = (z) => z.b < 24 || z.h < 24;
    for (const u of unter24) {
      const [cx, cy] = mitte(u);
      u.abstand_ok = !alle.some((t) => {
        if (t === u || !t.b || !t.h) return false;
        const dx = Math.max(t.x - cx, 0, cx - (t.x + t.b));
        const dy = Math.max(t.y - cy, 0, cy - (t.y + t.h));
        if (Math.hypot(dx, dy) < 12) return true;
        if (zuKlein(t)) { const [tx, ty] = mitte(t); return Math.hypot(tx - cx, ty - cy) < 24; }
        return false;
      });
    }
    return {
      gesamt: ziele.length, unter_24px: unter24.length, unter_44px: unter44.length,
      unter_24px_ohne_abstand: unter24.filter((u) => !u.abstand_ok).length,
      liste_unter_24px: unter24, liste_unter_44px: unter44,
      inline_links: inline.length, inline_links_beispiele: inline.slice(0, 15),
    };
  };

  M.ueberlauf = () => {
    const d = document.documentElement;
    const breite = d.clientWidth;
    // innerhalb eines eigenen Scroll- oder Clip-Containers (z. B. Tabelle) zählt nicht als Seitenüberlauf
    const scroller = (el) => {
      for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
        if (getComputedStyle(a).overflowX !== "visible") return true;
      }
      return false;
    };
    const elemente = [];
    for (const el of document.body.querySelectorAll("*")) {
      const r = el.getBoundingClientRect();
      if (!r.width || r.right <= breite + 1) continue;
      if (!M.gerendert(el) || M.visuellVersteckt(el) || scroller(el)) continue;
      elemente.push({ tag: el.tagName.toLowerCase(), klasse: typeof el.className === "string" ? el.className.slice(0, 40) : "", rechts: Math.round(r.right), text: M.textKurz(el.innerText, 40) });
    }
    return {
      horizontal_px: Math.max(0, d.scrollWidth - breite), scroll_breite: d.scrollWidth, sichtbare_breite: breite,
      scroll_hoehe: d.scrollHeight, elemente_rechts_ausserhalb: elemente.length, beispiele: elemente.slice(0, 10),
    };
  };

  M.merkmale = () => {
    const medien = new Set();
    const selektoren = [];
    const lauf = (regeln) => {
      for (const r of regeln) {
        if (r.media && r.conditionText !== undefined) medien.add(r.conditionText);
        else if (r.media && r.media.mediaText) medien.add(r.media.mediaText);
        if (r.selectorText) selektoren.push(r.selectorText);
        if (r.cssRules) lauf(r.cssRules);
      }
    };
    for (const s of document.styleSheets) {
      try { if (s.media && s.media.mediaText) medien.add(s.media.mediaText); lauf(s.cssRules); } catch (_) { /* fremde Quelle */ }
    }
    const m = [...medien].join(" | ");
    const sel = selektoren.join(" ");
    const steuerText = [...document.querySelectorAll("label, legend, button, summary, h2, h3, [role=radio], [role=switch], option")]
      .map((e) => e.textContent.replace(/\s+/g, " ").trim()).join(" | ");
    return {
      forced_colors: /forced-colors/.test(m),
      dunkel: /prefers-color-scheme:\s*dark/.test(m) || /\[data-[a-z-]*=["']?(dunkel|dark)/i.test(sel),
      hoher_kontrast: /prefers-contrast/.test(m) || /\[data-[a-z-]*=["']?(kontrast|hoher|contrast)/i.test(sel) || /Hoher Kontrast/.test(steuerText),
      reduzierte_bewegung: /prefers-reduced-motion/.test(m),
      druck_stylesheet: /(^|\W)print(\W|$)/.test(m),
      textgroesse_steuerung: /Textgröße/.test(steuerText),
      leichte_sprache: /Leichte Sprache/.test(steuerText),
      farbschema_steuerung: /Farbschema/.test(steuerText),
      plan_drucken_knopf: /Plan drucken/.test(steuerText),
      // \b kennt kein „Ä“: Wortgrenze über Unicode-Buchstaben-Klasse
      angaben_aendern: /(^|[^\p{L}])Ändern(?![\p{L}])/u.test(steuerText),
      media_queries: [...medien].sort(),
    };
  };
})();
"""


def hilfen(page) -> None:
    page.evaluate(JS_HILFEN)
    page.evaluate("() => window.__messung.cache.clear()")


# ---------------------------------------------------------------------------
# Browser und Warten
# ---------------------------------------------------------------------------


def browser_starten(p):
    pfad = os.environ.get("LOTSE_UI_BROWSER")
    if not pfad or not Path(pfad).is_file():
        raise SystemExit("LOTSE_UI_BROWSER muss auf eine Chromium-Datei zeigen (siehe requirements-dev.txt).")
    return p.chromium.launch(executable_path=pfad)


def ist_api_post(r) -> bool:
    return r.request.method == "POST" and "/api/" in r.url


def ruhe(page, timeout: int = 20000) -> None:
    """Wartet, bis keine Ladeanzeige mehr aktiv ist."""
    page.wait_for_function(
        """() => !document.querySelector('[aria-busy="true"], .nachricht.laedt, .laedt[aria-hidden="false"]')""",
        timeout=timeout,
    )
    page.wait_for_timeout(150)


def mit_antwort(page, aktion, timeout: int = 30000) -> dict | None:
    """Führt `aktion` aus, wartet auf die API-Antwort und das Ende der Ladeanzeige; liefert das JSON."""
    with page.expect_response(ist_api_post, timeout=timeout) as info:
        aktion()
    try:
        daten = info.value.json()
    except Exception:  # noqa: BLE001 – Fehlerantworten ohne JSON
        daten = None
    ruhe(page, timeout)
    return daten


def sichtbar(locator):
    return locator.filter(visible=True).first


def neue_ui(page) -> bool:
    return page.get_by_role("navigation", name="Hauptnavigation").count() > 0


def laden(page, url: str) -> None:
    """Lädt die Oberfläche in einem frischen Kontext und wartet, bis die erste Sitzung angelegt ist."""
    with page.expect_response(lambda r: r.request.method == "POST" and r.url.endswith("/api/sitzung")):
        page.goto(url)
    sichtbar(page.get_by_role("textbox", name="Ihre Nachricht")).wait_for()
    ruhe(page)


def nachricht(page, text: str) -> dict | None:
    feld = sichtbar(page.get_by_role("textbox", name="Ihre Nachricht"))
    feld.fill(text)
    return mit_antwort(page, lambda: sichtbar(page.get_by_role("button", name="Senden", exact=True)).click())


def antworten(page, name) -> dict | None:
    knopf = sichtbar(page.get_by_role("button", name=name, exact=not isinstance(name, re.Pattern)))
    knopf.wait_for()
    return mit_antwort(page, knopf.click)


# Antworten je Rückfrage-Slot (Optionslabel, Regex oder ("text", Eingabe) für Freitextfragen)
ANTWORT_JE_SLOT = {
    "person.bundesland": "Wien",
    "versicherung.pension": "PVA",
    "versicherung.krankenversicherung": "ÖGK",
    "pflege.antragsart": re.compile(r"^Nein"),
    "termin.anlass": "Vorsorgeuntersuchung",
    "termin.ort": ("text", "Graz"),
    "termin.zeit": "Vormittags",
}


def rueckfragen_beantworten(page, a: dict | None, max_fragen: int = 6) -> dict | None:
    """Beantwortet offene Rückfragen über die sichtbaren Knöpfe bzw. das Nachrichtenfeld."""
    for _ in range(max_fragen):
        rf = (a or {}).get("rueckfrage")
        if not rf:
            break
        wahl = ANTWORT_JE_SLOT.get(rf.get("slot"))
        if isinstance(wahl, tuple):
            a = nachricht(page, wahl[1])
        elif wahl is not None:
            a = antworten(page, wahl)
        elif rf.get("optionen"):
            a = antworten(page, rf["optionen"][0]["label"])
        else:
            break
    return a


def pflegefall(page) -> dict | None:
    return rueckfragen_beantworten(page, nachricht(page, PFLEGE_SATZ))


def termin(page) -> dict | None:
    return rueckfragen_beantworten(page, nachricht(page, TERMIN_SATZ))


def demo(page, name: str) -> dict | None:
    knopf = page.get_by_role("button", name=name)
    if not knopf.filter(visible=True).count():
        for text in DEMO_DISCLOSURES:
            aufklapper = page.get_by_text(text, exact=True)
            if aufklapper.filter(visible=True).count():
                sichtbar(aufklapper).click()
                break
    return mit_antwort(page, sichtbar(knopf).click)


def datei_eingabe(page, *namen: str):
    """Datei-Eingabe zum sichtbaren Label (z. B. „Dokument hinzufügen“); erste passende Beschriftung gewinnt."""
    for name in namen:
        label = page.locator("label").filter(has_text=name).filter(visible=True)
        if label.count():
            fid = label.first.get_attribute("for")
            return page.locator(f"#{fid}") if fid else label.first.locator("input[type=file]")
    raise AssertionError(f"keine sichtbare Datei-Eingabe mit Beschriftung {namen}")


def dokument_hinzufuegen(page, pfad) -> dict | None:
    eingabe = datei_eingabe(page, "Dokument hinzufügen", "Dokument hochladen")
    return mit_antwort(page, lambda: eingabe.set_input_files(str(pfad)))


def demo_oder_hochladen(page, name: str, pfad) -> dict | None:
    """Demo-Knopf, solange angeboten (Leerzustand); sonst dieselbe Beispieldatei über „Dokument hinzufügen“."""
    angeboten = page.get_by_role("button", name=name).filter(visible=True).count() or any(
        page.get_by_text(t, exact=True).filter(visible=True).count() for t in DEMO_DISCLOSURES)
    return demo(page, name) if angeboten else dokument_hinzufuegen(page, pfad)


def route(page, hash_: str) -> None:
    page.evaluate("(h) => { location.hash = h; }", hash_)
    page.wait_for_timeout(300)
    ruhe(page)


def ansicht(page, name: str) -> None:
    """Wechselt über die Hauptnavigation (Name als Teilstring, z. B. „Mein Plan, 3 offene Schritte“)."""
    nav = page.get_by_role("navigation", name="Hauptnavigation")
    sichtbar(nav.get_by_role("link", name=name)).click()
    sichtbar(page.get_by_role("heading", level=1, name=name)).wait_for()
    ruhe(page)


def einstellungen_oeffnen(page):
    dialog = page.get_by_role("dialog", name="Einstellungen")
    if not dialog.is_visible():
        sichtbar(page.get_by_role("banner").get_by_role("button", name="Einstellungen")).click()
        dialog.wait_for()
    return dialog


def einstellung(page, gruppe: str, option, schliessen: bool = True) -> None:
    """Wählt im Dialog „Einstellungen“ in der Radiogruppe `gruppe` die Option `option` (Name oder Regex)."""
    dialog = einstellungen_oeffnen(page)
    radio = dialog.get_by_role("radiogroup", name=gruppe).get_by_role(
        "radio", name=option, exact=not isinstance(option, re.Pattern))
    radio.check()
    page.wait_for_timeout(200)
    ruhe(page)
    if schliessen:
        page.keyboard.press("Escape")
        dialog.wait_for(state="hidden")


TEXTGROESSE = {"A": re.compile(r"^A(?!\+)"), "A+": re.compile(r"^A\+(?!\+)"), "A++": re.compile(r"^A\+\+")}


def fokus(page, bereich: str | None = None) -> dict | None:
    """Infos zum fokussierten Element (None = Fokus auf body)."""
    hilfen(page)
    return page.evaluate("(b) => window.__messung.fokusInfo(b)", bereich)


def fokus_aria(page) -> str:
    """Erste Zeile des Accessibility-Tree-Snapshots des fokussierten Elements, z. B. `- button "Senden"`."""
    loc = page.locator(":focus")
    if not loc.count():
        return ""
    return loc.first.aria_snapshot().splitlines()[0]


def tab_zu(page, muster, max_schritte: int = 160, pruefen=None, zusatz_js: str | None = None) -> str:
    """Drückt Tab (dann Shift+Tab), bis der Snapshot des fokussierten Elements `muster` trifft.

    `pruefen(info)` wird bei jedem Halt aufgerufen (z. B. für die Fokusanzeige). `zusatz_js` ist ein
    JS-Ausdruck `(el) => bool`, der zusätzlich erfüllt sein muss.
    """
    muster = re.compile(muster) if isinstance(muster, str) else muster
    besucht: list[str] = []
    for taste in ("Tab", "Shift+Tab"):
        for _ in range(max_schritte):
            page.keyboard.press(taste)
            info = fokus(page)
            if pruefen:
                pruefen(info)
            zeile = fokus_aria(page)
            besucht.append(zeile)
            if muster.search(zeile) and (not zusatz_js or page.evaluate(f"({zusatz_js})(document.activeElement)")):
                return zeile
    raise AssertionError(f"{muster.pattern!r} per Tastatur nicht erreichbar; zuletzt: {besucht[-12:]}")


# ---------------------------------------------------------------------------
# Einzelmessungen
# ---------------------------------------------------------------------------


def axe_pruefen(page, context=None) -> dict:
    from axe_playwright_python.sync_playwright import Axe

    optionen = {"runOnly": {"type": "tag", "values": WCAG_TAGS + ["best-practice"]},
                "resultTypes": ["violations", "incomplete"]}
    erg = Axe().run(page, context=context, options=optionen).response

    def eintrag(v):
        return {"regel": v["id"], "impact": v.get("impact"), "knoten": len(v["nodes"]),
                "tags": [t for t in v["tags"] if t.startswith("wcag")],
                "ziele": [" ".join(map(str, n["target"])) for n in v["nodes"][:5]]}

    wcag, bp = [], []
    for v in erg["violations"]:
        (wcag if any(t in WCAG_TAGS for t in v["tags"]) else bp).append(eintrag(v))
    nach_impact: dict[str, int] = {}
    for v in wcag:
        nach_impact[v["impact"] or "unbekannt"] = nach_impact.get(v["impact"] or "unbekannt", 0) + v["knoten"]
    return {
        "version": erg.get("testEngine", {}).get("version"),
        "verstoesse_regeln": len(wcag),
        "verstoesse_knoten": sum(v["knoten"] for v in wcag),
        "nach_impact_knoten": nach_impact,
        "verstoesse": wcag,
        "best_practice": bp,
        "unvollstaendig": [{"regel": v["id"], "knoten": len(v["nodes"])} for v in erg.get("incomplete", [])],
    }


def tab_reihenfolge(page, bereich: str | None = None, max_stops: int = 900) -> dict:
    page.evaluate("""() => {
        const b = document.body; b.setAttribute('tabindex', '-1'); b.focus(); b.removeAttribute('tabindex');
        window.scrollTo(0, 0);
    }""")
    stops: list[dict] = []
    gesehen: set[int] = set()
    for _ in range(max_stops):
        page.keyboard.press("Tab")
        info = page.evaluate("(b) => window.__messung.fokusInfo(b)", bereich)
        if info is None or info["id"] in gesehen:
            break
        gesehen.add(info["id"])
        stops.append(info)
    vor_eingabe = next((i for i, s in enumerate(stops) if s["nachrichtenfeld"]), None)
    ohne = [s for s in stops if s["fokus_px"] < 2]
    return {
        "gesamt": len(stops),
        "vor_nachrichtenfeld": vor_eingabe,
        "im_bereich": sum(1 for s in stops if s["im_bereich"]) if bereich else None,
        "ohne_fokusanzeige_2px": len(ohne),
        "ohne_fokusanzeige_beispiele": [{k: s[k] for k in ("tag", "name", "fokus_px")} for s in ohne[:20]],
        "fokus_px_min": min((s["fokus_px"] for s in stops), default=None),
        "erste_10": [s["name"] for s in stops[:10]],
    }


def messen(page, bereich: str | None, mit_tab: bool = True) -> dict:
    hilfen(page)
    page.evaluate("window.scrollTo(0, 0)")
    erg = {
        "axe": axe_pruefen(page),
        "texte": page.evaluate("(b) => window.__messung.texte(null)", None),
        "ziele": page.evaluate("() => window.__messung.ziele(null)"),
        "woerter_seite": page.evaluate("() => window.__messung.woerter(null)"),
        "details_gesamt": page.evaluate("() => document.querySelectorAll('details').length"),
        "details_sichtbar": page.evaluate(
            "() => [...document.querySelectorAll('details')].filter((d) => window.__messung.gerendert(d)).length"),
        "buttons_sichtbar": page.evaluate(
            """() => [...document.querySelectorAll('button, [role=button], input[type=button], input[type=submit], input[type=reset]')]
                     .filter((d) => window.__messung.gerendert(d) && !window.__messung.visuellVersteckt(d)).length"""),
        "links_sichtbar": page.evaluate(
            "() => [...document.querySelectorAll('a[href]')].filter((d) => window.__messung.textSichtbar(d)).length"),
        "aufklapper_sichtbar": page.evaluate(
            "() => [...document.querySelectorAll('summary')].filter((d) => window.__messung.gerendert(d)).length"),
        "hauptaktionen_sichtbar": page.evaluate(
            "() => [...document.querySelectorAll('.hauptaktion')].filter((d) => window.__messung.gerendert(d)).length"),
        "badges_sichtbar": page.evaluate(
            "() => [...document.querySelectorAll('[class*=badge]')].filter((d) => window.__messung.textSichtbar(d)).length"),
        "layout": page.evaluate("() => window.__messung.ueberlauf()"),
        "h1": page.evaluate("() => [...document.querySelectorAll('h1')].filter((h) => window.__messung.gerendert(h)).map((h) => h.textContent.trim())"),
        "titel": page.title(),
    }
    if bereich:
        erg["bereich"] = {
            "selektor": bereich,
            "woerter": page.evaluate("(b) => window.__messung.woerter(b)", bereich),
            "details": page.evaluate("(b) => { const w = document.querySelector(b); return w ? w.querySelectorAll('details').length : null; }", bereich),
            "ziele": (page.evaluate("(b) => window.__messung.ziele(b)", bereich) or {}).get("gesamt"),
        }
    if mit_tab:
        erg["tab"] = tab_reihenfolge(page, bereich)
    return erg


# ---------------------------------------------------------------------------
# Zustände
# ---------------------------------------------------------------------------


def _ansicht_oder_bereich(page, neu: bool, hash_: str, alt_bereich: str) -> str:
    """Neue Oberfläche: zur Ansicht `hash_` wechseln (Bereich main); alte: Bereich auf derselben Seite."""
    if neu:
        route(page, hash_)
        return "main"
    return alt_bereich


def zustand_herstellen(page, url: str, zustand: str) -> tuple[str | None, bool]:
    """Stellt den Zustand her; liefert (Bereich-Selektor, neue Oberfläche?)."""
    laden(page, url)
    neu = neue_ui(page)
    if zustand == "S1_start":
        return ("main" if neu else ".haupt"), neu
    if zustand.startswith("S2") or zustand.startswith("S3"):
        pflegefall(page)
        if zustand == "S2_pflegefall":
            return ("main" if neu else ".akte"), neu
        if zustand == "S2_plan":
            return _ansicht_oder_bereich(page, neu, "#/plan", ".akte"), neu
        if zustand == "S2_akte":
            return _ansicht_oder_bereich(page, neu, "#/akte", ".akte"), neu
        # S3: Leistung Pflegegeld (alt: die aufgeklappte Karte)
        if neu:
            route(page, "#/leistung/pflegegeld")
            return "main", neu
        page.evaluate("""() => { const d = document.getElementById('k-pflegegeld').closest('details');
                                d.open = true; d.id = d.id || 'messung-karte-pflegegeld'; }""")
        return "#messung-karte-pflegegeld", neu
    if zustand.startswith("S4"):
        demo(page, DEMO_BRIEF)
        if zustand == "S4_brief":
            return ("main" if neu else ".akte"), neu
        return _ansicht_oder_bereich(page, neu, "#/akte", ".akte"), neu
    if zustand.startswith("S5"):
        a = termin(page)
        if zustand == "S5_termin":
            return ("main" if neu else ".akte"), neu
        if zustand == "S5_plan":
            return _ansicht_oder_bereich(page, neu, "#/plan", ".akte"), neu
        termin_id = a["termine"][0]["id"]
        return _ansicht_oder_bereich(page, neu, f"#/termin/{termin_id}", "#termine article"), neu
    raise ValueError(zustand)


ZUSTAENDE = {
    "S1_start": "Start (leer)",
    "S2_pflegefall": "Pflegefall Wien/PVA/ÖGK/Erstantrag – Ansicht nach der letzten Antwort",
    "S2_plan": "Pflegefall – Plan (alt: dieselbe Seite, Bereich Fallakte .akte; neu: #/plan)",
    "S2_akte": "Pflegefall – Angaben/Akte (alt: dieselbe Seite, Bereich .akte; neu: #/akte)",
    "S3_leistung": "Leistung Pflegegeld (alt: aufgeklappte Karte; neu: #/leistung/pflegegeld)",
    "S4_brief": "Synthetischer Entlassungsbrief geladen (Demo-Knopf)",
    "S4_akte": "Brief geladen – Dokumente (alt: Bereich .akte; neu: #/akte)",
    "S5_termin": "Arzttermin vorbereitet (Vorsorge, Graz, vormittags)",
    "S5_plan": "Termin vorbereitet – Plan (alt: Bereich .akte; neu: #/plan)",
    "S5_termin_ansicht": "Termin vorbereitet – Terminkarte (alt: article im Bereich #termine; neu: #/termin/<id>)",
}


def zusammenfassen(m: dict) -> dict:
    return {
        "axe_wcag_regeln": m["axe"]["verstoesse_regeln"],
        "axe_wcag_knoten": m["axe"]["verstoesse_knoten"],
        "axe_regel_ids": sorted({v["regel"] for v in m["axe"]["verstoesse"]}),
        "axe_best_practice": sorted({v["regel"] for v in m["axe"]["best_practice"]}),
        "texte": m["texte"]["gesamt"], "texte_unter_16": m["texte"]["unter_16px"],
        "texte_unter_14": m["texte"]["unter_14px"], "kleinste_schrift_px": m["texte"]["kleinste_px"],
        "ziele": m["ziele"]["gesamt"], "ziele_unter_24": m["ziele"]["unter_24px"],
        "ziele_unter_24_ohne_abstand": m["ziele"]["unter_24px_ohne_abstand"],
        "ziele_unter_44": m["ziele"]["unter_44px"], "inline_links": m["ziele"]["inline_links"],
        "woerter_seite": m["woerter_seite"], "woerter_bereich": (m.get("bereich") or {}).get("woerter"),
        "details": m["details_gesamt"], "details_sichtbar": m["details_sichtbar"],
        "buttons_sichtbar": m["buttons_sichtbar"], "links_sichtbar": m["links_sichtbar"],
        "aufklapper_sichtbar": m["aufklapper_sichtbar"], "hauptaktionen_sichtbar": m["hauptaktionen_sichtbar"],
        "tabstopps": (m.get("tab") or {}).get("gesamt"),
        "tabstopps_vor_nachrichtenfeld": (m.get("tab") or {}).get("vor_nachrichtenfeld"),
        "tabstopps_ohne_fokus_2px": (m.get("tab") or {}).get("ohne_fokusanzeige_2px"),
        "seitenhoehe_px": m["layout"]["scroll_hoehe"], "horizontal_ueberlauf_px": m["layout"]["horizontal_px"],
    }


def messung(url: str, zustaende: list[str], viewports: list[str], mit_tab: bool = True) -> dict:
    from playwright.sync_api import sync_playwright

    ergebnis: dict = {"messungen": {}, "zusammenfassung": {}}
    with sync_playwright() as p:
        browser = browser_starten(p)
        ergebnis["meta"] = {
            "url": url, "zeitpunkt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "chromium": browser.version, "playwright": _paketversion("playwright"),
            "axe_playwright_python": _paketversion("axe-playwright-python"),
            "viewports": {k: VIEWPORTS[k] for k in viewports}, "zustaende": {k: ZUSTAENDE[k] for k in zustaende},
            "wcag_tags": WCAG_TAGS,
        }
        for z in zustaende:
            ergebnis["messungen"][z] = {}
            ergebnis["zusammenfassung"][z] = {}
            for v in viewports:
                t0 = time.time()
                ctx = browser.new_context(viewport=VIEWPORTS[v], locale="de-AT")
                page = ctx.new_page()
                page.set_default_timeout(30000)
                bereich, neu = zustand_herstellen(page, url, z)
                m = messen(page, bereich, mit_tab)
                m["sekunden"] = round(time.time() - t0, 1)
                ergebnis["meta"]["ui"] = "neu" if neu else "alt"
                if "axe_core" not in ergebnis["meta"]:
                    ergebnis["meta"]["axe_core"] = m["axe"]["version"]
                    ergebnis["merkmale"] = page.evaluate("() => window.__messung.merkmale()")
                ergebnis["messungen"][z][v] = m
                ergebnis["zusammenfassung"][z][v] = zusammenfassen(m)
                print(f"{z:15} {v:11} {json.dumps(ergebnis['zusammenfassung'][z][v], ensure_ascii=False)}",
                      file=sys.stderr, flush=True)
                ctx.close()
        browser.close()
    return ergebnis


def _paketversion(name: str) -> str | None:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(name)
    except PackageNotFoundError:
        return None


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", required=True, help="Basis-URL des laufenden Lotsen, z. B. http://127.0.0.1:8123/")
    ap.add_argument("--out", required=True, type=Path, help="Zieldatei (JSON)")
    ap.add_argument("--zustaende", nargs="*", default=list(ZUSTAENDE), choices=list(ZUSTAENDE))
    ap.add_argument("--viewports", nargs="*", default=list(VIEWPORTS), choices=list(VIEWPORTS))
    ap.add_argument("--ohne-tab", action="store_true", help="Tab-Reihenfolge nicht durchlaufen (schneller)")
    args = ap.parse_args(argv)
    url = args.url if args.url.endswith("/") else args.url + "/"
    erg = messung(url, args.zustaende, args.viewports, mit_tab=not args.ohne_tab)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(erg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"geschrieben: {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
