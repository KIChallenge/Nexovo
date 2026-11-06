// Gemeinsamer Zustand, Texte, API-Zugriff und die Aktionen, die app.js für die Ansichten bereitstellt.

export const BASIS = ["de", "en"];
export const SPRACH_TAG = { de: "de-AT", en: "en-GB", tr: "tr-TR", bs: "bs-BA", uk: "uk-UA", ar: "ar" };

export const zustand = {
  sitzung: null, sprache: "de", stil: "einfach", richtung: "ltr", modus: "regelbasiert",
  T: {}, texteSprache: null, texteCache: new Map(), sprachen: [], ki: false,
  slots: new Map(),  // Slot-ID → Metadaten aus /api/slots (Sprache der Oberfläche)
  slotsSprache: null,
  buendel: [], fallakte: null, angaben: [], termine: [], impfungen: [], medikamente: [],
  uebersicht: null, dokumente: [], demo: [],
  rueckfrage: null, letzteAntwort: "",  // Text für den einen „Vorlesen“-Knopf (letzte Antwort inkl. Optionen)
  nr: 0, beschaeftigt: false, begonnen: false,
  route: { name: "gespraech", id: null },
  fokusZiel: null,  // ID, die nach dem nächsten Ansichtswechsel statt der h1 den Fokus bekommt
  planErledigt: new Map(),  // Aufgaben-ID → { id, vorher } des gerade abgehakten Schritts (bleibt rückgängig machbar)
  bearbeiten: null,  // Slot-ID der gerade geöffneten Angaben-Eingabe
  fehlendePrimaer: null,  // Antwort.fehlende_angaben_primaer (fehlt sie, berechnet „Meine Akte“ selbst)
  alleFehlenden: false,  // „Alle N anzeigen“ bei den fehlenden Angaben gewählt
};

// Persönliche Einstellungen (localStorage); Sprache und Darstellung gelten zusätzlich für die Sitzung.
export const einst = { sprache: "de", stil: "einfach", groesse: "100", farbe: "system", belege: false, tempo: "normal" };

export const t = (key) => {
  const v = zustand.T && zustand.T[key];
  return typeof v === "string" ? v : key;
};
export const tf = (key, werte) => t(key).replace(/\{(\w+)\}/g, (m, k) => (k in werte ? String(werte[k]) : m));
export const statusText = (s) => (zustand.T.status && zustand.T.status[s]) || s;

// Fehlermeldungen des Servers: Text oder {de, en}.
function meldungAus(detail) {
  if (!detail) return null;
  if (typeof detail === "string") return detail;
  if (typeof detail === "object") {
    const sp = BASIS.includes(zustand.sprache) ? zustand.sprache : "en";
    if (typeof detail[sp] === "string") return detail[sp];
    if (typeof detail.de === "string") return detail.de;
  }
  return JSON.stringify(detail);
}

export class ApiFehler extends Error {
  constructor(meldung, status) {
    super(meldung);
    this.status = status;
  }
}

export async function api(methode, url, body, alsFormular = false) {
  const opt = { method: methode, headers: {} };
  if (body !== undefined) {
    if (alsFormular) opt.body = body;
    else { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  }
  const r = await fetch(url, opt);
  if (!r.ok) {
    let meldung = r.statusText;
    try {
      meldung = meldungAus((await r.json()).detail) || meldung;
    } catch (_) { /* keine JSON-Antwort */ }
    throw new ApiFehler(meldung, r.status);
  }
  return r.json();
}

// Von app.js befüllt: senden, statusSetzen, terminStarten, terminAendern, angabeSetzen, akteNeuLaden,
// belegeSetzen, navigieren, neuZeichnen, demoLaden, einstellen.
export const aktion = {};

// Leistungs-ID bzw. Termin-ID → Fallakten-Eintrag
export function eintraegeNachLeistung() {
  const fa = zustand.fallakte || { eintraege: [] };
  return Object.fromEntries(fa.eintraege.map((e) => [e.leistung_id, e]));
}

export function schrittVon(eintrag, schrittId) {
  return eintrag ? eintrag.schritte.find((s) => s.id === schrittId) || null : null;
}

export const leistungHref = (id) => `#/leistung/${encodeURIComponent(id)}`;
export const terminHref = (id) => `#/termin/${encodeURIComponent(id)}`;

/**
 * Offene Aufgaben in fester Reihenfolge: wichtigste Leistung, Termine, übrige wichtige Leistungen.
 * Je Aufgabe: nächster offener Schritt (`schritt`) und ggf. der gerade im Plan abgehakte (`abgehakt`).
 */
export function aufgaben() {
  const fa = zustand.fallakte || { eintraege: [] };
  const nachLeistung = Object.fromEntries(fa.eintraege.map((e) => [e.leistung_id, e]));
  const nachTermin = Object.fromEntries(fa.eintraege.filter((e) => e.termin_id).map((e) => [e.termin_id, e]));
  const mitGemerktem = (id, eintrag, schrittId) => {
    const gemerkt = zustand.planErledigt.get(id);
    const abgehakt = gemerkt ? schrittVon(eintrag, gemerkt.id) : null;
    return { schritt: schrittVon(eintrag, schrittId), abgehakt: abgehakt && abgehakt.status === "erledigt" ? abgehakt : null };
  };
  const leistung = (b) => {
    const s = mitGemerktem(b.leistung_id, nachLeistung[b.leistung_id], b.naechster_schritt);
    return s.schritt || s.abgehakt ? {
      art: "leistung", id: b.leistung_id, titel: b.titel, href: leistungHref(b.leistung_id), b, ...s,
      text: s.schritt ? s.schritt.text : "",
    } : null;
  };
  const termin = (tm) => {
    const e = nachTermin[tm.id];
    const s = mitGemerktem(tm.id, e, e && e.naechster_schritt);
    if (tm.status === "erledigt" || !(s.schritt || s.abgehakt)) return null;
    const wann = tm.datum ? ` – ${tm.datum}${tm.uhrzeit ? `, ${tm.uhrzeit}` : ""}` : "";
    return {
      art: "termin", id: tm.id, titel: `${t("termin_titel")}: ${tm.anlass_label}`, href: terminHref(tm.id), tm, ...s,
      text: s.schritt ? `${s.schritt.text}${s.schritt.schritt_id === "wahrnehmen" ? wann : ""}` : "",
    };
  };
  const prim = zustand.buendel.filter((b) => b.primaer);
  return [...prim.slice(0, 1).map(leistung), ...zustand.termine.map(termin), ...prim.slice(1).map(leistung)]
    .filter(Boolean);
}
