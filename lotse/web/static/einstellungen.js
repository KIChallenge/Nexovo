// Einstellungen: Dialog, Speicherung im localStorage und Anwendung auf die Seite (Textgröße, Farbschema, Belege).
import { $, el } from "./dom.js";
import { aktion, einst, t, zustand } from "./kern.js";
import { vorlesenMoeglich } from "./stimme.js";

const SCHLUESSEL = "lotse.einstellungen";
const ERLAUBT = {
  stil: ["einfach", "ausfuehrlich", "leicht"],
  groesse: ["100", "115", "130"],
  farbe: ["system", "hell", "dunkel", "kontrast"],
  tempo: ["langsam", "normal", "schnell"],
};

export function einstellungenLaden() {
  try {
    const d = JSON.parse(window.localStorage.getItem(SCHLUESSEL) || "{}");
    for (const [k, werte] of Object.entries(ERLAUBT)) if (werte.includes(d[k])) einst[k] = d[k];
    if (typeof d.sprache === "string" && /^[a-z]{2}$/.test(d.sprache)) einst.sprache = d.sprache;
    if (typeof d.belege === "boolean") einst.belege = d.belege;
  } catch (_) { /* keine oder beschädigte Einstellungen: Standard */ }
}

export function einstellungenSpeichern() {
  try {
    window.localStorage.setItem(SCHLUESSEL, JSON.stringify(einst));
  } catch (_) { /* Speicher gesperrt (z. B. privater Modus): gilt nur für diese Seite */ }
}

const dunkelMedien = window.matchMedia("(prefers-color-scheme: dark)");

export function darstellungAnwenden() {
  const html = document.documentElement;
  html.dataset.groesse = einst.groesse;
  html.dataset.farbe = einst.farbe === "system" ? (dunkelMedien.matches ? "dunkel" : "hell") : einst.farbe;
  html.dataset.belege = einst.belege ? "an" : "aus";
  dialogAbgleichen();
}

function radiosSetzen(name, wert) {
  document.querySelectorAll(`#einstellungen input[name="${name}"]`).forEach((r) => { r.checked = r.value === wert; });
}

// Sprachen: einmal anlegen, danach nur Verfügbarkeit und Hinweis aktualisieren (Fokus bleibt erhalten).
function sprachOptionen() {
  const box = $("#sprache-optionen");
  for (const s of zustand.sprachen) {
    let input = box.querySelector(`input[value="${s.code}"]`);
    if (!input) {
      input = el("input", { type: "radio", name: "sprache", value: s.code });
      input.addEventListener("change", () => { if (input.checked) aktion.einstellen({ sprache: s.code }); });
      box.append(el("label", { class: "wahl-option" }, input, el("span", {},
        el("span", { lang: s.code, dir: "auto" }, s.name), " ", el("span", { class: "wahl-zusatz" }))));
    }
    input.disabled = !s.verfuegbar;
    input.closest("label").classList.toggle("gesperrt", !s.verfuegbar);
    input.closest("label").querySelector(".wahl-zusatz").textContent = s.verfuegbar ? "" : `– ${t("nur_ki")}`;
  }
}

/** Dialog-Steuerelemente auf den aktuellen Stand bringen (z. B. nach einer abgelehnten Änderung). */
export function dialogAbgleichen() {
  sprachOptionen();
  radiosSetzen("sprache", zustand.sprache);
  radiosSetzen("stil", zustand.stil);
  radiosSetzen("groesse", einst.groesse);
  radiosSetzen("farbe", einst.farbe);
  radiosSetzen("tempo", einst.tempo);
  $("#belege-schalter").setAttribute("aria-checked", String(einst.belege));
  $("#wahl-tempo").hidden = !vorlesenMoeglich;
}

function tabbare(dlg) {
  const alle = [...dlg.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")]
    .filter((e) => !e.disabled && e.getClientRects().length > 0);
  // Je Radiogruppe ist nur das gewählte (sonst das erste) Feld per Tab erreichbar.
  return alle.filter((e) => {
    if (e.type !== "radio") return true;
    const gruppe = alle.filter((x) => x.type === "radio" && x.name === e.name);
    const gewaehlt = gruppe.find((x) => x.checked);
    return e === (gewaehlt || gruppe[0]);
  });
}

export function dialogEinrichten() {
  const dlg = $("#einstellungen");
  const oeffner = $("#einstellungen-knopf");
  oeffner.addEventListener("click", () => {
    dialogAbgleichen();
    dlg.showModal();
    $("#einst-schliessen").focus();
  });
  $("#einst-schliessen").addEventListener("click", () => dlg.close());
  dlg.addEventListener("close", () => oeffner.focus());
  // Fokus bleibt im Dialog (Tab am Ende → Anfang, Umschalt+Tab am Anfang → Ende).
  dlg.addEventListener("keydown", (ev) => {
    if (ev.key !== "Tab") return;
    const liste = tabbare(dlg);
    if (!liste.length) return;
    const erstes = liste[0];
    const letztes = liste[liste.length - 1];
    if (ev.shiftKey && document.activeElement === erstes) {
      ev.preventDefault();
      letztes.focus();
    } else if (!ev.shiftKey && document.activeElement === letztes) {
      ev.preventDefault();
      erstes.focus();
    }
  });

  const lokal = (name, feld) => document.querySelectorAll(`#einstellungen input[name="${name}"]`).forEach((r) =>
    r.addEventListener("change", () => {
      if (!r.checked) return;
      einst[feld] = r.value;
      einstellungenSpeichern();
      darstellungAnwenden();
    }));
  lokal("groesse", "groesse");
  lokal("farbe", "farbe");
  lokal("tempo", "tempo");
  document.querySelectorAll('#einstellungen input[name="stil"]').forEach((r) =>
    r.addEventListener("change", () => { if (r.checked) aktion.einstellen({ stil: r.value }); }));
  $("#belege-schalter").addEventListener("click", () => aktion.belegeSetzen(!einst.belege));
  dunkelMedien.addEventListener("change", () => { if (einst.farbe === "system") darstellungAnwenden(); });
}
