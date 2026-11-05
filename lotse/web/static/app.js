"use strict";
// SV KI-Lotse – Oberfläche ohne Build-Schritt. Alle Daten werden per textContent eingefügt (kein innerHTML).
(() => {
  const zustand = {
    sitzung: null, sprache: "de", stil: "einfach",
    alleT: null, T: {}, buendel: [], fallakte: null, angaben: [], demo: [], nr: 0, beschaeftigt: false,
    offen: new Map(),  // Leistungs-ID → Karte aufgeklappt?
  };
  const $ = (sel) => document.querySelector(sel);
  const t = (key) => (zustand.T && zustand.T[key]) || key;

  function el(tag, attrs = {}, ...kinder) {
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

  async function api(methode, url, body, alsFormular = false) {
    const opt = { method: methode, headers: {} };
    if (body !== undefined) {
      if (alsFormular) opt.body = body;
      else { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
    }
    const r = await fetch(url, opt);
    if (!r.ok) {
      let meldung = r.statusText;
      try { meldung = (await r.json()).detail || meldung; } catch (_) { /* keine JSON-Antwort */ }
      throw new Error(meldung);
    }
    return r.json();
  }

  // ---- Texte und Schalter ---------------------------------------------------

  function texteAnwenden() {
    zustand.T = zustand.alleT[zustand.sprache];
    document.documentElement.lang = zustand.sprache;
    document.title = t("titel");
    document.querySelectorAll("[data-t]").forEach((e) => { e.textContent = t(e.dataset.t); });
    $("#eingabe").placeholder = t("chat_platzhalter");
    document.querySelectorAll("[data-sprache]").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.sprache === zustand.sprache)));
    document.querySelectorAll("[data-stil]").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.stil === zustand.stil)));
    $(".leiste").setAttribute("aria-label", t("beispiele"));
    const q = zustand.T.quelle_1450;
    $("#grenze-quelle").textContent = q ? `(${t("quelle")}: ${q.titel}, ${q.fundstelle})` : "";
    demoAnzeigen();
  }

  function demoAnzeigen() {
    const gruppe = $("#demo-gruppe");
    gruppe.querySelectorAll("button").forEach((b) => b.remove());
    for (const d of zustand.demo) {
      gruppe.append(el("button", { type: "button", class: "chip", onclick: () => demoLaden(d) },
        d.titel[zustand.sprache] || d.name));
    }
    gruppe.hidden = zustand.demo.length === 0;
  }

  function beschaeftigt(an) {
    zustand.beschaeftigt = an;
    document.querySelectorAll("#eingabe-form button, #optionen button, .chip, [data-sprache], [data-stil], #neu")
      .forEach((b) => { b.disabled = an; });
    $("#datei").disabled = an;
  }

  // ---- Gespräch -------------------------------------------------------------

  function quelleOeffnen(ev) {
    const ziel = document.getElementById(ev.currentTarget.getAttribute("href").slice(1));
    if (!ziel) return;
    ev.preventDefault();
    const details = ziel.closest("details");
    if (details) details.open = true;
    ziel.scrollIntoView({ block: "nearest" });
    ziel.setAttribute("tabindex", "-1");
    ziel.focus();
  }

  function textMitZitaten(text, praefix) {
    const frag = document.createDocumentFragment();
    for (const teil of text.split(/(\[\d+\])/)) {
      const m = /^\[(\d+)\]$/.exec(teil);
      if (m && praefix) {
        frag.append(el("sup", {}, el("a", {
          href: `#${praefix}-${m[1]}`, "aria-label": `${t("quelle")} ${m[1]}`, onclick: quelleOeffnen,
        }, teil)));
      } else {
        frag.append(document.createTextNode(teil));
      }
    }
    return frag;
  }

  function quellenListe(quellen, praefix) {
    const liste = el("ul", { class: "quellen-liste" });
    quellen.forEach((q, i) => {
      const meta = [
        q.fundstelle ? `${t("fundstelle")}: ${q.fundstelle}` : null,
        q.stand ? `${t("stand")}: ${q.stand}` : (q.art === "recht" ? t("stand_unbekannt") : null),
      ].filter(Boolean).join(" · ");
      liste.append(el("li", { id: praefix ? `${praefix}-${i + 1}` : null },
        el("div", {},
          praefix ? `[${i + 1}] ` : null,
          el("span", { class: "q-titel" }, q.titel), " ",
          q.art === "extern" ? el("span", { class: "badge badge-extern" }, t("extern_badge")) : null),
        meta ? el("div", { class: "q-meta" }, meta) : null,
        q.zitat ? el("blockquote", {}, q.zitat) : null,
        q.url ? el("div", { class: "q-meta" },
          el("a", { href: q.url, target: "_blank", rel: "noopener noreferrer" }, q.url)) : null));
    });
    return el("details", { class: "quellen" }, el("summary", {}, `${t("quellen")} (${quellen.length})`), liste);
  }

  function nachrichtAnzeigen(rolle, text, { quellen = [], grenze = false, laedt = false } = {}) {
    const nr = ++zustand.nr;
    const praefix = quellen.length ? `q${nr}` : null;
    const blase = el("div", { class: "blase" }, rolle === "lotse" ? textMitZitaten(text, praefix) : text);
    if (quellen.length) blase.append(quellenListe(quellen, praefix));
    const klasse = ["nachricht", rolle, grenze ? "grenzfall" : "", laedt ? "laedt" : ""].join(" ").trim();
    const li = el("li", { class: klasse },
      el("span", { class: "wer" }, rolle === "nutzer" ? t("sie") : (grenze ? t("grenze_antwort") : t("lotse"))),
      blase);
    $("#verlauf").append(li);
    li.scrollIntoView({ block: "end" });
    return li;
  }

  function optionenAnzeigen(rueckfrage) {
    const box = $("#optionen");
    box.querySelectorAll("button").forEach((b) => b.remove());
    if (!rueckfrage || !rueckfrage.optionen.length) { box.hidden = true; return; }
    for (const o of rueckfrage.optionen) {
      box.append(el("button", { type: "button", onclick: () => senden(o.wert, o.label) }, o.label));
    }
    box.hidden = false;
  }

  function antwortAnzeigen(a, { blase = true } = {}) {
    zustand.sitzung = a.sitzung_id;
    zustand.sprache = a.sprache;
    zustand.stil = a.stil;
    if (blase) nachrichtAnzeigen("lotse", a.text, { quellen: a.quellen, grenze: Boolean(a.grenze) });
    const modus = $("#modus");
    modus.textContent = t(`modus_${a.modus}`);
    modus.title = t(`modus_titel_${a.modus}`);
    modus.classList.toggle("ki", a.modus === "ki");
    optionenAnzeigen(a.rueckfrage);
    if (!a.grenze) zustand.buendel = a.buendel;
    zustand.fallakte = a.fallakte;
    zustand.angaben = a.angaben;
    akteAnzeigen();
  }

  async function laufen(aufruf) {
    if (zustand.beschaeftigt) return;
    beschaeftigt(true);
    const warte = nachrichtAnzeigen("lotse", t("laedt"), { laedt: true });
    try {
      const a = await aufruf();
      warte.remove();
      antwortAnzeigen(a);
    } catch (err) {
      warte.remove();
      nachrichtAnzeigen("lotse", `${t("fehler")} (${err.message})`);
    } finally {
      beschaeftigt(false);
    }
  }

  function senden(text, anzeige) {
    const sauber = (text || "").trim();
    if (!sauber || !zustand.sitzung) return Promise.resolve();
    nachrichtAnzeigen("nutzer", anzeige || sauber);
    return laufen(() => api("POST", `/api/sitzung/${zustand.sitzung}/nachricht`, { text: sauber }));
  }

  async function neueSitzung() {
    const a = await api("POST", "/api/sitzung", { sprache: zustand.sprache, stil: zustand.stil });
    $("#verlauf").replaceChildren();
    zustand.buendel = [];
    zustand.offen.clear();
    antwortAnzeigen(a);
  }

  async function demoLaden(d) {
    if (!zustand.sitzung) return;
    nachrichtAnzeigen("nutzer", `[${d.titel[zustand.sprache] || d.name}]`);
    await laufen(() => api("POST", `/api/sitzung/${zustand.sitzung}/demo/${encodeURIComponent(d.name)}`));
  }

  // ---- Fallakte -------------------------------------------------------------

  function abschnitt(titel, ...inhalt) {
    return el("div", { class: "abschnitt" }, el("div", { class: "abschnitt-titel" }, titel), ...inhalt);
  }

  async function statusSetzen(schrittId, status) {
    await laufen(() => api("POST",
      `/api/sitzung/${zustand.sitzung}/schritt/${encodeURIComponent(schrittId)}`, { status }));
  }

  async function akteNeuLaden() {
    try {
      antwortAnzeigen(await api("GET", `/api/sitzung/${zustand.sitzung}`), { blase: false });
    } catch (_) { /* Anzeige bleibt unverändert */ }
  }

  function karte(b, eintrag, index) {
    const kid = `k-${b.leistung_id}`;
    const offen = zustand.offen.has(b.leistung_id)
      ? zustand.offen.get(b.leistung_id)
      : index < 3 || (b.dokument || []).length > 0;
    const kopf = el("summary", { class: "karte-summary" },
      el("h3", { id: kid }, b.titel),
      b.beleg === "extern"
        ? el("span", { class: "badge badge-extern" }, t("extern_badge"))
        : el("span", { class: "badge" }, t("lokal_badge")),
      el("span", { class: "karte-kurz" }, b.kurz),
      el("span", { class: "karte-stelle" }, `${t("zustaendig")}: ${b.stelle.name}`));
    const art = el("details", {
      class: "karte", open: offen,
      ontoggle: (ev) => zustand.offen.set(b.leistung_id, ev.currentTarget.open),
    }, kopf);
    if (b.regionen_anzeige && b.regionen_anzeige.length) {
      art.append(el("p", { class: "leise" }, `${t("region")}: ${b.regionen_anzeige.join(", ")}`));
    }
    if (b.details) art.append(el("p", {}, b.details));
    if (b.voraussetzungen && b.voraussetzungen.length) {
      art.append(abschnitt(t("voraussetzungen"), el("ul", {}, b.voraussetzungen.map((v) => el("li", {}, v)))));
    }
    for (const d of b.dokument || []) {
      art.append(el("div", { class: "dok-zitat" }, el("span", { class: "zitat" }, d.text)));
    }

    const st = b.stelle;
    art.append(abschnitt(t("zustaendig"),
      el("div", { class: "stelle-name" }, st.name),
      st.kontakt ? el("div", {}, st.kontakt) : null,
      st.hinweis ? el("div", { class: "leise" }, st.hinweis) : null,
      st.abhaengig_von ? el("div", { class: "stelle-offen" }, `${t("zustaendig_offen")}: ${st.abhaengig_von.label}`) : null));

    if (b.formular) {
      const f = b.formular;
      art.append(abschnitt(t("formular"), el("div", { class: "formular-box" },
        el("div", { class: "stelle-name" }, f.titel),
        f.vorauswahl ? el("div", { class: "leise" }, f.vorauswahl) : null,
        f.stelle ? el("div", {}, f.stelle) : null,
        f.adresse ? el("div", { class: "leise" }, f.adresse) : null,
        el("p", {}, el("a", {
          class: "knopf", href: f.url, download: `${f.id}_Entwurf.pdf`,
          onclick: () => window.setTimeout(akteNeuLaden, 1500),
        }, t("entwurf_laden"))),
        b.fehlende_angaben.length ? el("div", { class: "abschnitt-titel" }, t("fehlend")) : null,
        b.fehlende_angaben.length ? el("ul", { class: "fehlend" }, b.fehlende_angaben.map((x) => el("li", {}, x.label))) : null,
        f.hinweis ? el("p", { class: "leise" }, f.hinweis) : null,
        el("p", { class: "leise" }, t("unterschrift_hinweis")),
        f.ohne_unterlagen ? el("p", { class: "leise" }, f.ohne_unterlagen) : null)));
    }

    if (b.unterlagen && b.unterlagen.length) {
      const liste = el("ul", { class: "checkliste" });
      for (const u of b.unterlagen) {
        const cid = `c-${u.id}`;
        liste.append(el("li", {},
          el("input", {
            type: "checkbox", id: cid, checked: u.status === "erledigt",
            onchange: (ev) => statusSetzen(u.id, ev.target.checked ? "erledigt" : "offen"),
          }),
          el("label", { for: cid }, u.text,
            u.quelle ? el("span", { class: "q-ref" }, ` (${u.quelle.titel}, ${u.quelle.fundstelle})`) : null)));
      }
      art.append(abschnitt(t("unterlagen"), liste));
    }

    if (eintrag && eintrag.schritte.length) {
      const liste = el("ol", { class: "schritte" });
      for (const s of eintrag.schritte) {
        const naechster = s.id === eintrag.naechster_schritt;
        liste.append(el("li", {
          class: `status-${s.status}${naechster ? " ist-naechster" : ""}`,
          "aria-current": naechster ? "step" : null,
        },
          el("span", { class: "schritt-text" }, s.text),
          el("select", {
            id: `s-${s.id}`, "aria-label": `${t("status_aendern")}: ${s.text}`,
            onchange: (ev) => statusSetzen(s.id, ev.target.value),
          }, ["offen", "in_arbeit", "erledigt"].map((v) =>
            el("option", { value: v, selected: v === s.status }, zustand.T.status[v])))));
      }
      art.append(abschnitt(`${t("schritte")} (${eintrag.erledigt}/${eintrag.gesamt})`, liste));
    }

    if (b.quellen && b.quellen.length) art.append(quellenListe(b.quellen, null));
    return art;
  }

  function akteAnzeigen() {
    const fokusId = document.activeElement && document.activeElement.id;
    const fa = zustand.fallakte || { eintraege: [], naechster_schritt: null, historie: [] };
    const eintraege = Object.fromEntries(fa.eintraege.map((e) => [e.leistung_id, e]));

    const nb = $("#naechster");
    if (fa.naechster_schritt) {
      nb.replaceChildren(el("span", { class: "label" }, t("naechster")),
        el("span", {}, `${fa.naechster_schritt.titel}: ${fa.naechster_schritt.text}`));
      nb.hidden = false;
    } else {
      nb.hidden = true;
    }

    const ab = $("#angaben");
    if (zustand.angaben.length) {
      ab.replaceChildren(el("h3", {}, t("angaben")), el("dl", {}, zustand.angaben.map((x) => [
        el("dt", {}, x.label),
        el("dd", {}, x.wert, " ", el("span", { class: "herkunft" }, `(${x.herkunft})`)),
      ])));
      ab.hidden = false;
    } else {
      ab.hidden = true;
    }

    const karten = $("#karten");
    karten.replaceChildren(...zustand.buendel.map((b, i) => karte(b, eintraege[b.leistung_id], i)));
    $("#akte-leer").hidden = zustand.buendel.length > 0;

    if (fa.historie.length) {
      karten.append(el("div", { class: "historie" }, el("strong", {}, t("verlauf")),
        el("ul", {}, fa.historie.slice(-8).reverse().map((h) =>
          el("li", {}, `${h.zeit.slice(11, 16)} · ${h.titel}: ${h.text} → ${zustand.T.status[h.nach]}`)))));
    }
    if (fokusId) {
      const ziel = document.getElementById(fokusId);
      if (ziel) ziel.focus();
    }
  }

  // ---- Ereignisse -----------------------------------------------------------

  function verbinden() {
    $("#eingabe-form").addEventListener("submit", (ev) => {
      ev.preventDefault();
      const feld = $("#eingabe");
      const text = feld.value;
      feld.value = "";
      senden(text);
    });
    $("#eingabe").addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) {
        ev.preventDefault();
        $("#eingabe-form").requestSubmit();
      }
    });
    document.querySelectorAll("[data-sprache]").forEach((b) => b.addEventListener("click", () =>
      einstellen({ sprache: b.dataset.sprache })));
    document.querySelectorAll("[data-stil]").forEach((b) => b.addEventListener("click", () =>
      einstellen({ stil: b.dataset.stil })));
    document.querySelectorAll("[data-szenario]").forEach((b) => b.addEventListener("click", async () => {
      if (zustand.beschaeftigt) return;
      await neueSitzung();
      await senden(zustand.T.beispiele_saetze[b.dataset.szenario]);
    }));
    $("#neu").addEventListener("click", () => { if (!zustand.beschaeftigt) neueSitzung(); });
    const datei = $("#datei");
    datei.addEventListener("focus", () => $("#datei-label").classList.add("datei-fokus"));
    datei.addEventListener("blur", () => $("#datei-label").classList.remove("datei-fokus"));
    datei.addEventListener("change", async () => {
      const f = datei.files[0];
      if (!f || !zustand.sitzung) return;
      nachrichtAnzeigen("nutzer", `[${f.name}]`);
      const fd = new FormData();
      fd.append("datei", f);
      await laufen(() => api("POST", `/api/sitzung/${zustand.sitzung}/dokument`, fd, true));
      datei.value = "";
    });
  }

  async function einstellen(aenderung) {
    if (zustand.beschaeftigt) return;
    if (aenderung.sprache) zustand.sprache = aenderung.sprache;
    if (aenderung.stil) zustand.stil = aenderung.stil;
    texteAnwenden();
    if (zustand.sitzung) {
      await laufen(() => api("POST", `/api/sitzung/${zustand.sitzung}/einstellungen`, aenderung));
    }
  }

  async function start() {
    verbinden();
    try {
      zustand.alleT = await api("GET", "/api/texte");
      zustand.demo = await api("GET", "/api/demo/dokumente");
      texteAnwenden();
      await neueSitzung();
    } catch (err) {
      nachrichtAnzeigen("lotse", `Fehler / Error: ${err.message}`);
    }
  }

  start();
})();
