// Ansicht „Leistung“: sichtbar nur das Nötige (Kurztext, zuständige Stelle, Hauptaktion, Unterlagen beim Antrag);
// alles Weitere in „Mehr zu dieser Leistung“, Quellen in „Belege (N)“. Dazu Bausteine, die auch Termin und Plan nutzen.
import { $, domId, el, link, sichereUrl, symbol } from "./dom.js";
import { aktion, eintraegeNachLeistung, schrittVon, statusText, t, tf, zustand } from "./kern.js";
import { belege, belegeBereich } from "./belege.js";

const STATUS = ["offen", "in_arbeit", "erledigt"];

function abschnitt(id, titel, ebene, ...inhalt) {
  const hid = `${id}-titel`;
  return el("section", { class: `abschnitt abschnitt-${ebene}`, id, "aria-labelledby": hid },
    el(ebene, { id: hid, tabindex: "-1" }, titel), ...inhalt);
}

/** Schritte mit Status als Segment-Steuerung (Offen / In Arbeit / Erledigt, je Schritt eine Radiogruppe). */
export function schritteListe(eintrag, praefix) {
  return el("ol", { class: "schritte" }, eintrag.schritte.map((s) => {
    const naechster = s.id === eintrag.naechster_schritt;
    const name = domId(`${praefix}-s`, s.id);
    return el("li", {
      class: `schritt status-${s.status}${naechster ? " ist-naechster" : ""}`,
      "aria-current": naechster ? "step" : null,
    },
      el("fieldset", { class: "segment" },
        el("legend", {}, el("span", { class: "schritt-text" }, s.text)),
        el("div", { class: "segment-optionen" }, STATUS.map((v) => {
          const id = `${name}-${v}`;
          return el("label", { class: "segment-option", for: id },
            el("input", {
              type: "radio", name, id, value: v, checked: v === s.status,
              onchange: (ev) => { if (ev.target.checked) aktion.statusSetzen(s.id, v); },
            }),
            el("span", {}, statusText(v)));
        }))));
  }));
}

/**
 * Unterlagen als Checkliste: „Immer nötig“ sichtbar, bedingte (`bedingt`) unter „Nur wenn es auf Sie zutrifft (N)“ –
 * eingeklappt, außer innerhalb eines anderen Aufklappers (`eingeklappt: false`, keine verschachtelten Aufklapper).
 * Unterlagen zum regionalen Formular stehen wie bisher gesammelt unter ihrem Hinweis.
 */
export function unterlagenListe(b, praefix, { eingeklappt = true } = {}) {
  const eintragLi = (u) => {
    const cid = domId(`${praefix}-u`, u.id);
    return el("li", {},
      el("label", { class: "check-zeile", for: cid },
        el("input", {
          type: "checkbox", id: cid, checked: u.status === "erledigt",
          onchange: (ev) => aktion.statusSetzen(u.id, ev.target.checked ? "erledigt" : "offen"),
        }),
        el("span", {}, u.text)),
      u.quelle ? belege([u.quelle], { id: `${cid}-belege` }) : null);
  };
  const liste = (us) => el("ul", { class: "checkliste" }, us.map(eintragLi));
  const ohneRegion = b.unterlagen.filter((u) => !u.region_hinweis);
  const immer = ohneRegion.filter((u) => !u.bedingt);
  const bedingt = ohneRegion.filter((u) => u.bedingt);
  const gruppen = new Map();
  for (const u of b.unterlagen.filter((x) => x.region_hinweis)) {
    if (!gruppen.has(u.region_hinweis)) gruppen.set(u.region_hinweis, []);
    gruppen.get(u.region_hinweis).push(u);
  }
  const bedingtTitel = tf("unterlagen_bedingt", { n: bedingt.length });
  return [
    immer.length ? [el("p", { class: "unterlagen-titel" }, t("unterlagen_immer")), liste(immer)] : null,
    [...gruppen].map(([hinweis, us]) => el("div", { class: "unterlagen-region" },
      el("p", { class: "hinweis-text" }, hinweis), liste(us))),
    !bedingt.length ? null : eingeklappt
      ? el("details", { class: "bereich", id: `${praefix}-bedingt` }, el("summary", {}, bedingtTitel), liste(bedingt))
      : [el("p", { class: "unterlagen-titel" }, bedingtTitel), liste(bedingt)],
  ];
}

/** Hauptaktion: Antrag herunterladen, sonst Termin vorbereiten, sonst nächsten Schritt als erledigt markieren. */
function hauptaktion(b, ns, p) {
  const f = b.formular;
  const url = f && sichereUrl(f.url);
  if (url) {
    return [
      f.region_hinweis ? el("p", { class: "hinweis-text" }, f.region_hinweis) : null,
      el("p", {}, el("a", {
        class: "knopf hauptaktion", href: url, download: `${f.id}_Entwurf.pdf`, id: `${p}-pdf`,
        onclick: () => window.setTimeout(aktion.akteNeuLaden, 1500),
      }, symbol("herunterladen"), t("antrag_herunterladen"))),
      el("p", { class: "leise" }, t("unterschrift_hinweis")),
    ];
  }
  if (b.termin_anlass) {
    return el("p", {}, el("button", {
      type: "button", class: "knopf hauptaktion", id: `${p}-termin`,
      onclick: () => aktion.terminStarten(b.termin_anlass, b.leistung_id, `${t("termin_vorbereiten")}: ${b.titel}`),
    }, t("termin_vorbereiten")));
  }
  if (ns) {
    return [
      el("p", { id: `${p}-naechster` }, el("strong", {}, `${t("naechster")}: `), ns.text),
      el("p", {}, el("button", {
        type: "button", class: "knopf hauptaktion", id: `${p}-erledigt`, "aria-describedby": `${p}-naechster`,
        onclick: () => aktion.statusSetzen(ns.id, "erledigt"),
      }, symbol("haken"), t("termin_als_erledigt"))),
    ];
  }
  return [
    el("p", {}, t("alles_erledigt_kurz")),
    el("p", {}, el("a", { href: "#/plan", class: "knopf hauptaktion" }, t("zurueck_plan"))),
  ];
}

function regionalBlock(b) {
  const r = b.regional;
  if (!r) return null;
  return abschnitt(`l-${b.leistung_id}-regional`, `${t("regional_titel")}: ${r.bundesland}`, "h3",
    el("p", { class: "stelle-name" }, r.stelle),
    r.kontakt ? el("p", {}, r.kontakt) : null,
    r.url ? el("p", {}, link(r.url)) : null,
    belege([r.quelle], { id: `l-${b.leistung_id}-regional-belege`, extern: r.beleg === "extern" }));
}

function formularDetails(b) {
  const f = b.formular;
  if (!f) return null;
  const fehlend = f.fehlende_angaben || b.fehlende_angaben || [];
  return abschnitt("abschnitt-formular", t("formular"), "h3",
    el("p", { class: "stelle-name" }, f.titel),
    f.vorauswahl ? el("p", {}, f.vorauswahl) : null,
    f.stelle ? el("p", {}, f.stelle) : null,
    f.adresse ? el("p", {}, f.adresse) : null,
    fehlend.length ? [
      el("p", { class: "fehlend-titel" }, t("fehlend")),
      el("ul", { class: "fehlend" }, fehlend.map((x) => el("li", {}, x.label))),
      el("p", {}, el("a", {
        href: "#/akte", class: "knopf", onclick: () => { zustand.fokusZiel = "fehlende-titel"; },
      }, t("in_akte_ergaenzen"))),
    ] : null,
    f.hinweis ? el("p", { class: "leise" }, f.hinweis) : null,
    f.ohne_unterlagen ? el("p", { class: "leise" }, f.ohne_unterlagen) : null);
}

function mehrBereich(b, eintrag, p) {
  const teile = [
    b.regionen_anzeige && b.regionen_anzeige.length
      ? el("p", { class: "hinweis-text" }, `${t("region")}: ${b.regionen_anzeige.join(", ")}`) : null,
    b.details ? el("p", {}, b.details) : null,
    b.voraussetzungen && b.voraussetzungen.length
      ? abschnitt("abschnitt-voraussetzungen", t("voraussetzungen"), "h3",
        el("ul", {}, b.voraussetzungen.map((v) => el("li", {}, v)))) : null,
    b.nutzen ? abschnitt("abschnitt-nutzen", t("nutzen_titel"), "h3",
      el("p", {}, b.nutzen), belege([b.nutzen_quelle], { id: `${p}-nutzen-belege` })) : null,
    b.stelle.hinweis ? el("p", {}, b.stelle.hinweis) : null,
    regionalBlock(b),
    eintrag && eintrag.schritte.length ? abschnitt("abschnitt-schritte", t("so_gehen_sie_vor"), "h3",
      el("p", { class: "leise" }, `${t("schritte")}: ${eintrag.erledigt}/${eintrag.gesamt} ${statusText("erledigt")}`),
      schritteListe(eintrag, p),
      // Beim Antrag ist der Download die Hauptaktion; der Termin bleibt hier erreichbar
      b.formular && b.termin_anlass ? el("p", {}, el("button", {
        type: "button", class: "knopf", id: `${p}-termin`,
        onclick: () => aktion.terminStarten(b.termin_anlass, b.leistung_id, `${t("termin_vorbereiten")}: ${b.titel}`),
      }, t("termin_vorbereiten"))) : null) : null,
    formularDetails(b),
    !b.formular && b.unterlagen && b.unterlagen.length
      ? abschnitt("abschnitt-unterlagen", t("unterlagen"), "h3", unterlagenListe(b, p, { eingeklappt: false })) : null,
    b.einrichtungen && b.einrichtungen.length ? abschnitt("abschnitt-einrichtungen", t("einrichtungen_titel"), "h3",
      el("ul", { class: "einrichtungen" }, b.einrichtungen.map((e, i) => el("li", {},
        el("p", {},
          el("span", { class: "stelle-name" }, e.name), " ",
          el("span", { class: "leise" }, e.regionen && e.regionen.length ? e.regionen.join(", ") : t("oesterreichweit"))),
        e.kontakt ? el("p", {}, e.kontakt) : null,
        e.url ? el("p", {}, link(e.url)) : null,
        belege([e.quelle], { id: `${p}-e${i}-belege`, extern: e.beleg === "extern" }))))) : null,
    b.dokument && b.dokument.length ? abschnitt("abschnitt-dokument", t("dokument_zitat"), "h3",
      b.dokument.map((d, i) => el("div", { class: "dok-zitat" },
        el("p", { class: "zitat", dir: "auto" }, d.text),
        belege([d.quelle], { id: `${p}-d${i}-belege` })))) : null,
  ].flat().filter(Boolean);
  return el("details", { class: "bereich", id: `${p}-mehr` }, el("summary", {}, t("mehr_zur_leistung")), teile);
}

export function leistungAnzeigen(id) {
  const h1 = $("#h-leistung");
  const box = $("#leistung-inhalt");
  const b = zustand.buendel.find((x) => x.leistung_id === id);
  if (!b) {
    h1.textContent = t("leistung_fehlt");
    box.replaceChildren(el("p", {}, el("a", { href: "#/plan", class: "knopf hauptaktion" }, t("zurueck_plan"))));
    return;
  }
  h1.textContent = b.titel;
  const eintrag = eintraegeNachLeistung()[b.leistung_id];
  const ns = schrittVon(eintrag, b.naechster_schritt);
  const p = `l-${b.leistung_id}`;
  const st = b.stelle;
  box.replaceChildren(...[
    el("p", { class: "kurz" }, b.kurz),
    abschnitt("abschnitt-stelle", t("zustaendig"), "h2",
      el("p", { class: "stelle-name" }, st.name),
      st.kontakt ? el("p", {}, st.kontakt) : null,
      st.abhaengig_von ? el("p", { class: "hinweis-text" }, `${t("zustaendig_offen")}: ${st.abhaengig_von.label}`) : null,
      st.quelle ? belege([st.quelle], { id: `${p}-stelle-belege`, extern: st.beleg === "extern" }) : null),
    el("div", { class: "haupt-block" }, hauptaktion(b, ns, p)),
    b.formular && b.unterlagen && b.unterlagen.length
      ? abschnitt("abschnitt-unterlagen", t("unterlagen"), "h2", unterlagenListe(b, p)) : null,
    mehrBereich(b, eintrag, p),
    belegeBereich(b.quellen, `${p}-belege`),
  ].filter(Boolean));
}
