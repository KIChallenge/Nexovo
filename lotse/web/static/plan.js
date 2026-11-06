// Ansicht „Mein Plan“: ein nächster Schritt mit der Hauptaktion, höchstens zwei weitere Aufgaben, eine
// Fortschrittszeile und „Weitere Möglichkeiten“ (eingeklappt). Dazu die Druckfassung und der Text zum Vorlesen.
import { $, domId, el, symbol } from "./dom.js";
import { aktion, aufgaben, leistungHref, statusText, t, terminHref, tf, zustand } from "./kern.js";

const SICHTBAR = 3;  // nächster Schritt + höchstens 2 weitere Aufgaben

function fortschritt() {
  const u = zustand.uebersicht;
  const gesamt = u ? u.erledigt + u.offen : 0;
  if (!gesamt) return null;
  return el("div", { class: "fortschritt" },
    el("progress", { value: u.erledigt, max: gesamt, "aria-labelledby": "fortschritt-text" }),
    el("p", { id: "fortschritt-text" }, tf("fortschritt", { erledigt: u.erledigt, gesamt })));
}

/** Umschalter „Erledigt“ für den gezeigten Schritt; bleibt nach dem Abhaken rückgängig machbar. */
function erledigtKnopf(a, textId, haupt) {
  return el("button", {
    type: "button", class: haupt ? "knopf hauptaktion umschalter" : "knopf umschalter", id: `${domId("plan", a.id)}-erledigt`,
    "aria-pressed": String(Boolean(a.abgehakt)), "aria-describedby": textId,
    onclick: () => {
      if (a.abgehakt) {
        const gemerkt = zustand.planErledigt.get(a.id);
        zustand.planErledigt.delete(a.id);
        aktion.statusSetzen(a.abgehakt.id, gemerkt && gemerkt.vorher !== "erledigt" ? gemerkt.vorher : "offen");
      } else {
        zustand.planErledigt.set(a.id, { id: a.schritt.id, vorher: a.schritt.status });
        aktion.statusSetzen(a.schritt.id, "erledigt");
      }
    },
  }, symbol("kasten"), symbol("kasten-haken"), t("erledigt_knopf"));
}

function naechsterSchritt(a) {
  const p = domId("plan", a.id);
  const textId = `${p}-text`;
  let haupt = null;
  if (a.art === "termin") {
    haupt = el("button", { type: "button", class: "knopf hauptaktion", id: `${p}-aktion`,
      onclick: () => aktion.navigieren(a.href) }, t("termin_oeffnen"));
  } else if (a.b.formular) {
    haupt = el("button", { type: "button", class: "knopf hauptaktion", id: `${p}-aktion`,
      onclick: () => aktion.navigieren(a.href, `l-${a.id}-pdf`) }, t("antrag_vorbereiten"));
  } else if (a.b.termin_anlass) {
    haupt = el("button", { type: "button", class: "knopf hauptaktion", id: `${p}-aktion`,
      onclick: () => aktion.terminStarten(a.b.termin_anlass, a.id, `${t("termin_vorbereiten")}: ${a.titel}`) },
    t("termin_vorbereiten"));
  }
  const kannAbhaken = a.schritt || a.abgehakt;
  return el("section", { class: "naechster-karte", id: "plan-naechster", "aria-labelledby": "plan-naechster-titel" },
    el("h2", { id: "plan-naechster-titel", tabindex: "-1" }, t("naechster_schritt_titel")),
    el("p", { class: "naechster-titel" }, a.titel),
    el("p", { id: textId, class: a.abgehakt ? "naechster-text ist-erledigt" : "naechster-text" },
      a.abgehakt ? tf("schritt_erledigt", { text: a.abgehakt.text }) : a.text),
    a.abgehakt && a.schritt ? el("p", {}, `${t("danach")}: ${a.text}`) : null,
    el("div", { class: "knopf-zeile" },
      haupt || (kannAbhaken ? erledigtKnopf(a, textId, true) : null),
      haupt && kannAbhaken ? erledigtKnopf(a, textId, false) : null,
      a.art === "leistung" && !a.b.formular
        ? el("a", { href: a.href, class: "knopf" }, t("ansehen"), el("span", { class: "sr-only" }, ` ${a.titel}`)) : null));
}

function weitereAufgaben(liste) {
  if (!liste.length) return null;
  return el("ul", { class: "aufgaben" }, liste.map((a) => el("li", { class: "aufgabe" },
    el("p", {}, el("strong", {}, a.titel), el("br"), a.text),
    el("a", { href: a.href, class: "knopf" }, t("ansehen"), el("span", { class: "sr-only" }, ` ${a.titel}`)))));
}

/** Alles, was nicht als Aufgabe oben steht: übrige Leistungen und Termine (eingeklappt). */
function weitereMoeglichkeiten(sichtbar) {
  const oben = new Set(sichtbar.map((a) => `${a.art}:${a.id}`));
  const links = [
    ...zustand.buendel.filter((b) => !oben.has(`leistung:${b.leistung_id}`))
      .map((b) => [leistungHref(b.leistung_id), b.titel]),
    ...zustand.termine.filter((tm) => !oben.has(`termin:${tm.id}`))
      .map((tm) => [terminHref(tm.id), `${t("termin_titel")}: ${tm.anlass_label}`]),
  ];
  if (!links.length) return null;
  return el("details", { class: "bereich", id: "plan-weitere" },
    el("summary", {}, tf("weitere_moeglichkeiten", { n: links.length })),
    el("ul", { class: "link-liste" }, links.map(([href, titel]) => el("li", {},
      el("a", { href, class: "link-zeile" }, el("span", {}, titel), symbol("weiter"))))));
}

// ---- Druckfassung: alle Aufgaben mit Stelle, Kontakt, Unterlagen; alle Leistungen mit Quellen ----------

function quellenKompakt(quellen) {
  const liste = [...new Set((quellen || []).map((q) => [q.titel, q.fundstelle].filter(Boolean).join(", ")))];
  return liste.length ? el("p", { class: "druck-quellen" }, `${t("quellen")}: ${liste.join("; ")}`) : null;
}

function druckAufgabe(a) {
  const zeile = (titel, ...wert) => el("p", {}, el("strong", {}, `${titel}: `), ...wert);
  const teile = [el("h3", {}, a.titel), a.text ? zeile(t("naechster"), a.text) : null];
  if (a.art === "leistung") {
    const b = a.b;
    teile.push(
      zeile(t("zustaendig"), b.stelle.name, b.stelle.kontakt ? ` – ${b.stelle.kontakt}` : null),
      b.regional ? zeile(`${t("regional_titel")} (${b.regional.bundesland})`, b.regional.stelle,
        b.regional.kontakt ? ` – ${b.regional.kontakt}` : null) : null,
      b.formular ? zeile(t("formular"), b.formular.titel, b.formular.adresse ? ` – ${b.formular.adresse}` : null) : null,
      b.unterlagen && b.unterlagen.length ? [
        el("p", {}, el("strong", {}, t("unterlagen"))),
        el("ul", { class: "druck-checkliste" }, b.unterlagen.map((u) =>
          el("li", { class: u.status === "erledigt" ? "erledigt" : null }, u.text))),
      ] : null);
  } else {
    const tm = a.tm;
    teile.push(
      tm.ort ? zeile(t("termin_ort"), tm.ort) : null,
      tm.zeit ? zeile(t("termin_zeit"), tm.zeit) : null,
      tm.datum ? zeile(t("datum"), tm.datum, tm.uhrzeit ? `, ${tm.uhrzeit}` : null) : null,
      tm.wo ? zeile(t("termin_wo"), tm.wo) : null,
      tm.anfrage_text ? zeile(t("termin_anfrage"), tm.anfrage_text) : null,
      quellenKompakt(tm.quellen));
  }
  return el("li", { class: "druck-aufgabe" }, teile);
}

function druckfassung(alle) {
  if (!alle.length && !zustand.buendel.length) return null;
  return el("div", { class: "nur-druck" },
    alle.length ? [el("h2", {}, t("naechster_schritt_titel")), el("ol", { class: "druck-aufgaben" }, alle.map(druckAufgabe))] : null,
    zustand.buendel.length ? [
      el("h2", {}, t("leistungen_liste")),
      el("ol", {}, zustand.buendel.map((b) => el("li", {},
        el("strong", {}, b.titel), ` – ${t("zustaendig")}: ${b.stelle.name}`, quellenKompakt(b.quellen)))),
    ] : null);
}

export function planAnzeigen() {
  const alle = aufgaben();
  const sichtbar = alle.slice(0, SICHTBAR);
  const leer = !alle.length && !zustand.buendel.length && !zustand.termine.length;
  const teile = leer
    ? [el("div", { class: "leer" },
      el("p", {}, t("plan_leer")),
      el("p", {}, el("a", { href: "#/gespraech", class: "knopf hauptaktion" }, t("zum_gespraech"))))]
    : [
      sichtbar.length ? naechsterSchritt(sichtbar[0]) : el("p", { class: "naechster-karte" }, t("alles_erledigt_kurz")),
      weitereAufgaben(sichtbar.slice(1)),
      fortschritt(),
      weitereMoeglichkeiten(sichtbar),
      druckfassung(alle),
    ];
  $("#plan-inhalt").replaceChildren(...teile.filter(Boolean));
}

/** Text für „Plan vorlesen“. */
export function planText() {
  const teile = [`${t("plan_titel")}.`];
  const alle = aufgaben();
  if (alle.length) {
    teile.push(`${t("naechster_schritt_titel")}: ${alle[0].titel}: ${alle[0].text || t("alles_erledigt_kurz")}`);
    alle.slice(1, SICHTBAR).forEach((a) => teile.push(`${a.titel}: ${a.text}`));
  }
  const u = zustand.uebersicht;
  if (u && u.erledigt + u.offen) teile.push(`${tf("fortschritt", { erledigt: u.erledigt, gesamt: u.erledigt + u.offen })}.`);
  if (teile.length === 1) teile.push(t("plan_leer"));
  return teile.join("\n");
}
