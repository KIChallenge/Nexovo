// Ansicht „Termin“ (#/termin/<id>, Unteransicht von „Mein Plan“): alle Terminfunktionen. Hauptaktion: „Text kopieren“,
// nach der Vereinbarung „In Kalender eintragen (.ics)“.
import { $, el, link, sichereUrl, symbol, vonIso, zuIso } from "./dom.js";
import { aktion, t, zustand } from "./kern.js";
import { belegeBereich } from "./belege.js";
import { schritteListe } from "./leistung.js";

async function kopieren(text, feld, meldung) {
  let ok = false;
  try {
    await navigator.clipboard.writeText(text);
    ok = true;
  } catch (_) {
    feld.focus();
    feld.select();
    try { ok = document.execCommand("copy"); } catch (__) { ok = false; }
  }
  meldung.textContent = t(ok ? "kopiert" : "kopieren_fehler");
  window.setTimeout(() => { meldung.textContent = ""; }, 4000);
}

function abschnitt(titel, ...inhalt) {
  return el("section", { class: "abschnitt abschnitt-h2" }, el("h2", {}, titel), ...inhalt);
}

export function terminAnzeigen(terminId) {
  const h1 = $("#h-termin");
  const box = $("#termin-inhalt");
  const tm = zustand.termine.find((x) => x.id === terminId);
  if (!tm) {
    h1.textContent = t("leistung_fehlt");
    box.replaceChildren(el("p", {}, el("a", { href: "#/plan", class: "knopf hauptaktion" }, t("zurueck_plan"))));
    return;
  }
  const id = tm.id;
  const fa = zustand.fallakte || { eintraege: [] };
  const eintrag = fa.eintraege.find((e) => e.termin_id === id);
  h1.textContent = `${t("termin_titel")}: ${tm.anlass_label}`;
  const aktiv = tm.status !== "erledigt";  // erledigte Termine kompakt: Eckdaten, Kalender, Schritte, Belege
  const ics = sichereUrl(tm.ics_url);
  const kopierenHaupt = aktiv && tm.anfrage_text && !ics;

  const fakten = [
    tm.ort ? [t("termin_ort"), tm.ort] : null,
    tm.zeit ? [t("termin_zeit"), tm.zeit] : null,
    tm.datum ? [t("datum"), tm.datum] : null,
    tm.uhrzeit ? [t("uhrzeit"), tm.uhrzeit] : null,
  ].filter(Boolean);
  const teile = [
    fakten.length ? el("dl", { class: "fakten" }, fakten.map(([k, v]) => el("div", {}, el("dt", {}, k), el("dd", {}, v)))) : null,
  ];

  if (ics) {
    teile.push(el("p", {}, el("a", { class: "knopf hauptaktion", href: ics, download: true, id: `ics-${id}` },
      symbol("herunterladen"), t("ics_laden"))));
  }

  if (aktiv && tm.anfrage_text) {
    const feldId = `anfrage-${id}`;
    const feld = el("textarea", { id: feldId, class: "anfrage", readonly: true, rows: 3, dir: "auto" }, tm.anfrage_text);
    const meldung = el("span", { class: "kopier-meldung", role: "status" });
    teile.push(el("div", { class: "anfrage-block" },
      el("label", { for: feldId, class: "feld-label" }, t("termin_anfrage")),
      feld,
      el("p", { class: "knopf-zeile" },
        el("button", {
          type: "button", id: `kopieren-${id}`, class: kopierenHaupt ? "knopf hauptaktion" : "knopf",
          onclick: () => kopieren(tm.anfrage_text, feld, meldung),
        }, t("kopieren")),
        meldung)));
  }

  if (aktiv && tm.wo) teile.push(abschnitt(t("termin_wo"), el("p", {}, tm.wo)));
  const hinweise = aktiv ? tm.hinweise || [] : [];
  if (hinweise.length) {
    // Bei Beschwerden steht der 1450-Hinweis an erster Stelle und wird hervorgehoben.
    const beschwerden = tm.anlass === "beschwerden";
    teile.push(abschnitt(t("termin_hinweise"), el("ul", { class: "termin-hinweise" }, hinweise.map((h, i) =>
      el("li", { class: beschwerden && i === 0 ? "hinweis-1450" : null }, h)))));
  }
  const suche = aktiv ? (tm.suche || []).filter((s) => sichereUrl(s.url)) : [];
  if (suche.length) {
    teile.push(abschnitt(t("termin_suche"), el("ul", { class: "termin-suche" }, suche.map((s) =>
      el("li", {}, link(s.url, s.name),
        s.beleg === "extern" ? el("span", { class: "nur-mit-belegen" }, " ",
          el("span", { class: "badge badge-extern" }, t("extern_badge"))) : null)))));
  }

  if (aktiv) {
    const datumId = `datum-${id}`;
    const zeitId = `uhrzeit-${id}`;
    const datumFeld = el("input", { type: "date", id: datumId, value: zuIso(tm.datum), required: true });
    const zeitFeld = el("input", { type: "time", id: zeitId, value: tm.uhrzeit || "" });
    const form = el("form", { class: "termin-form" },
      el("fieldset", {},
        el("legend", {}, t("termin_eintragen")),
        el("div", { class: "termin-felder" },
          el("div", {}, el("label", { for: datumId, class: "feld-label" }, t("datum")), datumFeld),
          el("div", {}, el("label", { for: zeitId, class: "feld-label" }, t("uhrzeit")), zeitFeld),
          el("button", { type: "submit", class: "knopf", id: `speichern-${id}` }, t("termin_speichern")))));
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const datum = vonIso(datumFeld.value);
      if (!datum) return;  // Pflichtfeld prüft der Browser
      const daten = { datum, status: "vereinbart" };
      if (zeitFeld.value) daten.uhrzeit = zeitFeld.value;
      aktion.terminAendern(id, daten);
    });
    teile.push(form);
  }
  if (tm.status === "vereinbart") {
    teile.push(el("p", {}, el("button", {
      type: "button", class: "knopf", id: `erledigt-${id}`, onclick: () => aktion.terminAendern(id, { status: "erledigt" }),
    }, t("termin_als_erledigt"))));
  }
  teile.push(el("p", { class: "leise" }, t("termin_kein_buchen")));
  if (!ics && !kopierenHaupt) {
    teile.push(el("p", {}, el("a", { href: "#/plan", class: "knopf hauptaktion" }, t("zurueck_plan"))));
  }
  if (eintrag && eintrag.schritte.length) {
    teile.push(el("details", { class: "bereich", id: `termin-${id}-schritte` },
      el("summary", {}, `${t("so_gehen_sie_vor")} (${eintrag.erledigt}/${eintrag.gesamt})`),
      schritteListe(eintrag, `t-${id}`)));
  }
  teile.push(belegeBereich(tm.quellen, `termin-${id}-belege`));
  box.replaceChildren(...teile.filter(Boolean));
  box.querySelectorAll("textarea.anfrage").forEach((f) => {
    f.style.height = "auto";
    f.style.height = `${f.scrollHeight + 4}px`;
  });
}
