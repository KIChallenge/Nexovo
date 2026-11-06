"use strict";
// SV KI-Lotse – Oberfläche ohne Build-Schritt. Alle Daten werden per textContent eingefügt (kein innerHTML).
(() => {
  const zustand = {
    sitzung: null, sprache: "de", stil: "einfach", richtung: "ltr",
    T: {}, texteSprache: null, texteCache: new Map(), sprachen: [], ki: false,
    buendel: [], weitereAnzahl: 0, fallakte: null, angaben: [], termine: [], impfungen: [], medikamente: [],
    uebersicht: null, dokumente: [], demo: [], nr: 0, beschaeftigt: false,
    offen: new Map(),  // Leistungs-ID → Karte aufgeklappt?
    weitereOffen: false,
    vorlesen: null,  // {knopf, utterance} der gerade vorgelesenen Nachricht
  };
  const BASIS = ["de", "en"];
  const SPRACH_TAG = { de: "de-AT", en: "en-GB", tr: "tr-TR", bs: "bs-BA", uk: "uk-UA", ar: "ar" };
  const $ = (sel) => document.querySelector(sel);
  const t = (key) => (zustand.T && zustand.T[key]) || key;
  const tf = (key, werte) => t(key).replace(/\{(\w+)\}/g, (m, k) => (k in werte ? String(werte[k]) : m));

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
      try {
        const d = (await r.json()).detail;
        if (d) meldung = typeof d === "string" ? d : JSON.stringify(d);
      } catch (_) { /* keine JSON-Antwort */ }
      throw new Error(meldung);
    }
    return r.json();
  }

  // Nur http(s) und Pfade der eigenen App als Link zulassen.
  function sichereUrl(u) {
    if (!u) return null;
    if (u.startsWith("/") && !u.startsWith("//")) return u;
    try {
      const x = new URL(u);
      return x.protocol === "https:" || x.protocol === "http:" ? x.href : null;
    } catch (_) {
      return null;
    }
  }

  const kurzUrl = (u) => u.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "");

  function link(url, text) {
    const href = sichereUrl(url);
    if (!href) return null;
    return el("a", { href, target: "_blank", rel: "noopener noreferrer", class: "link-extern" }, text || kurzUrl(href));
  }

  function belegBadge(beleg) {
    return beleg === "extern"
      ? el("span", { class: "badge badge-extern" }, t("extern_badge"))
      : el("span", { class: "badge" }, t("lokal_badge"));
  }

  // Kompakter, aufklappbarer Beleg für eine einzelne Quelle.
  function belegKurz(q, beleg) {
    if (!q) return null;
    const art = beleg || (q.art === "extern" ? "extern" : "lokal");
    const kopf = [q.titel, q.fundstelle].filter(Boolean).join(", ");
    return el("details", { class: "beleg" },
      el("summary", {}, `${t("quelle")}: ${kopf} `, belegBadge(art)),
      q.zitat ? el("blockquote", { dir: "auto" }, q.zitat) : null,
      q.stand ? el("div", { class: "q-meta" }, `${t("stand")}: ${q.stand}`) : null,
      q.url ? el("div", { class: "q-meta" }, link(q.url, q.url)) : null);
  }

  // ---- Texte und Schalter ---------------------------------------------------

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

  function texteAnwenden() {
    const sp = zustand.texteSprache || "de";
    const info = zustand.sprachen.find((s) => s.code === sp);
    document.documentElement.lang = sp;
    document.documentElement.dir = (info && info.richtung) || "ltr";
    document.title = t("titel");
    document.querySelectorAll("[data-t]").forEach((e) => { e.textContent = t(e.dataset.t); });
    $("#eingabe").placeholder = t("chat_platzhalter");
    const q = zustand.T.quelle_1450;
    $("#grenze-quelle").textContent = q ? `(${t("quelle")}: ${q.titel}, ${q.fundstelle})` : "";
    document.querySelectorAll(".vorlesen").forEach((b) => {
      b.textContent = t(b.getAttribute("aria-pressed") === "true" ? "vorlesen_stop" : "vorlesen");
    });
    mikroStatus(Boolean(mikro.erkennung));
    steuerungAnzeigen();
    demoAnzeigen();
  }

  function steuerungAnzeigen() {
    document.querySelectorAll("[data-sprache]").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.sprache === zustand.sprache)));
    document.querySelectorAll("[data-stil]").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.stil === zustand.stil)));
    const sel = $("#sprache-weitere");
    const weitere = zustand.sprachen.filter((s) => !BASIS.includes(s.code));
    sel.replaceChildren(el("option", { value: "" }, `${t("weitere_sprachen")} …`),
      ...weitere.map((s) => el("option", {
        value: s.code, lang: s.code, disabled: !s.verfuegbar, selected: s.code === zustand.sprache,
      }, s.verfuegbar ? s.name : `${s.name} – ${t("nur_ki")}`)));
    sel.hidden = weitere.length === 0;
    sel.classList.toggle("gewaehlt", !BASIS.includes(zustand.sprache));
    sel.title = weitere.some((s) => s.verfuegbar) ? t("weitere_sprachen") : t("weitere_sprachen_hinweis");
    const speichern = $("#fall-speichern");
    if (zustand.sitzung) speichern.href = `/api/sitzung/${encodeURIComponent(zustand.sitzung)}/export`;
    else speichern.removeAttribute("href");
  }

  const demoTitel = (d) =>
    (d.text_key && zustand.T[d.text_key]) || d.titel[zustand.sprache] || d.titel.en || d.name;

  function demoAnzeigen() {
    const gruppe = $("#demo-gruppe");
    gruppe.querySelectorAll("button").forEach((b) => b.remove());
    for (const d of zustand.demo) {
      const gesperrt = Boolean(d.nur_ki) && !zustand.ki;  // Foto-Abschrift braucht den KI-Modus
      gruppe.append(el("button", {
        type: "button", class: "chip", onclick: () => demoLaden(d),
        disabled: gesperrt || zustand.beschaeftigt, "data-gesperrt": gesperrt ? "1" : null,
        title: gesperrt ? t("nur_ki") : null,
      }, demoTitel(d), gesperrt ? ` – ${t("nur_ki")}` : null));
    }
    gruppe.hidden = zustand.demo.length === 0;
  }

  function beschaeftigt(an) {
    zustand.beschaeftigt = an;
    document.querySelectorAll(
      "#eingabe-form button, #optionen button, .chip, [data-sprache], [data-stil], #neu, #sprache-weitere, .aktion",
    ).forEach((b) => { b.disabled = an || b.dataset.gesperrt === "1"; });
    for (const id of ["#datei", "#foto", "#fall-datei"]) $(id).disabled = an;
    $(".akte").setAttribute("aria-busy", String(an));
  }

  // ---- Sprachsteuerung: Vorlesen und Spracheingabe -------------------------

  function vorlesenBeenden() {
    if (!zustand.vorlesen) return;
    const knopf = zustand.vorlesen.knopf;
    knopf.setAttribute("aria-pressed", "false");
    knopf.textContent = t("vorlesen");
    zustand.vorlesen = null;
  }

  function vorlesen(knopf, text, sprache) {
    const lief = zustand.vorlesen && zustand.vorlesen.knopf === knopf;
    vorlesenBeenden();
    window.speechSynthesis.cancel();
    if (lief) return;  // zweiter Klick stoppt
    const u = new SpeechSynthesisUtterance(text);
    u.lang = SPRACH_TAG[sprache] || sprache;
    const ende = () => { if (zustand.vorlesen && zustand.vorlesen.utterance === u) vorlesenBeenden(); };
    u.addEventListener("end", ende);
    u.addEventListener("error", ende);
    zustand.vorlesen = { knopf, utterance: u };
    knopf.setAttribute("aria-pressed", "true");
    knopf.textContent = t("vorlesen_stop");
    window.speechSynthesis.speak(u);
  }

  function vorlesenKnopf(text) {
    const sprache = zustand.sprache;
    const sauber = text.replace(/\[\d+\]/g, "");
    const knopf = el("button", { type: "button", class: "vorlesen", "aria-pressed": "false" }, t("vorlesen"));
    knopf.addEventListener("click", () => vorlesen(knopf, sauber, sprache));
    return knopf;
  }

  const mikro = { erkennung: null, fehler: false };

  function mikroStatus(an) {
    const knopf = $("#mikro");
    knopf.setAttribute("aria-pressed", String(an));
    knopf.classList.toggle("aktiv", an);
    $("#mikro-text").textContent = t(an ? "mikro_stop" : "mikro_start");
    knopf.title = t(an ? "mikro_stop" : "mikro_start");
    if (an) $("#mikro-status").textContent = t("mikro_aktiv");
    else if (!mikro.fehler) $("#mikro-status").textContent = "";
  }

  function mikroEinrichten() {
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
        q.zitat ? el("blockquote", { dir: "auto" }, q.zitat) : null,
        q.url ? el("div", { class: "q-meta" }, link(q.url, q.url)) : null));
    });
    return el("details", { class: "quellen" }, el("summary", {}, `${t("quellen")} (${quellen.length})`), liste);
  }

  function nachrichtAnzeigen(rolle, text, { quellen = [], grenze = false, laedt = false } = {}) {
    const nr = ++zustand.nr;
    const praefix = quellen.length ? `q${nr}` : null;
    const blase = el("div", { class: "blase", dir: "auto" }, rolle === "lotse" ? textMitZitaten(text, praefix) : text);
    if (quellen.length) blase.append(quellenListe(quellen, praefix));
    const klasse = ["nachricht", rolle, grenze ? "grenzfall" : "", laedt ? "laedt" : ""].join(" ").trim();
    const li = el("li", { class: klasse },
      el("span", { class: "wer" }, rolle === "nutzer" ? t("sie") : (grenze ? t("grenze_antwort") : t("lotse"))),
      blase);
    if (rolle === "lotse" && !laedt && "speechSynthesis" in window) li.append(vorlesenKnopf(text));
    const verlauf = $("#verlauf");
    verlauf.append(li);
    // Nur im Verlauf scrollen (die Seite bleibt stehen); lange Antworten ab ihrem Anfang zeigen
    const vr = verlauf.getBoundingClientRect();
    const lr = li.getBoundingClientRect();
    verlauf.scrollTop += lr.height > vr.height ? lr.top - vr.top : lr.bottom - vr.bottom;
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

  async function antwortAnzeigen(a, { blase = true } = {}) {
    const gleicheSitzung = zustand.sitzung === a.sitzung_id;
    zustand.sitzung = a.sitzung_id;
    zustand.sprache = a.sprache;
    zustand.stil = a.stil;
    zustand.richtung = a.richtung === "rtl" ? "rtl" : "ltr";
    if (zustand.texteSprache !== a.sprache) {
      try { await texteSetzen(a.sprache); } catch (_) { /* Oberfläche bleibt in der bisherigen Sprache */ }
    }
    steuerungAnzeigen();
    $(".haupt").dir = zustand.richtung;
    if (blase) nachrichtAnzeigen("lotse", a.text, { quellen: a.quellen, grenze: Boolean(a.grenze) });
    const modus = $("#modus");
    modus.textContent = t(`modus_${a.modus}`);
    modus.title = t(`modus_titel_${a.modus}`);
    modus.classList.toggle("ki", a.modus === "ki");
    optionenAnzeigen(a.rueckfrage);
    const bisher = new Set(zustand.termine.map((x) => x.id));
    if (!a.grenze) {
      // Bei einer Grenzantwort bleibt der bisherige Fallstand sichtbar.
      zustand.buendel = a.buendel || [];
      zustand.weitereAnzahl = a.weitere_anzahl || 0;
      zustand.termine = a.termine || [];
      zustand.impfungen = a.impfungen || [];
      zustand.medikamente = a.medikamente || [];
    }
    zustand.fallakte = a.fallakte;
    zustand.angaben = a.angaben || [];
    zustand.uebersicht = a.status_uebersicht || null;
    zustand.dokumente = a.dokumente || [];
    akteAnzeigen();
    // Neu angelegter Termin: Karte zeigen und fokussieren
    const neuerTermin = gleicheSitzung && zustand.termine.find((x) => !bisher.has(x.id));
    if (neuerTermin) fokussieren(`termin-${neuerTermin.id}`);
  }

  async function laufen(aufruf, { neu = false, anzeige = null } = {}) {
    if (zustand.beschaeftigt) return null;
    beschaeftigt(true);
    const warte = nachrichtAnzeigen("lotse", t("laedt"), { laedt: true });
    try {
      const a = await aufruf();
      warte.remove();
      if (neu) {
        // Wiederhergestellter Fall: Gespräch neu beginnen
        $("#verlauf").replaceChildren();
        zustand.offen.clear();
        zustand.weitereOffen = false;
        if (anzeige) nachrichtAnzeigen("nutzer", anzeige);
      }
      await antwortAnzeigen(a);
      return a;
    } catch (err) {
      warte.remove();
      nachrichtAnzeigen("lotse", `${t("fehler")} (${err.message})`);
      return null;
    } finally {
      beschaeftigt(false);
      steuerungAnzeigen();
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
    zustand.weitereOffen = false;
    await antwortAnzeigen(a);
  }

  async function demoLaden(d) {
    if (!zustand.sitzung) return;
    nachrichtAnzeigen("nutzer", `[${demoTitel(d)}]`);
    await laufen(() => api("POST", `/api/sitzung/${zustand.sitzung}/demo/${encodeURIComponent(d.name)}`));
  }

  function dateiSenden(f) {
    if (!f || !zustand.sitzung) return Promise.resolve();
    nachrichtAnzeigen("nutzer", `[${f.name}]`);
    const fd = new FormData();
    fd.append("datei", f);
    return laufen(() => api("POST", `/api/sitzung/${zustand.sitzung}/dokument`, fd, true));
  }

  function fallLaden(f) {
    if (!f) return Promise.resolve();
    const fd = new FormData();
    fd.append("datei", f);
    return laufen(() => api("POST", "/api/import", fd, true), { neu: true, anzeige: `[${t("fall_laden")}: ${f.name}]` });
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
      await antwortAnzeigen(await api("GET", `/api/sitzung/${zustand.sitzung}`), { blase: false });
    } catch (_) { /* Anzeige bleibt unverändert */ }
  }

  function terminStarten(anlass, leistung, anzeige) {
    nachrichtAnzeigen("nutzer", anzeige);
    return laufen(() => api("POST", `/api/sitzung/${zustand.sitzung}/termin`, { anlass, leistung }));
  }

  async function terminAendern(terminId, daten) {
    await laufen(() => api("POST",
      `/api/sitzung/${zustand.sitzung}/termin/${encodeURIComponent(terminId)}`, daten));
  }

  function fokussieren(id) {
    const ziel = document.getElementById(id);
    if (!ziel) return;
    ziel.setAttribute("tabindex", "-1");
    ziel.scrollIntoView({ block: "start" });
    ziel.focus({ preventScroll: true });
  }

  function schritteListe(eintrag) {
    const liste = el("ol", { class: "schritte" });
    for (const s of eintrag.schritte) {
      const naechster = s.id === eintrag.naechster_schritt;
      liste.append(el("li", {
        class: `status-${s.status}${naechster ? " ist-naechster" : ""}`,
        "aria-current": naechster ? "step" : null,
      },
        el("span", { class: "schritt-text" }, s.text),
        el("select", {
          id: `s-${s.id}`, class: "aktion", "aria-label": `${t("status_aendern")}: ${s.text}`,
          onchange: (ev) => statusSetzen(s.id, ev.target.value),
        }, ["offen", "in_arbeit", "erledigt"].map((v) =>
          el("option", { value: v, selected: v === s.status }, zustand.T.status ? zustand.T.status[v] : v)))));
    }
    return abschnitt(`${t("schritte")} (${eintrag.erledigt}/${eintrag.gesamt})`, liste);
  }

  function einrichtungenAbschnitt(liste) {
    if (!liste || !liste.length) return null;
    return abschnitt(t("einrichtungen_titel"), el("ul", { class: "einrichtungen" }, liste.map((e) =>
      el("li", {},
        el("div", { class: "einrichtung-kopf" },
          el("span", { class: "stelle-name" }, e.name), " ",
          el("span", { class: "leise" }, e.regionen && e.regionen.length ? e.regionen.join(", ") : t("oesterreichweit"))),
        e.kontakt ? el("div", {}, e.kontakt) : null,
        e.url ? el("div", {}, link(e.url)) : null,
        belegKurz(e.quelle, e.beleg)))));
  }

  function regionalAbschnitt(r) {
    if (!r) return null;
    return abschnitt(`${t("regional_titel")}: ${r.bundesland}`, el("div", { class: "regional" },
      el("div", { class: "stelle-name" }, r.stelle),
      r.kontakt ? el("div", {}, r.kontakt) : null,
      r.url ? el("div", {}, link(r.url)) : null,
      belegKurz(r.quelle, r.beleg)));
  }

  function karte(b, eintrag, offenStandard) {
    const kid = `k-${b.leistung_id}`;
    const offen = zustand.offen.has(b.leistung_id) ? zustand.offen.get(b.leistung_id) : offenStandard;
    const kopf = el("summary", { class: "karte-summary" },
      el("h3", { id: kid }, b.titel),
      belegBadge(b.beleg),
      el("span", { class: "karte-kurz" }, b.kurz),
      el("span", { class: "karte-stelle" }, `${t("zustaendig")}: ${b.stelle.name}`));
    const art = el("details", {
      class: `karte${b.primaer ? " primaer" : ""}`, open: offen,
      ontoggle: (ev) => zustand.offen.set(b.leistung_id, ev.currentTarget.open),
    }, kopf);
    if (b.regionen_anzeige && b.regionen_anzeige.length) {
      art.append(el("p", { class: "leise" }, `${t("region")}: ${b.regionen_anzeige.join(", ")}`));
    }
    if (b.nutzen) {
      art.append(el("div", { class: "nutzen" },
        el("div", { class: "abschnitt-titel" }, t("nutzen_titel")),
        el("p", {}, b.nutzen),
        belegKurz(b.nutzen_quelle)));
    }
    if (b.details) art.append(el("p", {}, b.details));
    if (b.voraussetzungen && b.voraussetzungen.length) {
      art.append(abschnitt(t("voraussetzungen"), el("ul", {}, b.voraussetzungen.map((v) => el("li", {}, v)))));
    }
    for (const d of b.dokument || []) {
      art.append(el("div", { class: "dok-zitat" }, el("span", { class: "zitat", dir: "auto" }, d.text)));
    }

    const st = b.stelle;
    art.append(abschnitt(t("zustaendig"),
      el("div", { class: "stelle-name" }, st.name),
      st.kontakt ? el("div", {}, st.kontakt) : null,
      st.hinweis ? el("div", { class: "leise" }, st.hinweis) : null,
      st.abhaengig_von ? el("div", { class: "stelle-offen" }, `${t("zustaendig_offen")}: ${st.abhaengig_von.label}`) : null,
      st.quelle ? belegKurz(st.quelle, st.beleg || null) : null));
    const regional = regionalAbschnitt(b.regional);
    if (regional) art.append(regional);
    const einrichtungen = einrichtungenAbschnitt(b.einrichtungen);
    if (einrichtungen) art.append(einrichtungen);

    if (b.termin_anlass) {
      art.append(el("p", { class: "termin-start" }, el("button", {
        type: "button", class: "knopf aktion",
        onclick: () => terminStarten(b.termin_anlass, b.leistung_id, `${t("termin_vorbereiten")}: ${b.titel}`),
      }, t("termin_vorbereiten"))));
    }

    if (b.formular) {
      const f = b.formular;
      const fehlend = b.fehlende_angaben || [];
      art.append(abschnitt(t("formular"), el("div", { class: "formular-box" },
        el("div", { class: "stelle-name" }, f.titel),
        f.region_hinweis ? el("div", { class: "stelle-offen" }, f.region_hinweis) : null,
        f.vorauswahl ? el("div", { class: "leise" }, f.vorauswahl) : null,
        f.stelle ? el("div", {}, f.stelle) : null,
        f.adresse ? el("div", { class: "leise" }, f.adresse) : null,
        el("p", {}, el("a", {
          class: "knopf", href: sichereUrl(f.url), download: `${f.id}_Entwurf.pdf`,
          onclick: () => window.setTimeout(akteNeuLaden, 1500),
        }, t("entwurf_laden"))),
        fehlend.length ? el("div", { class: "abschnitt-titel" }, t("fehlend")) : null,
        fehlend.length ? el("ul", { class: "fehlend" }, fehlend.map((x) => el("li", {}, x.label))) : null,
        f.hinweis ? el("p", { class: "leise" }, f.hinweis) : null,
        el("p", { class: "leise" }, t("unterschrift_hinweis")),
        f.ohne_unterlagen ? el("p", { class: "leise" }, f.ohne_unterlagen) : null)));
    }

    if (b.unterlagen && b.unterlagen.length) {
      const eintragLi = (u) => {
        const cid = `c-${u.id}`;
        return el("li", {},
          el("input", {
            type: "checkbox", id: cid, class: "aktion", checked: u.status === "erledigt",
            onchange: (ev) => statusSetzen(u.id, ev.target.checked ? "erledigt" : "offen"),
          }),
          el("label", { for: cid }, u.text,
            u.quelle ? el("span", { class: "q-ref" }, ` (${u.quelle.titel}, ${u.quelle.fundstelle})`) : null));
      };
      // Unterlagen zum regionalen Formular gesammelt unter ihrem Hinweis (solange das Bundesland offen ist)
      const gruppen = new Map();
      for (const u of b.unterlagen) {
        const hinweis = u.region_hinweis || "";
        if (!gruppen.has(hinweis)) gruppen.set(hinweis, []);
        gruppen.get(hinweis).push(u);
      }
      const allgemein = gruppen.get("") || [];
      gruppen.delete("");
      art.append(abschnitt(t("unterlagen"),
        allgemein.length ? el("ul", { class: "checkliste" }, allgemein.map(eintragLi)) : null,
        [...gruppen].map(([hinweis, liste]) => el("div", { class: "unterlagen-region" },
          el("div", { class: "stelle-offen" }, hinweis),
          el("ul", { class: "checkliste" }, liste.map(eintragLi))))));
    }

    if (eintrag && eintrag.schritte.length) art.append(schritteListe(eintrag));
    if (b.quellen && b.quellen.length) art.append(quellenListe(b.quellen, null));
    return art;
  }

  // TT.MM.JJJJ ↔ JJJJ-MM-TT (Wert von <input type="date">)
  const zuIso = (d) => { const m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(d || ""); return m ? `${m[3]}-${m[2]}-${m[1]}` : ""; };
  const vonIso = (d) => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d || ""); return m ? `${m[3]}.${m[2]}.${m[1]}` : ""; };

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

  function terminKarte(tm, eintrag) {
    const id = tm.id;
    const art = el("article", { class: `termin status-${tm.status}`, "aria-labelledby": `termin-${id}` });
    art.append(el("div", { class: "termin-kopf" },
      el("h3", { id: `termin-${id}` }, `${t("termin_titel")}: ${tm.anlass_label}`),
      el("span", { class: `badge badge-termin-${tm.status}` }, t(`termin_status_${tm.status}`))));

    const fakten = [
      tm.ort ? [t("termin_ort"), tm.ort] : null,
      tm.zeit ? [t("termin_zeit"), tm.zeit] : null,
      tm.datum ? [t("datum"), tm.datum] : null,
      tm.uhrzeit ? [t("uhrzeit"), tm.uhrzeit] : null,
    ].filter(Boolean);
    if (fakten.length) {
      art.append(el("dl", { class: "termin-fakten" }, fakten.map(([k, v]) => [el("dt", {}, k), el("dd", {}, v)])));
    }
    // Erledigte Termine kompakt: nur Eckdaten, Kalender, Schritte und Quellen
    const aktiv = tm.status !== "erledigt";
    if (aktiv && tm.wo) art.append(abschnitt(t("termin_wo"), el("p", {}, tm.wo)));

    const hinweise = aktiv ? tm.hinweise || [] : [];
    if (hinweise.length) {
      // Bei Beschwerden steht der 1450-Hinweis an erster Stelle und wird hervorgehoben.
      const beschwerden = tm.anlass === "beschwerden";
      art.append(abschnitt(t("termin_hinweise"), el("ul", { class: "termin-hinweise" }, hinweise.map((h, i) =>
        el("li", { class: beschwerden && i === 0 ? "hinweis-1450" : null }, h)))));
    }

    const suche = aktiv ? (tm.suche || []).filter((s) => sichereUrl(s.url)) : [];
    if (suche.length) {
      art.append(abschnitt(t("termin_suche"), el("ul", { class: "termin-suche" }, suche.map((s) =>
        el("li", {}, link(s.url, s.name), " ", belegBadge(s.beleg))))));
    }

    if (aktiv && tm.anfrage_text) {
      const feldId = `anfrage-${id}`;
      const feld = el("textarea", { id: feldId, class: "anfrage", readonly: true, rows: 2, dir: "auto" }, tm.anfrage_text);
      const meldung = el("span", { class: "kopier-meldung", role: "status", "aria-live": "polite" });
      art.append(el("div", { class: "abschnitt" },
        el("label", { class: "abschnitt-titel", for: feldId }, t("termin_anfrage")),
        feld,
        el("div", { class: "knopf-zeile" },
          el("button", {
            type: "button", id: `kopieren-${id}`, class: "knopf knopf-sekundaer knopf-klein",
            onclick: () => kopieren(tm.anfrage_text, feld, meldung),
          }, t("kopieren")),
          meldung)));
    }

    if (tm.status !== "erledigt") {
      const datumId = `datum-${id}`;
      const zeitId = `uhrzeit-${id}`;
      const datumFeld = el("input", { type: "date", id: datumId, value: zuIso(tm.datum), required: true });
      const zeitFeld = el("input", { type: "time", id: zeitId, value: tm.uhrzeit || "" });
      const form = el("form", { class: "termin-form" },
        el("fieldset", {},
          el("legend", {}, t("termin_eintragen")),
          el("div", { class: "termin-felder" },
            el("div", {}, el("label", { for: datumId }, t("datum")), datumFeld),
            el("div", {}, el("label", { for: zeitId }, t("uhrzeit")), zeitFeld),
            el("button", { type: "submit", class: "knopf aktion", id: `speichern-${id}` }, t("termin_speichern")))));
      form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        const datum = vonIso(datumFeld.value);
        if (!datum) return;  // Pflichtfeld prüft der Browser
        const daten = { datum, status: "vereinbart" };
        if (zeitFeld.value) daten.uhrzeit = zeitFeld.value;
        terminAendern(id, daten);
      });
      art.append(form);
    }

    const aktionen = [];
    const ics = sichereUrl(tm.ics_url);
    if (ics) {
      aktionen.push(el("a", { class: "knopf", href: ics, download: true, id: `ics-${id}` }, t("ics_laden")));
    }
    if (tm.status === "vereinbart") {
      aktionen.push(el("button", {
        type: "button", class: "knopf knopf-sekundaer aktion", id: `erledigt-${id}`,
        onclick: () => terminAendern(id, { status: "erledigt" }),
      }, t("termin_als_erledigt")));
    }
    if (aktionen.length) art.append(el("div", { class: "knopf-zeile" }, aktionen));

    if (eintrag && eintrag.schritte.length) art.append(schritteListe(eintrag));
    art.append(el("p", { class: "leise" }, t("termin_kein_buchen")));
    if (tm.quellen && tm.quellen.length) art.append(quellenListe(tm.quellen, null));
    return art;
  }

  function dokumentPanels() {
    const panels = [];
    if (zustand.dokumente.length) {
      panels.push(el("section", { class: "panel", "aria-labelledby": "dok-titel" },
        el("h3", { id: "dok-titel" }, t("dokumente_titel")),
        el("ul", { class: "dok-liste" }, zustand.dokumente.map((d) => el("li", {},
          el("span", { class: "dok-name", dir: "auto" }, d.name),
          d.seiten ? el("span", { class: "leise" }, ` · ${d.seiten} ${t(d.seiten === 1 ? "seite_eine" : "seiten")}`) : null,
          d.transkribiert ? el("div", { class: "transkribiert" }, t("transkribiert_hinweis")) : null)))));
    }
    if (zustand.impfungen.length) {
      // Dokumentname nur, wenn die Einträge aus mehreren Dokumenten stammen
      const mehrere = new Set(zustand.impfungen.map((i) => i.dokument)).size > 1;
      panels.push(el("section", { class: "panel panel-impf", "aria-labelledby": "impf-titel" },
        el("h3", { id: "impf-titel" }, t("impfungen_titel")),
        el("p", { class: "panel-hinweis" }, t("impfungen_hinweis")),
        mehrere ? null : el("p", { class: "leise" }, `${t("dokument")}: ${zustand.impfungen[0].dokument}`),
        el("div", { class: "tabelle-rahmen", role: "region", tabindex: "0", "aria-labelledby": "impf-titel" },
          el("table", {},
            el("thead", {}, el("tr", {},
              el("th", { scope: "col" }, t("impfung")),
              el("th", { scope: "col" }, t("datum")),
              el("th", { scope: "col" }, t("fundstelle")))),
            el("tbody", {}, zustand.impfungen.map((i) => el("tr", {},
              el("td", { dir: "auto" }, i.impfung),
              el("td", { class: "zahl" }, i.datum),
              el("td", { class: "leise" },
                mehrere ? `${i.dokument}, ${t("seite")} ${i.seite}` : `${t("seite")} ${i.seite}`))))))));
    }
    if (zustand.medikamente.length) {
      panels.push(el("section", { class: "panel panel-medi", "aria-labelledby": "medi-titel" },
        el("h3", { id: "medi-titel" }, t("medikamente_titel")),
        el("p", { class: "panel-hinweis" }, t("medikamente_hinweis")),
        el("ul", { class: "medi-liste" }, zustand.medikamente.map((m) => {
          const e = m.eko;
          return el("li", {},
            el("div", { class: "medi-kopf" },
              el("span", { class: "medi-name", dir: "auto" }, m.name_dokument), " ",
              el("span", { class: "leise" }, `(${m.dokument}, ${t("seite")} ${m.seite})`)),
            e ? ekoBlock(e)
              : el("div", { class: "leise medi-fehlt" }, t("eko_nicht_gefunden")));
        }))));
    }
    return panels;
  }

  // ---- Erstattungskodex: alle Einträge zu einem Namen ----------------------

  const ekoAnzahl = (n) => (n === 1 ? t("eko_eintrag_eins") : tf("eko_eintraege", { n }));
  const kennzeichenListe = (kz) => kz.map((k) => el("span", { class: "kz" }, k));

  // Beispielpackung („z. B.“) – keine Aussage über die Packung im Dokument
  function ekoBeispiel(b) {
    if (!b || !b.name) return null;
    return el("span", { class: "leise" }, ` · ${t("eko_beispiel")} `,
      el("span", { dir: "auto" }, b.name), b.pzn ? `, PZN ${b.pzn}` : null);
  }

  function ekoBlock(e) {
    const status = e.einheitlich === false
      // Gemischte Boxen/Kennzeichen: jede Variante mit Anzahl und Beispiel, häufigste zuerst
      ? el("ul", { class: "eko-varianten" }, (e.varianten || []).map((v) => el("li", {},
        el("span", { class: `badge box-${v.box}` }, t(`box_${v.box}`)), " ",
        v.kennzeichen.length ? el("span", { class: "kennzeichen" }, `${t("kennzeichen")}: `, kennzeichenListe(v.kennzeichen)) : null,
        el("span", { class: "leise eko-anzahl" }, ` · ${ekoAnzahl(v.anzahl)}`),
        ekoBeispiel(v.beispiel))))
      // Einheitlich: Box und Kennzeichen; Anzahl und Beispiel nennt der erste Satz der Erklärung
      : el("div", { class: "eko-status" },
        el("span", { class: `badge box-${e.box}` }, t(`box_${e.box}`)), " ",
        e.kennzeichen && e.kennzeichen.length
          ? el("span", { class: "kennzeichen" }, `${t("kennzeichen")}: `, kennzeichenListe(e.kennzeichen)) : null);
    return el("div", { class: "medi-eko" }, status,
      e.erklaerung ? el("p", { class: "eko-erklaerung" }, e.erklaerung) : null,
      e.quellen && e.quellen.length ? quellenListe(e.quellen, null) : null);
  }

  function uebersichtAnzeigen(fa) {
    const box = $("#uebersicht");
    const u = zustand.uebersicht;
    const gesamt = u ? u.erledigt + u.offen : 0;
    if (!gesamt) { box.hidden = true; return; }
    const status = zustand.T.status || {};
    const teile = [
      el("progress", { value: u.erledigt, max: gesamt, "aria-labelledby": "uebersicht-text" }),
      el("span", { id: "uebersicht-text" },
        `${t("uebersicht")}: ${u.erledigt} ${status.erledigt || "erledigt"} · ${u.offen} ${status.offen || "offen"}`),
    ];
    if (u.naechster && !fa.naechster_schritt) {
      teile.push(el("span", { class: "leise" }, `${t("naechster")}: ${u.naechster}`));
    }
    box.replaceChildren(...teile);
    box.hidden = false;
  }

  function akteAnzeigen() {
    const fokusId = document.activeElement && document.activeElement.id;
    const fa = zustand.fallakte || { eintraege: [], naechster_schritt: null, historie: [] };
    const eintraege = Object.fromEntries(fa.eintraege.map((e) => [e.leistung_id, e]));
    const terminEintraege = Object.fromEntries(fa.eintraege.filter((e) => e.termin_id).map((e) => [e.termin_id, e]));

    uebersichtAnzeigen(fa);

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

    $("#termine").replaceChildren(...zustand.termine.map((tm) => terminKarte(tm, terminEintraege[tm.id])));
    document.querySelectorAll("textarea.anfrage").forEach((f) => {
      f.style.height = `${f.scrollHeight + 4}px`;  // ganzer Anfragetext ohne inneres Scrollen
    });
    const panels = dokumentPanels();
    $("#dokumente").replaceChildren(...panels);

    const primaer = zustand.buendel.filter((b) => b.primaer);
    const weitere = zustand.buendel.filter((b) => !b.primaer);
    const karten = $("#karten");
    // Auf schmalen Bildschirmen nur die erste Hauptkarte aufgeklappt, die anderen zeigen ihre Kurzfassung
    const schmal = window.matchMedia("(max-width: 480px)").matches;
    karten.replaceChildren(...primaer.map((b, i) =>
      karte(b, eintraege[b.leistung_id], i === 0 || !schmal || (b.dokument || []).length > 0)));
    if (weitere.length) {
      const anzahl = zustand.weitereAnzahl || weitere.length;
      karten.append(el("details", {
        class: "weitere", id: "weitere", open: zustand.weitereOffen,
        ontoggle: (ev) => { zustand.weitereOffen = ev.currentTarget.open; },
      },
        el("summary", {}, tf("weitere_angebote", { n: anzahl })),
        el("div", { class: "karten" },
          weitere.map((b) => karte(b, eintraege[b.leistung_id], (b.dokument || []).length > 0)))));
    }
    $("#akte-leer").hidden = zustand.buendel.length + zustand.termine.length + panels.length > 0;

    const hist = $("#historie");
    if (fa.historie.length) {
      hist.replaceChildren(el("strong", {}, t("verlauf")),
        el("ul", {}, fa.historie.slice(-8).reverse().map((h) =>
          el("li", {}, `${h.zeit.slice(11, 16)} · ${h.titel}: ${h.text} → ${(zustand.T.status || {})[h.nach] || h.nach}`))));
      hist.hidden = false;
    } else {
      hist.hidden = true;
    }
    if (fokusId) {
      const ziel = document.getElementById(fokusId);
      if (ziel) ziel.focus();
    }
  }

  // ---- Ereignisse -----------------------------------------------------------

  function dateiKnopf(input, beiAuswahl) {
    const label = document.querySelector(`label[for="${input.id}"]`);
    input.addEventListener("focus", () => label.classList.add("datei-fokus"));
    input.addEventListener("blur", () => label.classList.remove("datei-fokus"));
    input.addEventListener("change", async () => {
      const f = input.files[0];
      await beiAuswahl(f);
      input.value = "";
    });
  }

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
    $("#sprache-weitere").addEventListener("change", (ev) => {
      if (ev.target.value) einstellen({ sprache: ev.target.value });
    });
    document.querySelectorAll("[data-stil]").forEach((b) => b.addEventListener("click", () =>
      einstellen({ stil: b.dataset.stil })));
    document.querySelectorAll("[data-szenario]").forEach((b) => b.addEventListener("click", async () => {
      if (zustand.beschaeftigt) return;
      await neueSitzung();
      await senden((zustand.T.beispiele_saetze || {})[b.dataset.szenario]);
    }));
    $("#neu").addEventListener("click", () => { if (!zustand.beschaeftigt) neueSitzung(); });
    dateiKnopf($("#datei"), dateiSenden);
    dateiKnopf($("#foto"), dateiSenden);
    dateiKnopf($("#fall-datei"), fallLaden);
    mikroEinrichten();
  }

  async function einstellen(aenderung) {
    if (zustand.beschaeftigt || !zustand.sitzung) return;
    if ((aenderung.sprache || zustand.sprache) === zustand.sprache && (aenderung.stil || zustand.stil) === zustand.stil) {
      steuerungAnzeigen();
      return;
    }
    vorlesenBeenden();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    await laufen(() => api("POST", `/api/sitzung/${zustand.sitzung}/einstellungen`, aenderung));
  }

  async function start() {
    verbinden();
    try {
      await texteSetzen("de");
      zustand.demo = await api("GET", "/api/demo/dokumente");
      demoAnzeigen();
      await neueSitzung();
    } catch (err) {
      nachrichtAnzeigen("lotse", `Fehler / Error: ${err.message}`);
    }
  }

  start();
})();
