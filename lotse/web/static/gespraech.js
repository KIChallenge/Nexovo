// Ansicht „Gespräch“: Verlauf, Rückfrage-Knöpfe, Themen-Kacheln, Beispiel-Dokumente und Box „Ihr nächster Schritt“.
import { $, domId, el } from "./dom.js";
import { aktion, aufgaben, t, zustand } from "./kern.js";
import { belege, textBloecke } from "./belege.js";
import { vorlesenMoeglich } from "./stimme.js";

const istScrollbereich = (e) => ["auto", "scroll"].includes(getComputedStyle(e).overflowY);

function sichtbarMachen(li) {
  const verlauf = $("#verlauf");
  if (verlauf.closest("[hidden]")) return;
  const lr = li.getBoundingClientRect();
  if (istScrollbereich(verlauf)) {
    // Breite Ansicht: nur im Verlauf scrollen; lange Antworten ab ihrem Anfang zeigen
    const vr = verlauf.getBoundingClientRect();
    verlauf.scrollTop += lr.height > vr.height ? lr.top - vr.top : lr.bottom - vr.bottom;
  } else {
    li.scrollIntoView({ block: lr.height > window.innerHeight * 0.6 ? "start" : "nearest" });
  }
}

/** Nachricht in den Verlauf schreiben; Quellen erscheinen nur bei „Belege anzeigen“. */
export function nachrichtAnzeigen(rolle, text, { quellen = [], grenze = false, laedt = false, zeigen = true } = {}) {
  const nr = ++zustand.nr;
  const praefix = quellen.length ? `q${nr}` : null;
  const klasse = ["nachricht", rolle, grenze ? "grenzfall" : "", laedt ? "laedt" : ""].join(" ").trim();
  const li = el("li", { class: klasse, id: `nachricht-${nr}` },
    el("p", { class: "wer" }, rolle === "nutzer" ? t("sie") : (grenze ? t("grenze_antwort") : t("lotse"))),
    el("div", { class: "blase", dir: "auto" }, rolle === "lotse" ? textBloecke(text, praefix) : text),
    rolle === "lotse" && !laedt ? belege(quellen, { id: `belege-${nr}`, praefix }) : null);
  $("#verlauf").append(li);
  if (rolle === "lotse" && zeigen) sichtbarMachen(li);
  return li;
}

/** Rückfrage-Knöpfe; solange eine Rückfrage offen ist, sind sie die Hauptaktion (sonst „Senden“). */
export function optionenAnzeigen(rueckfrage) {
  const box = $("#optionen");
  const knoepfe = $("#optionen-knoepfe");
  knoepfe.replaceChildren();
  const offen = Boolean(rueckfrage && rueckfrage.optionen && rueckfrage.optionen.length);
  if (offen) {
    $("#optionen-frage").textContent = rueckfrage.frage || t("antwortmoeglichkeiten");
    rueckfrage.optionen.forEach((o, i) => knoepfe.append(el("button", {
      type: "button", class: "knopf option", id: `option-${i}`, onclick: () => aktion.senden(o.wert, o.label),
    }, o.label)));
  }
  box.hidden = !offen;
  knoepfe.classList.toggle("hauptaktion", offen);
  $("#senden").classList.toggle("hauptaktion", !offen);
}

const demoTitel = (d) =>
  (d.text_key && zustand.T[d.text_key]) || d.titel[zustand.sprache] || d.titel.en || d.name;

export function demoAnzeigen() {
  $("#demo-knoepfe").replaceChildren(...zustand.demo.map((d) => {
    const gesperrt = Boolean(d.nur_ki) && !zustand.ki;  // Foto-Abschrift braucht den KI-Modus
    return el("button", {
      type: "button", class: "knopf", id: domId("demo", d.name), disabled: gesperrt,
      onclick: () => aktion.demoLaden(d, demoTitel(d)),
    }, demoTitel(d), gesperrt ? ` – ${t("nur_ki")}` : null);
  }));
  $("#demo").hidden = zustand.demo.length === 0;
}

/** Leerzustand: nur Themen-Kacheln und Eingabe; danach Verlauf, ein Vorlesen-Knopf und die Box mit dem nächsten Schritt. */
export function gespraechAnzeigen() {
  $("#start").hidden = zustand.begonnen;
  $("#verlauf-log").hidden = !zustand.begonnen;
  $("#vorlesen-zeile").hidden = !(zustand.begonnen && vorlesenMoeglich && zustand.letzteAntwort);

  const liste = aufgaben().slice(0, 3);
  const box = $("#naechster-box");
  box.hidden = liste.length === 0;
  if (!liste.length) return;
  const [erste, ...rest] = liste;
  // replaceChildren würde null als Text „null“ einfügen – daher leere Teile herausfiltern
  $("#naechster-box-inhalt").replaceChildren(...[
    el("p", { class: "naechster-titel" }, erste.titel),
    el("p", { class: "naechster-text" }, erste.text || t("alles_erledigt_kurz")),
    // Weitere Aufgaben nur als Titel (Link); ihr Schritttext steht im Plan bzw. in der Leistung
    rest.length ? el("ul", { class: "aufgaben-kurz" }, rest.map((a) =>
      el("li", {}, el("a", { href: a.href, class: "ziel-link" }, a.titel)))) : null,
  ].filter(Boolean));
}
