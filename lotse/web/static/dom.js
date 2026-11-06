// DOM-Hilfen ohne Zustand. Alle Daten werden per textContent eingefügt (kein innerHTML).

export const $ = (sel) => document.querySelector(sel);

export function el(tag, attrs = {}, ...kinder) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : String(v));
  }
  for (const kind of kinder.flat(Infinity)) {
    if (kind === null || kind === undefined || kind === false || kind === "") continue;
    e.append(kind instanceof Node ? kind : document.createTextNode(String(kind)));
  }
  return e;
}

// Symbole (24×24, Linienstil). Immer aria-hidden und nur neben sichtbarem Text bzw. mit Textalternative.
const SYMBOLE = {
  gespraech: ["M4 5h16v11H9l-5 4z"],
  akte: ["M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"],
  plan: ["M10 6h10", "M10 12h10", "M10 18h10", "M4 6l1.5 1.5L8 5", "M4 12l1.5 1.5L8 11", "M4 18l1.5 1.5L8 17"],
  zahnrad: ["M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"],
  mikro: ["M9 5a3 3 0 0 1 6 0v6a3 3 0 0 1-6 0z", "M5 10v1a7 7 0 0 0 14 0v-1", "M12 18v4"],
  senden: ["M4 12l16-8-6 16-3-7z", "M11 13l9-9"],
  lautsprecher: ["M4 9v6h4l5 4V5L8 9z", "M16.5 8.5a5 5 0 0 1 0 7", "M19 6a8.5 8.5 0 0 1 0 12"],
  drucker: ["M7 9V3h10v6", "M7 17H4v-8h16v8h-3", "M7 14h10v7H7z"],
  hochladen: ["M12 16V4", "M7 9l5-5 5 5", "M4 20h16"],
  herunterladen: ["M12 4v12", "M7 11l5 5 5-5", "M4 20h16"],
  kamera: ["M4 8h3l2-3h6l2 3h3v11H4z", "M12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"],
  haken: ["M5 12.5l4.5 4.5L19 7"],
  zurueck: ["M15 18l-6-6 6-6"],
  kasten: ["M5 4h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"],
  "kasten-haken": ["M5 4h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z", "M8 12.5l3 3 5-6"],
  weiter: ["M9 6l6 6-6 6"],
};
const SVG = "http://www.w3.org/2000/svg";

export function symbol(name) {
  const svg = document.createElementNS(SVG, "svg");
  for (const [k, v] of Object.entries({
    class: `symbol symbol-${name}`, viewBox: "0 0 24 24", width: "24", height: "24", fill: "none",
    stroke: "currentColor", "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round",
    "aria-hidden": "true", focusable: "false",
  })) svg.setAttribute(k, v);
  for (const d of SYMBOLE[name] || []) {
    const p = document.createElementNS(SVG, "path");
    p.setAttribute("d", d);
    svg.append(p);
  }
  return svg;
}

// Statische Knöpfe/Links mit data-icon bekommen ihr Symbol vorangestellt.
export function symboleEinsetzen(wurzel = document) {
  wurzel.querySelectorAll("[data-icon]").forEach((e) => {
    if (!e.querySelector(":scope > svg.symbol")) e.prepend(symbol(e.dataset.icon));
  });
}

// Nur http(s) und Pfade der eigenen App als Link zulassen.
export function sichereUrl(u) {
  if (!u) return null;
  if (u.startsWith("/") && !u.startsWith("//")) return u;
  try {
    const x = new URL(u);
    return x.protocol === "https:" || x.protocol === "http:" ? x.href : null;
  } catch (_) {
    return null;
  }
}

export const kurzUrl = (u) => u.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "");

export function link(url, text) {
  const href = sichereUrl(url);
  if (!href) return null;
  return el("a", { href, target: "_blank", rel: "noopener noreferrer", class: "link-extern" }, text || kurzUrl(href));
}

// Slot-/Schritt-IDs enthalten Punkte; für DOM-IDs vereinheitlichen.
export const domId = (praefix, id) => `${praefix}-${String(id).replace(/[^A-Za-z0-9_-]/g, "-")}`;

// TT.MM.JJJJ ↔ JJJJ-MM-TT (Wert von <input type="date">)
export const zuIso = (d) => {
  const m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(d || "");
  return m ? `${m[3]}-${m[2]}-${m[1]}` : "";
};
export const vonIso = (d) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d || "");
  return m ? `${m[3]}.${m[2]}.${m[1]}` : "";
};

// Höflich angesagte Meldung (eine Live-Region für alles; gleiche Texte werden erneut angesagt).
let ansageNr = 0;
export function ansagen(text) {
  const region = document.getElementById("ansage");
  if (!region || !text) return;
  const nr = ++ansageNr;
  region.textContent = "";
  window.setTimeout(() => { if (nr === ansageNr) region.textContent = text; }, 60);
}

// Fokus setzen, ohne dass das Ziel dauerhaft in der Tab-Reihenfolge landet.
export function fokussieren(ziel, { scroll = true } = {}) {
  const e = typeof ziel === "string" ? document.getElementById(ziel) : ziel;
  if (!e) return false;
  if (!e.matches("a[href], button, input, select, textarea, summary, [tabindex]")) e.setAttribute("tabindex", "-1");
  if (scroll) e.scrollIntoView({ block: "start" });
  e.focus({ preventScroll: true });
  return document.activeElement === e;
}
