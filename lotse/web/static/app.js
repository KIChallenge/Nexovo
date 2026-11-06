// SV KI-Lotse – Oberfläche ohne Build-Schritt (ES-Module). Alle Daten werden per textContent eingefügt (kein innerHTML).
// Ansichten über Hash-Routen: #/gespraech (Standard), #/plan, #/akte; Unteransichten #/leistung/<id>, #/termin/<id>.
import { $, ansagen, fokussieren, symboleEinsetzen } from "./dom.js";
import { BASIS, aktion, api, einst, t, tf, zustand } from "./kern.js";
import {
  darstellungAnwenden, dialogAbgleichen, dialogEinrichten, einstellungenLaden, einstellungenSpeichern,
} from "./einstellungen.js";
import { demoAnzeigen, gespraechAnzeigen, nachrichtAnzeigen, optionenAnzeigen } from "./gespraech.js";
import { akteAnzeigen } from "./akte.js";
import { leistungAnzeigen } from "./leistung.js";
import { planAnzeigen, planText } from "./plan.js";
import { terminAnzeigen } from "./termin.js";
import {
  mikroEinrichten, mikroStatus, vorlesen, vorlesenBeenden, vorlesenBeschriften, vorlesenMoeglich,
} from "./stimme.js";

const ANSICHTEN = ["gespraech", "plan", "akte", "leistung", "termin"];

// ---- Texte ---------------------------------------------------------------------

async function texteSetzen(sprache) {
  let daten = zustand.texteCache.get(sprache);
  if (!daten) {
    daten = await api("GET", `/api/texte?sprache=${encodeURIComponent(sprache)}`);
    zustand.texteCache.set(sprache, daten);
  }
  zustand.T = daten.texte || {};
  zustand.texteSprache = sprache;
  zustand.sprachen = daten.sprachen || [];
  zustand.ki = Boolean(daten.ki);
  texteAnwenden();
}

// Metadaten der Angaben (Typ, Auswahl, Format) für die Eingabeformulare im Plan.
async function slotsLaden(sprache) {
  if (zustand.slotsSprache === sprache) return;
  try {
    const liste = await api("GET", `/api/slots?sprache=${encodeURIComponent(sprache)}`);
    zustand.slots = new Map(liste.map((s) => [s.id, s]));
    zustand.slotsSprache = sprache;
  } catch (_) { /* Formulare nutzen dann die Metadaten der Angaben selbst */ }
}

function modusAnzeigen() {
  const m = zustand.modus === "ki" ? "ki" : "regelbasiert";
  $("#modus-erklaerung").textContent = `${t(`modus_${m}`)}: ${t(`modus_titel_${m}`)}`;
}

function ansichtTitel() {
  const { name, id } = zustand.route;
  if (name === "plan") return t("plan_titel");
  if (name === "akte") return t("akte_titel");
  if (name === "leistung") {
    const b = zustand.buendel.find((x) => x.leistung_id === id);
    return b ? b.titel : t("leistung_fehlt");
  }
  if (name === "termin") {
    const tm = zustand.termine.find((x) => x.id === id);
    return tm ? `${t("termin_titel")}: ${tm.anlass_label}` : t("leistung_fehlt");
  }
  return t("chat_titel");
}

const titelSetzen = () => { document.title = `${ansichtTitel()} – ${t("titel")}`; };

function texteAnwenden() {
  const sp = zustand.texteSprache || "de";
  const info = zustand.sprachen.find((s) => s.code === sp);
  document.documentElement.lang = sp;
  document.documentElement.dir = (info && info.richtung) || "ltr";
  document.querySelectorAll("[data-t]").forEach((e) => { e.textContent = t(e.dataset.t); });
  $("#eingabe").placeholder = t("chat_platzhalter");
  const q = zustand.T.quelle_1450;
  const quelle = q ? `${t("quelle")}: ${q.titel}, ${q.fundstelle}` : "";
  $("#grenze-quelle").textContent = quelle;
  $("#grenze-quelle-druck").textContent = quelle;
  document.querySelectorAll(".vorlesen").forEach(vorlesenBeschriften);
  if (!$("#mikro").hidden) mikroStatus();
  $("#plan-vorlesen").hidden = !vorlesenMoeglich;
  modusAnzeigen();
  dialogAbgleichen();
  demoAnzeigen();
  titelSetzen();
}

// ---- Ansichten und Navigation ------------------------------------------------------

function ansichtZeichnen() {
  gespraechAnzeigen();
  const speichern = $("#fall-speichern");
  if (zustand.sitzung) speichern.href = `/api/sitzung/${encodeURIComponent(zustand.sitzung)}/export`;
  else speichern.removeAttribute("href");
  if (zustand.route.name === "plan") {
    planAnzeigen();
    druckDatum();
  } else if (zustand.route.name === "akte") {
    akteAnzeigen();
  } else if (zustand.route.name === "leistung") {
    leistungAnzeigen(zustand.route.id);
  } else if (zustand.route.name === "termin") {
    terminAnzeigen(zustand.route.id);
  }
  titelSetzen();
}

const sichtbar = (e) => e && e.isConnected && !e.closest("[hidden]") && e.getClientRects().length > 0;

/** Neu zeichnen und den Fokus behalten (gleiche ID), falls das fokussierte Element ersetzt wurde. */
function neuZeichnen() {
  const fokusId = document.activeElement && document.activeElement.id;
  ansichtZeichnen();
  fokusHalten(fokusId);
}

function fokusHalten(fokusId, { nachAntwort = false } = {}) {
  const aktiv = document.activeElement;
  const option = document.getElementById("option-0");
  const naechstes = () => (sichtbar(option) ? option : $("#eingabe"));
  if (nachAntwort && zustand.route.name === "gespraech") {
    naechstes().focus();
    return;
  }
  if (aktiv && aktiv !== document.body && sichtbar(aktiv)) return;
  if (fokusId && /^option-/.test(fokusId) && zustand.route.name === "gespraech") {
    naechstes().focus();
    return;
  }
  const ziel = fokusId && document.getElementById(fokusId);
  if (sichtbar(ziel)) { ziel.focus(); return; }
  if (zustand.route.name === "gespraech") naechstes().focus();
  else fokussieren(`h-${zustand.route.name}`, { scroll: false });
}

function routeLesen() {
  const h = location.hash || "";
  const m = /^#\/(leistung|termin)\/(.+)$/.exec(h);
  if (m) return { name: m[1], id: decodeURIComponent(m[2]) };
  if (h === "#/plan") return { name: "plan", id: null };
  if (h === "#/akte") return { name: "akte", id: null };
  return { name: "gespraech", id: null };
}

function routeAnwenden(fokus = true) {
  const neu = routeLesen();
  if (zustand.route.name === "plan" && neu.name !== "plan") zustand.planErledigt.clear();
  if (neu.name !== "akte") zustand.bearbeiten = null;
  zustand.route = neu;
  vorlesenBeenden();
  for (const n of ANSICHTEN) $(`#ansicht-${n}`).hidden = n !== neu.name;
  const unteransicht = neu.name === "leistung" || neu.name === "termin";
  const tab = unteransicht ? "plan" : neu.name;
  document.querySelectorAll(".tabs a[data-route]").forEach((a) => {
    if (a.dataset.route !== tab) a.removeAttribute("aria-current");
    else a.setAttribute("aria-current", unteransicht ? "true" : "page");
  });
  $("#skip-eingabe").hidden = neu.name !== "gespraech";
  fehlerVerbergen();
  ansichtZeichnen();
  if (!fokus) return;
  const ziel = zustand.fokusZiel;
  zustand.fokusZiel = null;
  if (!(ziel && fokussieren(ziel))) {
    window.scrollTo(0, 0);
    fokussieren(`h-${neu.name}`, { scroll: false });
  }
  ansagen(tf("ansicht_angezeigt", { titel: ansichtTitel() }));
}

function navigieren(hash, ziel = null) {
  zustand.fokusZiel = ziel;
  if (location.hash === hash) routeAnwenden(true);
  else location.hash = hash;
}

// ---- Anfragen ------------------------------------------------------------------------

function beschaeftigt(an) {
  zustand.beschaeftigt = an;
  $("#inhalt").setAttribute("aria-busy", String(an));
  document.querySelectorAll("#senden, .kachel, #neu, #optionen-knoepfe button").forEach((b) => {
    if (an) b.setAttribute("aria-disabled", "true");
    else b.removeAttribute("aria-disabled");
  });
}

function fehlerZeigen(meldung) {
  if (zustand.route.name === "gespraech") {
    nachrichtAnzeigen("lotse", meldung);
    ansagen(meldung);
  } else {
    const box = $("#fehler-meldung");
    box.textContent = meldung;
    box.hidden = false;
  }
}

function fehlerVerbergen() {
  const box = $("#fehler-meldung");
  box.hidden = true;
  box.textContent = "";
}

function zustandZuruecksetzen() {
  $("#verlauf").replaceChildren();
  Object.assign(zustand, {
    buendel: [], termine: [], impfungen: [], medikamente: [], begonnen: false, bearbeiten: null, letzteAntwort: "",
    fehlendePrimaer: null, alleFehlenden: false,
  });
  zustand.planErledigt.clear();
}

function vorlesText(a) {
  const r = a.rueckfrage;
  if (!r || !r.optionen || !r.optionen.length) return a.text;
  return `${a.text}\n${t("antwortmoeglichkeiten")}: ${r.optionen.map((o) => o.label).join(", ")}.`;
}

async function antwortAnzeigen(a, { blase = true, stumm = false, fokus = true, fokusId = null, nachAntwort = false } = {}) {
  Object.assign(zustand, {
    sitzung: a.sitzung_id, sprache: a.sprache, stil: a.stil, modus: a.modus,
    richtung: a.richtung === "rtl" ? "rtl" : "ltr", rueckfrage: a.rueckfrage,
  });
  einst.sprache = a.sprache;
  einst.stil = a.stil;
  einstellungenSpeichern();
  if (zustand.texteSprache !== a.sprache) {
    try { await texteSetzen(a.sprache); } catch (_) { /* Oberfläche bleibt in der bisherigen Sprache */ }
  }
  await slotsLaden(a.sprache);
  $("#inhalt").dir = zustand.richtung;
  if (!a.grenze) {
    // Bei einer Grenzantwort bleibt der bisherige Fallstand sichtbar.
    zustand.buendel = a.buendel || [];
    zustand.termine = a.termine || [];
    zustand.impfungen = a.impfungen || [];
    zustand.medikamente = a.medikamente || [];
  }
  zustand.fallakte = a.fallakte;
  zustand.angaben = a.angaben || [];
  zustand.fehlendePrimaer = Array.isArray(a.fehlende_angaben_primaer) ? a.fehlende_angaben_primaer : null;
  zustand.uebersicht = a.status_uebersicht || null;
  zustand.dokumente = a.dokumente || [];
  fehlerVerbergen();
  if (blase) {
    nachrichtAnzeigen("lotse", a.text, { quellen: a.quellen || [], grenze: Boolean(a.grenze), zeigen: !stumm });
    zustand.letzteAntwort = vorlesText(a);
  }
  modusAnzeigen();
  optionenAnzeigen(a.rueckfrage);
  ansichtZeichnen();
  if (!stumm) ansagen(a.ansage || t("antwort_da"));
  if (fokus) fokusHalten(fokusId, { nachAntwort });
}

async function laufen(aufruf, {
  neu = false, anzeige = null, warten = true, stumm = false, fokus = true, nachAntwort = false,
} = {}) {
  if (zustand.beschaeftigt) return null;
  const fokusId = document.activeElement && document.activeElement.id;
  beschaeftigt(true);
  const warte = warten ? nachrichtAnzeigen("lotse", t("laedt"), { laedt: true }) : null;
  try {
    const a = await aufruf();
    if (warte) warte.remove();
    if (neu) {
      // Neuer oder wiederhergestellter Fall: Gespräch neu beginnen
      zustandZuruecksetzen();
      if (anzeige) {
        nachrichtAnzeigen("nutzer", anzeige);
        zustand.begonnen = true;
      }
    }
    beschaeftigt(false);
    await antwortAnzeigen(a, { fokusId, stumm, fokus, nachAntwort });
    return a;
  } catch (err) {
    if (warte) warte.remove();
    beschaeftigt(false);
    fehlerZeigen(`${t("fehler")} (${err.message})`);
    neuZeichnen();  // z. B. eine angeklickte Checkbox wieder auf den gespeicherten Stand
    return null;
  }
}

function begonnen() {
  zustand.begonnen = true;
  gespraechAnzeigen();
}

function senden(text, anzeige = null, { nachAntwort = true } = {}) {
  const sauber = (text || "").trim();
  if (!sauber || !zustand.sitzung || zustand.beschaeftigt) return Promise.resolve(null);
  nachrichtAnzeigen("nutzer", anzeige || sauber);
  begonnen();
  return laufen(() => api("POST", `/api/sitzung/${zustand.sitzung}/nachricht`, { text: sauber }), { nachAntwort });
}

async function sitzungAnlegen() {
  try {
    return await api("POST", "/api/sitzung", { sprache: einst.sprache, stil: einst.stil });
  } catch (_) {
    // Gespeicherte Sprache nicht verfügbar (z. B. weitere Sprache ohne KI-Modus): Deutsch bzw. Englisch
    return api("POST", "/api/sitzung", { sprache: BASIS.includes(einst.sprache) ? einst.sprache : "de", stil: "einfach" });
  }
}

const neueSitzung = (opt = {}) => laufen(sitzungAnlegen, { neu: true, warten: false, ...opt });

function dateiSenden(f) {
  if (!f || !zustand.sitzung || zustand.beschaeftigt) return Promise.resolve();
  nachrichtAnzeigen("nutzer", `[${f.name}]`);
  begonnen();
  const fd = new FormData();
  fd.append("datei", f);
  return laufen(() => api("POST", `/api/sitzung/${zustand.sitzung}/dokument`, fd, true));
}

function fallLaden(f) {
  if (!f || zustand.beschaeftigt) return Promise.resolve();
  const fd = new FormData();
  fd.append("datei", f);
  return laufen(() => api("POST", "/api/import", fd, true), { neu: true, anzeige: `[${t("fall_laden")}: ${f.name}]` });
}

// ---- Aktionen für die Ansichten ---------------------------------------------------------

Object.assign(aktion, {
  senden: (wert, label) => senden(wert, label),
  neuZeichnen: ansichtZeichnen,
  navigieren,

  statusSetzen(schrittId, status) {
    if (zustand.beschaeftigt || !zustand.sitzung) { neuZeichnen(); return null; }
    return laufen(() => api("POST",
      `/api/sitzung/${zustand.sitzung}/schritt/${encodeURIComponent(schrittId)}`, { status }), { warten: false });
  },

  terminStarten(anlass, leistung, anzeige) {
    if (zustand.beschaeftigt || !zustand.sitzung) return null;
    if (zustand.route.name !== "gespraech") navigieren("#/gespraech");
    nachrichtAnzeigen("nutzer", anzeige);
    begonnen();
    return laufen(() => api("POST", `/api/sitzung/${zustand.sitzung}/termin`, { anlass, leistung }),
      { nachAntwort: true });
  },

  terminAendern(terminId, daten) {
    return laufen(() => api("POST",
      `/api/sitzung/${zustand.sitzung}/termin/${encodeURIComponent(terminId)}`, daten), { warten: false });
  },

  /** Angabe setzen (wert) oder löschen (null); Fehler erscheinen am Feld. */
  async angabeSetzen(slot, wert, { fehler } = {}) {
    if (zustand.beschaeftigt || !zustand.sitzung) return;
    beschaeftigt(true);
    let a;
    try {
      a = await api("POST", `/api/sitzung/${zustand.sitzung}/angabe`, { slot, wert });
    } catch (err) {
      beschaeftigt(false);
      const meldung = err.status === 400 ? err.message : `${t("fehler")} (${err.message})`;
      if (fehler) fehler(meldung);
      else fehlerZeigen(meldung);
      return;
    }
    beschaeftigt(false);
    zustand.bearbeiten = null;
    const knopf = `aendern-${slot.replace(/[^A-Za-z0-9_-]/g, "-")}`;
    await antwortAnzeigen(a, { fokusId: wert ? knopf : "angaben-titel" });
    if (!document.activeElement || document.activeElement === document.body) {
      fokussieren(wert ? knopf : "angaben-titel", { scroll: false });
    }
  },

  async akteNeuLaden() {
    if (!zustand.sitzung || zustand.beschaeftigt) return;
    try {
      await antwortAnzeigen(await api("GET", `/api/sitzung/${zustand.sitzung}`), { blase: false, stumm: true });
    } catch (_) { /* Anzeige bleibt unverändert */ }
  },

  belegeSetzen(an) {
    einst.belege = Boolean(an);
    einstellungenSpeichern();
    darstellungAnwenden();
  },

  demoLaden(d, titel) {
    if (!zustand.sitzung || zustand.beschaeftigt) return null;
    nachrichtAnzeigen("nutzer", `[${titel}]`);
    begonnen();
    return laufen(() => api("POST", `/api/sitzung/${zustand.sitzung}/demo/${encodeURIComponent(d.name)}`));
  },

  async einstellen(aenderung) {
    const gleich = (aenderung.sprache || zustand.sprache) === zustand.sprache
      && (aenderung.stil || zustand.stil) === zustand.stil;
    if (gleich || zustand.beschaeftigt || !zustand.sitzung) {
      dialogAbgleichen();
      return;
    }
    vorlesenBeenden();
    await laufen(() => api("POST", `/api/sitzung/${zustand.sitzung}/einstellungen`, aenderung), { warten: false });
    dialogAbgleichen();
  },
});

// ---- Ereignisse ------------------------------------------------------------------------

function dateiKnopf(input, beiAuswahl) {
  const label = document.querySelector(`label[for="${input.id}"]`);
  input.addEventListener("focus", () => label.classList.add("datei-fokus"));
  input.addEventListener("blur", () => label.classList.remove("datei-fokus"));
  input.addEventListener("change", async () => {
    const f = input.files[0];
    input.value = "";
    await beiAuswahl(f);
  });
}

function verbinden() {
  $("#eingabe-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    if (zustand.beschaeftigt) return;
    const feld = $("#eingabe");
    const text = feld.value;
    if (!text.trim()) return;
    feld.value = "";
    senden(text, null, { nachAntwort: false });
  });
  $("#eingabe").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) {
      ev.preventDefault();
      $("#eingabe-form").requestSubmit();
    }
  });
  document.querySelectorAll("[data-szenario]").forEach((b) => b.addEventListener("click", () => {
    const satz = (zustand.T.beispiele_saetze || {})[b.dataset.szenario];
    if (satz) senden(satz);
  }));
  $("#neu").addEventListener("click", async () => {
    if (zustand.beschaeftigt) return;
    const etwas = zustand.begonnen || zustand.buendel.length || zustand.termine.length;
    if (etwas && !window.confirm(t("neuer_fall_frage"))) return;
    vorlesenBeenden();
    if (await neueSitzung()) navigieren("#/gespraech");
  });
  dateiKnopf($("#datei"), dateiSenden);
  dateiKnopf($("#akte-datei"), dateiSenden);
  dateiKnopf($("#fall-datei"), fallLaden);
  $("#vorlesen-antwort").addEventListener("click", (ev) => vorlesen(ev.currentTarget, zustand.letzteAntwort));
  $("#plan-drucken").addEventListener("click", () => window.print());
  $("#plan-vorlesen").addEventListener("click", (ev) => vorlesen(ev.currentTarget, planText()));
  // Sprunglinks fokussieren ihr Ziel, ohne die Hash-Route zu verändern
  document.querySelectorAll(".skip-link").forEach((a) => a.addEventListener("click", (ev) => {
    ev.preventDefault();
    fokussieren(a.getAttribute("href").slice(1));
  }));
  window.addEventListener("hashchange", () => {
    if (!location.hash || location.hash.startsWith("#/")) routeAnwenden(true);
  });
  // Druckfassung mit Datum
  window.addEventListener("beforeprint", druckDatum);
}

function druckDatum() {
  const datum = new Date().toLocaleDateString(document.documentElement.lang || "de");
  $("#druck-datum").textContent = tf("druck_datum", { datum });
}

async function start() {
  einstellungenLaden();
  darstellungAnwenden();
  symboleEinsetzen();
  verbinden();
  dialogEinrichten();
  mikroEinrichten();
  routeAnwenden(false);
  beschaeftigt(true);  // bis die erste Sitzung steht, laufen Klicks ins Leere – daher als beschäftigt markiert
  try {
    try {
      await texteSetzen(einst.sprache);
    } catch (_) {
      await texteSetzen("de");
    }
    zustand.demo = await api("GET", "/api/demo/dokumente");
    demoAnzeigen();
    beschaeftigt(false);
    await neueSitzung({ stumm: true, fokus: false });
  } catch (err) {
    beschaeftigt(false);
    nachrichtAnzeigen("lotse", `Fehler / Error: ${err.message}`);
  }
  ansichtZeichnen();
}

start();
