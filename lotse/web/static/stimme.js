// Vorlesen (Web Speech Synthesis) und Spracheingabe (Web Speech Recognition, nur wo vorhanden).
import { $ } from "./dom.js";
import { SPRACH_TAG, einst, t, zustand } from "./kern.js";

export const vorlesenMoeglich = "speechSynthesis" in window;
const TEMPO = { langsam: 0.8, normal: 1, schnell: 1.25 };
let laufend = null;  // { knopf }

// Lange Texte in Abschnitte teilen: manche Stimmen brechen sehr lange Äußerungen sonst ab.
function abschnitte(text) {
  const teile = [];
  for (const absatz of text.split(/\n+/)) {
    let rest = absatz.trim();
    while (rest.length > 220) {
      const cut = Math.max(rest.lastIndexOf(". ", 220), rest.lastIndexOf("? ", 220), rest.lastIndexOf("; ", 220));
      const pos = cut > 40 ? cut + 1 : (rest.lastIndexOf(" ", 220) > 40 ? rest.lastIndexOf(" ", 220) : 220);
      teile.push(rest.slice(0, pos).trim());
      rest = rest.slice(pos).trim();
    }
    if (rest) teile.push(rest);
  }
  return teile;
}

export function vorlesenBeschriften(knopf) {
  const an = knopf.getAttribute("aria-pressed") === "true";
  const ziel = knopf.querySelector(".knopf-text") || knopf;
  ziel.textContent = t(an ? "vorlesen_stop" : (knopf.dataset.label || "vorlesen"));
}

export function vorlesenBeenden() {
  if (!vorlesenMoeglich) return;
  const vorher = laufend;
  laufend = null;
  window.speechSynthesis.cancel();
  if (vorher && vorher.knopf.isConnected) {
    vorher.knopf.setAttribute("aria-pressed", "false");
    vorlesenBeschriften(vorher.knopf);
  }
}

/** Liest `text` in der Sitzungssprache und im gewählten Tempo; ein zweiter Klick auf denselben Knopf stoppt. */
export function vorlesen(knopf, text) {
  if (!vorlesenMoeglich) return;
  const lief = laufend && laufend.knopf === knopf;
  vorlesenBeenden();
  if (lief) return;
  const sauber = text.replace(/\[\d+\]/g, "").replace(/[ \t]+/g, " ");
  const teile = abschnitte(sauber);
  if (!teile.length) return;
  const lauf = { knopf };
  laufend = lauf;
  knopf.setAttribute("aria-pressed", "true");
  vorlesenBeschriften(knopf);
  const ende = () => { if (laufend === lauf) vorlesenBeenden(); };
  teile.forEach((teil, i) => {
    const u = new SpeechSynthesisUtterance(teil);
    u.lang = SPRACH_TAG[zustand.sprache] || zustand.sprache;
    u.rate = TEMPO[einst.tempo] || 1;
    if (i === teile.length - 1) u.addEventListener("end", ende);
    u.addEventListener("error", ende);
    window.speechSynthesis.speak(u);
  });
}

// ---- Spracheingabe ---------------------------------------------------------

const mikro = { erkennung: null, fehler: false };

export function mikroStatus(an = Boolean(mikro.erkennung)) {
  const knopf = $("#mikro");
  knopf.setAttribute("aria-pressed", String(an));
  knopf.classList.toggle("aktiv", an);
  $("#mikro-text").textContent = t(an ? "mikro_stop" : "mikro_start");
  knopf.title = t(an ? "mikro_stop" : "mikro_start");
  if (an) $("#mikro-status").textContent = t("mikro_aktiv");
  else if (!mikro.fehler) $("#mikro-status").textContent = "";
}

export function mikroEinrichten() {
  const Erkennung = window.SpeechRecognition || window.webkitSpeechRecognition;
  const knopf = $("#mikro");
  knopf.hidden = !Erkennung;
  if (!Erkennung) return;
  knopf.addEventListener("click", () => {
    if (mikro.erkennung) { mikro.erkennung.stop(); return; }
    const feld = $("#eingabe");
    const basis = feld.value.trim() ? `${feld.value.trimEnd()} ` : "";
    const e = new Erkennung();
    e.lang = SPRACH_TAG[zustand.sprache] || zustand.sprache;
    e.interimResults = true;
    e.continuous = false;
    e.addEventListener("result", (ev) => {
      let text = "";
      for (const r of ev.results) text += r[0].transcript;
      feld.value = basis + text;
    });
    e.addEventListener("error", () => {
      mikro.fehler = true;
      $("#mikro-status").textContent = t("mikro_fehler");
    });
    e.addEventListener("end", () => {
      mikro.erkennung = null;
      mikroStatus(false);
      feld.focus();
    });
    mikro.fehler = false;
    try {
      e.start();
      mikro.erkennung = e;
      mikroStatus(true);
    } catch (_) {
      mikro.fehler = true;
      $("#mikro-status").textContent = t("mikro_fehler");
    }
  });
}
