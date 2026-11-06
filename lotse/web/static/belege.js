// Belege (Quellen). Inline-Belege (`belege`) und Quellenmarker [n] erscheinen nur bei „Belege anzeigen“ (CSS);
// Leistung und Termin haben zusätzlich immer einen eingeklappten Bereich „Belege (N)“ (`belegeBereich`).
import { el, fokussieren, link } from "./dom.js";
import { t, tf } from "./kern.js";

function quelleEintrag(q, nummer, id, extern) {
  const meta = [
    q.fundstelle ? `${t("fundstelle")}: ${q.fundstelle}` : null,
    q.stand ? `${t("stand")}: ${q.stand}` : (q.art === "recht" ? t("stand_unbekannt") : null),
  ].filter(Boolean).join(" · ");
  const istExtern = extern || q.art === "extern";
  return el("li", { id },
    el("p", { class: "q-kopf" },
      nummer ? `[${nummer}] ` : null,
      el("span", { class: "q-titel" }, q.titel),
      istExtern ? [" ", el("span", { class: "badge badge-extern" }, t("extern_badge"))] : null),
    meta ? el("p", { class: "q-meta" }, meta) : null,
    q.zitat ? el("blockquote", { dir: "auto" }, q.zitat) : null,
    q.url ? el("p", { class: "q-meta" }, link(q.url, q.url)) : null);
}

function liste(quellen, id, praefix, extern) {
  return el("ol", { class: "belege-liste", id, tabindex: "-1", "aria-label": t("quellen") },
    quellen.map((q, i) => quelleEintrag(q, praefix ? i + 1 : null, praefix ? `${praefix}-${i + 1}` : null, extern)));
}

/**
 * Inline-Belege eines Eintrags (nur sichtbar bei „Belege anzeigen“). `id`: stabile DOM-ID; `praefix`: IDs der Einträge
 * für [n]-Verweise im Text (dann nummeriert); `extern`: Eintrag ist insgesamt extern belegt.
 */
export function belege(quellen, { id, praefix = null, extern = false } = {}) {
  const q = (quellen || []).filter(Boolean);
  return q.length ? el("div", { class: "belege" }, liste(q, id, praefix, extern)) : null;
}

/** Immer vorhandener, eingeklappter Bereich „Belege (N)“ (letzter Bereich einer Leistung bzw. eines Termins). */
export function belegeBereich(quellen, id) {
  const q = (quellen || []).filter(Boolean);
  if (!q.length) return null;
  return el("details", { class: "bereich belege-bereich", id },
    el("summary", {}, tf("belege_n", { n: q.length })), liste(q, `${id}-liste`, null, false));
}

/** Text mit [n]-Verweisen auf die Belege der Nachricht (Verweise nur sichtbar bei „Belege anzeigen“). */
export function textMitZitaten(text, praefix) {
  const frag = document.createDocumentFragment();
  for (const teil of text.split(/(\[\d+\])/)) {
    const m = /^\[(\d+)\]$/.exec(teil);
    if (m && praefix) {
      const ziel = `${praefix}-${m[1]}`;
      frag.append(el("sup", { class: "zitat-marke" }, el("a", {
        href: `#${ziel}`, "aria-label": `${t("quelle")} ${m[1]}`,
        onclick: (ev) => {
          ev.preventDefault();
          const e = document.getElementById(ziel);
          if (e && fokussieren(e, { scroll: false })) e.scrollIntoView({ block: "nearest" });
        },
      }, teil)));
    } else if (m) {
      continue;  // Marker ohne Belegliste nicht anzeigen
    } else if (teil) {
      frag.append(document.createTextNode(teil));
    }
  }
  return frag;
}

/** Antworttext als Absätze und Listen („• …“, „– …“, „1. …“ am Zeilenanfang). */
export function textBloecke(text, praefix = null) {
  const frag = document.createDocumentFragment();
  for (const absatz of String(text || "").split(/\n\s*\n/)) {
    let aufzaehlung = null;
    let p = null;
    for (const zeile of absatz.split("\n")) {
      if (!zeile.trim()) continue;
      const m = /^\s*(?:([•\-–])|(\d+)\.)\s+(.*)$/.exec(zeile);
      if (m) {
        const art = m[2] ? "ol" : "ul";
        if (!aufzaehlung || aufzaehlung.tagName.toLowerCase() !== art) {
          aufzaehlung = el(art, {});
          frag.append(aufzaehlung);
        }
        aufzaehlung.append(el("li", {}, textMitZitaten(m[3], praefix)));
        p = null;
      } else {
        aufzaehlung = null;
        if (p) p.append(el("br"));
        else { p = el("p", {}); frag.append(p); }
        p.append(textMitZitaten(zeile.trim(), praefix));
      }
    }
  }
  return frag;
}
