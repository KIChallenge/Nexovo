// Ansicht „Meine Akte“: Angaben (änderbar), für Formulare fehlende Angaben, Dokumente mit ihren zitierten
// Empfehlungen, Impfungen und Erstattungsstatus (je eingeklappt) sowie der Verlauf.
import { $, domId, el, fokussieren, vonIso, zuIso } from "./dom.js";
import { aktion, leistungHref, statusText, t, tf, zustand } from "./kern.js";
import { belege } from "./belege.js";

function abschnitt(id, titel, ...inhalt) {
  const hid = `${id}-titel`;
  return el("section", { class: "akte-abschnitt", id, "aria-labelledby": hid },
    el("h2", { id: hid, tabindex: "-1" }, titel), ...inhalt);
}

// ---- Angaben ---------------------------------------------------------------------

// Eingabezweck (WCAG 1.3.5) nur, wo es um die Person am Gerät geht.
const ZWECK = {
  "person.vorname": "given-name", "person.nachname": "family-name", "person.geburtsdatum": "bday",
  "person.strasse": "address-line1", "person.hausnummer": "address-line2", "person.plz": "postal-code",
  "person.ort": "address-level2", "person.telefon": "tel", "person.email": "email",
  "vertretung.vorname": "given-name", "vertretung.nachname": "family-name", "vertretung.telefon": "tel",
};

function zweck(slot) {
  const z = ZWECK[slot];
  if (!z) return "off";
  if (slot.startsWith("vertretung.")) return z;
  const fuerWen = zustand.angaben.find((x) => x.slot === "anliegen.fuer_wen");
  return fuerWen && fuerWen.wert_roh === "selbst" ? z : "off";
}

function meta(slot, eintrag = {}) {
  const m = zustand.slots.get(slot) || {};
  return {
    label: eintrag.label || m.label || slot,
    typ: eintrag.typ || m.typ || "text",
    optionen: (eintrag.optionen && eintrag.optionen.length ? eintrag.optionen : m.optionen) || [],
    muster_hinweis: eintrag.muster_hinweis || m.muster_hinweis || "",
    sensibel: Boolean(eintrag.sensibel ?? m.sensibel),
    wert_roh: eintrag.sensibel ? "" : (eintrag.wert_roh ?? ""),
  };
}

function bearbeiten(slot) {
  zustand.bearbeiten = slot;
  aktion.neuZeichnen();
  fokussieren(`${domId("angabe", slot)}-feld`, { scroll: false });
}

function abbrechen(knopfId) {
  zustand.bearbeiten = null;
  aktion.neuZeichnen();
  fokussieren(knopfId, { scroll: false }) || fokussieren("angaben-titel", { scroll: false });
}

function angabeFormular(slot, m, { vorhanden, knopfId }) {
  const fid = domId("angabe", slot);
  const feldId = `${fid}-feld`;
  const hilfeId = `${fid}-hilfe`;
  const fehlerId = `${fid}-fehler`;
  let feld;
  if (m.typ === "auswahl" && m.optionen.length) {
    feld = el("select", { id: feldId },
      el("option", { value: "" }, t("bitte_waehlen")),
      m.optionen.map((o) => el("option", { value: o.wert, selected: o.wert === m.wert_roh }, o.label)));
  } else if (m.typ === "datum") {
    feld = el("input", { type: "date", id: feldId, value: zuIso(m.wert_roh), autocomplete: zweck(slot) });
  } else {
    const z = zweck(slot);
    feld = el("input", {
      type: z === "email" ? "email" : (z === "tel" ? "tel" : "text"), id: feldId, value: m.wert_roh,
      inputmode: m.typ === "zahl" ? "numeric" : null, autocomplete: z, spellcheck: "false",
    });
  }
  const hinweise = [
    m.muster_hinweis && !["auswahl", "datum"].includes(m.typ) ? tf("angabe_format", { muster: m.muster_hinweis }) : null,
    m.sensibel ? t("angabe_sensibel_hinweis") : null,
  ].filter(Boolean);
  feld.setAttribute("aria-describedby", [hinweise.length ? hilfeId : null, fehlerId].filter(Boolean).join(" "));
  const fehler = el("p", { id: fehlerId, class: "feld-fehler" });
  const fehlerZeigen = (meldung) => {
    fehler.textContent = meldung;
    feld.setAttribute("aria-invalid", "true");
    feld.focus();
  };
  const form = el("form", { class: "angabe-form", novalidate: true },
    el("label", { for: feldId, class: "feld-label" }, tf("angabe_neu", { label: m.label })),
    feld,
    hinweise.length ? el("p", { id: hilfeId, class: "leise" }, hinweise.join(" ")) : null,
    fehler,
    el("div", { class: "knopf-zeile" },
      el("button", { type: "submit", class: "knopf knopf-rahmen", id: `${fid}-speichern` }, t("speichern")),
      el("button", { type: "button", class: "knopf", onclick: () => abbrechen(knopfId) }, t("abbrechen")),
      vorhanden ? el("button", {
        type: "button", class: "knopf knopf-gefahr", id: `${fid}-loeschen`,
        onclick: () => aktion.angabeSetzen(slot, null, { fehler: fehlerZeigen }),
      }, t("loeschen")) : null));
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const wert = m.typ === "datum" ? vonIso(feld.value) : feld.value.trim();
    if (!wert) {
      fehlerZeigen(t("angabe_leer_fehler"));
      return;
    }
    aktion.angabeSetzen(slot, wert, { fehler: fehlerZeigen });
  });
  form.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") {
      ev.preventDefault();
      abbrechen(knopfId);
    }
  });
  return form;
}

function angabeZeile(x) {
  const knopfId = domId("aendern", x.slot);
  const offen = zustand.bearbeiten === x.slot;
  return el("li", { class: "angabe" },
    el("div", { class: "angabe-kopf" },
      el("p", { class: "angabe-text" },
        el("span", { class: "angabe-label" }, x.label),
        el("span", { class: "angabe-wert", dir: "auto" }, x.wert),
        // Herkunft nur, wenn sie etwas sagt (Dokument, Ortsangabe, von Ihnen geändert)
        x.herkunft && x.herkunft_art && x.herkunft_art !== "dialog" ? el("span", { class: "herkunft" }, `(${x.herkunft})`) : null),
      x.editierbar !== false && !offen ? el("button", {
        type: "button", class: "knopf", id: knopfId, onclick: () => bearbeiten(x.slot),
      }, t("aendern"), el("span", { class: "sr-only" }, ` ${x.label}`)) : null),
    offen ? angabeFormular(x.slot, meta(x.slot, x), { vorhanden: true, knopfId }) : null);
}

const FEHLENDE_SICHTBAR = 4;

/**
 * Pflichtangaben, die in den Formularen der wichtigsten Leistungen noch fehlen (je Slot einmal): vom Backend
 * (`fehlende_angaben_primaer`), sonst aus den Formularen der primären Bündel berechnet.
 */
function fehlendeAngaben() {
  const vorhanden = new Set(zustand.angaben.map((x) => x.slot));
  if (zustand.fehlendePrimaer) {
    return zustand.fehlendePrimaer.filter((x) => !vorhanden.has(x.slot)).map((x) => ({ ...x, fuer: x.fuer || [] }));
  }
  const liste = new Map();
  for (const b of zustand.buendel) {
    if (!b.primaer || !b.formular) continue;
    for (const x of b.formular.fehlende_angaben || b.fehlende_angaben || []) {
      if (vorhanden.has(x.slot)) continue;
      if (!liste.has(x.slot)) liste.set(x.slot, { ...x, fuer: [] });
      const e = liste.get(x.slot);
      if (!e.fuer.includes(b.titel)) e.fuer.push(b.titel);
    }
  }
  return [...liste.values()];
}

function fehlendeZeile(x) {
  const knopfId = domId("eintragen", x.slot);
  const offen = zustand.bearbeiten === x.slot;
  return el("li", { class: "angabe" },
    el("div", { class: "angabe-kopf" },
      el("p", { class: "angabe-text" },
        el("span", { class: "angabe-wert" }, x.label),
        x.fuer.length ? el("span", { class: "herkunft" }, tf("fehlende_fuer", { formulare: x.fuer.join(", ") })) : null),
      offen ? null : el("button", {
        type: "button", class: "knopf", id: knopfId, onclick: () => bearbeiten(x.slot),
      }, t("eintragen"), el("span", { class: "sr-only" }, ` ${x.label}`))),
    offen ? angabeFormular(x.slot, meta(x.slot, x), { vorhanden: false, knopfId }) : null);
}

function fehlendeAbschnitt() {
  const liste = fehlendeAngaben();
  if (!liste.length) return null;
  // Mehr als 4: die ersten 4 sichtbar (und eine gerade geöffnete Eingabe), Rest hinter „Alle N anzeigen“
  const alle = zustand.alleFehlenden || liste.length <= FEHLENDE_SICHTBAR
    || liste.slice(FEHLENDE_SICHTBAR).some((x) => x.slot === zustand.bearbeiten);
  const sichtbar = alle ? liste : liste.slice(0, FEHLENDE_SICHTBAR);
  return abschnitt("fehlende", t("fehlen_noch"),
    el("p", { class: "leise" }, t("fehlende_hilfe")),
    el("ul", { class: "angaben-liste" }, sichtbar.map(fehlendeZeile)),
    alle ? null : el("p", {}, el("button", {
      type: "button", class: "knopf", id: "fehlende-alle",
      onclick: () => {
        zustand.alleFehlenden = true;
        aktion.neuZeichnen();
        fokussieren(domId("eintragen", liste[FEHLENDE_SICHTBAR].slot), { scroll: false });
      },
    }, tf("alle_anzeigen", { n: liste.length }))));
}

// ---- Dokumente, Impfungen, Erstattungsstatus -----------------------------------------

const ekoAnzahl = (n) => (n === 1 ? t("eko_eintrag_eins") : tf("eko_eintraege", { n }));
const kennzeichen = (kz) => (kz && kz.length ? ` · ${t("kennzeichen")}: ${kz.join(", ")}` : "");

// Beispielpackung („z. B.“) – keine Aussage über die Packung im Dokument
function ekoBeispiel(b) {
  if (!b || !b.name) return null;
  return el("span", { class: "leise" }, ` · ${t("eko_beispiel")} `,
    el("span", { dir: "auto" }, b.name), b.pzn ? `, PZN ${b.pzn}` : null);
}

function ekoBlock(e, nr) {
  const status = e.einheitlich === false
    // Gemischte Boxen/Kennzeichen: jede Variante mit Anzahl und Beispiel, häufigste zuerst
    ? el("ul", { class: "eko-varianten" }, (e.varianten || []).map((v) => el("li", {},
      el("strong", {}, t(`box_${v.box}`)), kennzeichen(v.kennzeichen),
      el("span", { class: "leise" }, ` · ${ekoAnzahl(v.anzahl)}`),
      ekoBeispiel(v.beispiel))))
    // Einheitlich: Box und Kennzeichen; Anzahl und Beispiel nennt der erste Satz der Erklärung
    : el("p", {}, el("strong", {}, t(`box_${e.box}`)), kennzeichen(e.kennzeichen));
  return [status,
    e.erklaerung ? el("p", { class: "eko-erklaerung" }, e.erklaerung) : null,
    belege(e.quellen, { id: `medi-${nr}-belege` })];
}

function dokumenteListe() {
  // Zitierte Empfehlungen je Dokument (gleicher Satz für mehrere Leistungen nur einmal, mit allen Leistungen)
  const nachDokument = new Map();
  zustand.buendel.forEach((b) => (b.dokument || []).forEach((d) => {
    const name = (d.quelle && d.quelle.titel) || "";
    if (!nachDokument.has(name)) nachDokument.set(name, new Map());
    const saetze = nachDokument.get(name);
    if (!saetze.has(d.text)) saetze.set(d.text, { d, leistungen: [] });
    saetze.get(d.text).leistungen.push(b);
  }));
  const empfehlungen = (name, praefix) => {
    const saetze = [...(nachDokument.get(name) || new Map()).values()];
    nachDokument.delete(name);
    return saetze.length ? el("ul", { class: "empf-liste" }, saetze.map(({ d, leistungen }, i) => el("li", {},
      el("p", { class: "zitat", dir: "auto" }, d.text),
      el("p", { class: "empf-links" }, leistungen.map((b, k) => [k ? " · " : null,
        el("a", { href: leistungHref(b.leistung_id), class: "ziel-link" }, b.titel)])),
      belege([d.quelle], { id: `${praefix}-${i}-belege` })))) : null;
  };
  const dokumente = zustand.dokumente.map((d, nr) => el("li", {},
    el("p", { class: "dok-kopf" },
      el("span", { class: "dok-name", dir: "auto" }, d.name),
      d.seiten ? el("span", { class: "leise" }, ` · ${d.seiten} ${t(d.seiten === 1 ? "seite_eine" : "seiten")}`) : null),
    d.transkribiert ? el("p", { class: "hinweis-text" }, t("transkribiert_hinweis")) : null,
    empfehlungen(d.name, `dok-${nr}`)));
  // Empfehlungen ohne zuordenbares Dokument (z. B. nach dem Laden eines Falls) bleiben sichtbar
  const rest = [...nachDokument.keys()].map((name, nr) => el("li", {},
    name ? el("p", { class: "dok-name" }, name) : null, empfehlungen(name, `dok-rest-${nr}`)));
  return dokumente.length || rest.length ? el("ul", { class: "dok-liste" }, dokumente, rest) : null;
}

function impfungenBereich() {
  if (!zustand.impfungen.length) return null;
  // Dokumentname nur, wenn die Einträge aus mehreren Dokumenten stammen
  const mehrere = new Set(zustand.impfungen.map((i) => i.dokument)).size > 1;
  return el("details", { class: "bereich", id: "impfungen" },
    el("summary", {}, t("impfungen_titel")),
    el("p", { class: "hinweis-text" }, t("impfungen_hinweis")),
    mehrere ? null : el("p", { class: "leise" }, `${t("dokument")}: ${zustand.impfungen[0].dokument}`),
    el("div", { class: "tabelle-rahmen", role: "region", tabindex: "0", "aria-label": t("impfungen_titel") },
      el("table", {},
        el("thead", {}, el("tr", {},
          el("th", { scope: "col" }, t("impfung")),
          el("th", { scope: "col" }, t("datum")),
          el("th", { scope: "col" }, t("fundstelle")))),
        el("tbody", {}, zustand.impfungen.map((i) => el("tr", {},
          el("td", { dir: "auto" }, i.impfung),
          el("td", { class: "zahl" }, i.datum),
          el("td", {}, mehrere ? `${i.dokument}, ${t("seite")} ${i.seite}` : `${t("seite")} ${i.seite}`)))))));
}

function medikamenteBereich() {
  if (!zustand.medikamente.length) return null;
  return el("details", { class: "bereich", id: "medikamente" },
    el("summary", {}, t("medikamente_titel")),
    el("p", { class: "hinweis-text" }, t("medikamente_hinweis")),
    el("ul", { class: "medi-liste" }, zustand.medikamente.map((m, nr) => el("li", {},
      el("p", { class: "medi-kopf" },
        el("span", { class: "medi-name", dir: "auto" }, m.name_dokument), " ",
        el("span", { class: "leise" }, `(${m.dokument}, ${t("seite")} ${m.seite})`)),
      m.eko ? ekoBlock(m.eko, nr) : el("p", { class: "leise" }, t("eko_nicht_gefunden"))))));
}

function verlaufBereich() {
  const fa = zustand.fallakte;
  if (!fa || !fa.historie.length) return null;
  const letzte = fa.historie.slice(-8).reverse();
  return el("details", { class: "bereich", id: "verlauf-akte" },
    el("summary", {}, `${t("verlauf")} (${letzte.length})`),
    el("ul", { class: "verlauf-liste" }, letzte.map((h) =>
      el("li", {}, `${h.zeit.slice(11, 16)} · ${h.titel}: ${h.text} → ${statusText(h.nach)}`))));
}

export function akteAnzeigen() {
  $("#akte-inhalt").replaceChildren(...[
    abschnitt("angaben", t("angaben"),
      zustand.angaben.length
        ? el("ul", { class: "angaben-liste" }, zustand.angaben.map(angabeZeile))
        : el("p", { class: "leise" }, t("angaben_leer"))),
    fehlendeAbschnitt(),
  ].filter(Boolean));
  const liste = dokumenteListe();
  $("#akte-dokumente").replaceChildren(...[
    liste || el("p", { class: "leise" }, t("dokumente_leer")),
    impfungenBereich(),
    medikamenteBereich(),
  ].filter(Boolean));
  $("#akte-verlauf").replaceChildren(...[verlaufBereich()].filter(Boolean));
}
