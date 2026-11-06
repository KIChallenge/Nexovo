import copy
import json
import re
import xml.etree.ElementTree as ET
from functools import lru_cache

import pytest

from lotse import config, katalog
from lotse.katalog import KatalogFehler
from lotse.models import FORMULARE, THEMEN
from lotse.slots import BUNDESLAENDER, SLOTS


def _roh() -> dict:
    return json.loads(katalog.DATEI.read_text(encoding="utf-8"))


def _termine_roh() -> dict:
    return json.loads(katalog.TERMIN_DATEI.read_text(encoding="utf-8"))


def _alle_quellen(l) -> list:
    """Alle Belege einer Leistung: Kernquellen, Nutzen, Einrichtungen, regionale Stellen, Trägerzuständigkeit."""
    quellen = list(l.quellen)
    if l.nutzen_quelle:
        quellen.append(l.nutzen_quelle)
    quellen += [e["quelle"] for e in l.einrichtungen]
    quellen += [r["quelle"] for r in l.regional.values()]
    quellen += [q for je_wert in l.stelle_belege.values() for q in je_wert.values()]
    return quellen


def _termin_quellen() -> list:
    return [q for anlass in katalog.TERMIN_ANLAESSE for q in katalog.termin_info(anlass).quellen] + [
        s["quelle"] for anlass in katalog.TERMIN_ANLAESSE for land in BUNDESLAENDER for s in katalog.termin_info(anlass, land).suche
    ]


# --- Struktur und Inhalt ----------------------------------------------------------------------

def test_katalog_hat_mindestens_20_leistungen_und_alle_themen():
    ids = {l.id for l in katalog.alle()}
    assert len(ids) >= 20
    assert set(THEMEN) <= ids


def test_alle_texte_zweisprachig_und_kurz_in_einfacher_sprache():
    for l in katalog.alle():
        for feld in (l.titel, l.kurz, l.details, l.stelle["name"]):
            assert feld["de"].strip() and feld["en"].strip(), l.id
        for eintrag in l.unterlagen + l.unterlagen_formular + l.voraussetzungen + l.schritte:
            assert eintrag["de"].strip() and eintrag["en"].strip(), l.id
        for sprache in ("de", "en"):
            saetze = re.findall(r"(?<!\d)[.!?](?:\s|$)", l.kurz[sprache])  # „18. Geburtstag“ ist kein Satzende
            assert len(saetze) <= 2, f"{l.id} kurz.{sprache} hat mehr als zwei Sätze"


def test_slot_ids_formulare_und_regionen_sind_gueltig():
    for l in katalog.alle():
        assert all(s in SLOTS for s in l.rueckfragen), l.id
        assert not any(SLOTS[s].sensibel for s in l.rueckfragen), l.id
        for slot_id, je_wert in l.stelle_nach.items():
            assert set(je_wert) <= set(SLOTS[slot_id].optionen), l.id
        assert l.formular is None or l.formular in FORMULARE, l.id
        assert set(l.regionen) <= set(BUNDESLAENDER), l.id
        assert set(l.regional) <= set(BUNDESLAENDER), l.id
        assert set(l.formular_regionen) <= set(BUNDESLAENDER), l.id
        assert all(set(e["regionen"]) <= set(BUNDESLAENDER) for e in l.einrichtungen), l.id
        assert l.termin_anlass is None or l.termin_anlass in SLOTS["termin.anlass"].optionen, l.id


def test_formular_leistungen_fuehren_antragsschritte_in_reihenfolge():
    mit_formular = [l for l in katalog.alle() if l.formular]
    assert {l.formular for l in mit_formular} == set(FORMULARE)
    for l in mit_formular:
        ids = [s["id"] for s in l.schritte]
        positionen = [ids.index(s) for s in katalog.ANTRAGSSCHRITTE]
        assert positionen == sorted(positionen), l.id


@pytest.mark.parametrize("szenario", katalog.SZENARIEN)
def test_jedes_szenario_hat_mindestens_fuenf_belegte_leistungen(szenario):
    liste = katalog.fuer_szenario(szenario)
    assert len(liste) >= 5
    for l in liste:
        assert szenario in l.szenarien
        assert l.quellen, l.id
        assert l.stelle["name"]["de"], l.id


def test_quellen_folgen_der_konvention():
    for l in katalog.alle():
        for q in _alle_quellen(l):
            assert len(q.zitat) <= 300, l.id
            assert q.zitat.strip(), (l.id, q.titel)
            if q.art == "recht":
                assert re.fullmatch(r"BGBl\. (I |II )?Nr\. \d+/\d{4}", q.fundstelle), (l.id, q.fundstelle)
                assert re.fullmatch(r".+ (§|Art\.|Anl\.) \w+", q.titel), (l.id, q.titel)
                assert q.datei.startswith("Rechtstexte/"), l.id
            elif q.art in ("serviceratgeber", "formular", "honorarordnung"):
                assert re.fullmatch(r"PDF-S\. \d+", q.fundstelle), (l.id, q.fundstelle)
            if q.art == "extern":
                assert q.url.startswith("https://") and not q.datei, l.id
                assert "abgerufen am" in q.fundstelle, (l.id, q.url)  # Prüfdatum sichtbar
            else:
                assert not q.url, (l.id, q.titel)  # extern ⇔ URL


def test_extern_belegte_leistung_ist_gekennzeichnet():
    park = katalog.leistung("bewegt_im_park")
    assert park.beleg == "extern"
    assert all(q.art == "extern" and q.url for q in park.quellen)
    for l in katalog.alle():
        if l.beleg == "lokal":
            assert all(q.art != "extern" for q in l.quellen), l.id


def test_jede_leistung_hat_stichworte_und_die_neuen_felder():
    for l in katalog.alle():
        assert l.stichworte, l.id
        assert all(s == s.strip().lower() for s in l.stichworte), l.id
        assert isinstance(l.einrichtungen, list) and isinstance(l.regional, dict), l.id


HAUPTLEISTUNGEN = ["pflegegeld", "pflegeberatung", "pflege_zu_hause", "hauskrankenpflege", "heilbehelfe_hilfsmittel", "rehabilitation",
                   "fahrtkosten", "rezeptgebuehrenbefreiung", "krankengeld"]


def test_nutzen_fuer_gesundheit_kind_und_hauptleistungen_mit_beleg():
    ids = {l.id for sz in ("gesundheit", "kind") for l in katalog.fuer_szenario(sz)} | set(HAUPTLEISTUNGEN)
    for lid in ids:
        l = katalog.leistung(lid)
        assert l.nutzen["de"].strip() and l.nutzen["en"].strip(), lid
        assert l.nutzen_quelle is not None and l.nutzen_quelle.zitat, lid
    for l in katalog.alle():
        assert bool(l.nutzen["de"]) == (l.nutzen_quelle is not None), l.id


def test_honorarordnungen_belegen_mindestens_drei_leistungen():
    mit_ho = {l.id for l in katalog.alle() if any(q.art == "honorarordnung" for q in l.quellen)}
    assert len(mit_ho) >= 3
    assert {"zahngesundheit_kinder", "vorsorgeuntersuchung"} <= mit_ho
    for l in katalog.alle():
        for q in l.quellen:
            if q.art == "honorarordnung":
                assert q.datei.startswith("Leistungskataloge/") and q.stand, l.id
                assert re.search(r"gültig ab|Stand", q.titel), q.titel  # Gültigkeit im Titel


# --- Leichte Sprache ----------------------------------------------------------------------------

def _belegt(l, sprache: str) -> str:
    return " ".join([l.kurz[sprache], l.details[sprache], *(t[sprache] for t in l.voraussetzungen + l.schritte)])


def test_jede_leistung_hat_leichte_sprache_nach_den_regeln():
    for l in katalog.alle():
        for sprache in ("de", "en"):
            assert katalog.pruefe_leichte_sprache(l.leicht[sprache], _belegt(l, sprache)) == [], (l.id, sprache)
            assert l.leicht[sprache] != l.kurz[sprache], (l.id, sprache)
    pg = katalog.leistung("pflegegeld")
    assert pg.to_dict()["leicht"] == pg.leicht


def test_leichte_sprache_behaelt_kernaussagen_und_hinweise():
    pg = katalog.leistung("pflegegeld").leicht
    assert "6 Monate" in pg["de"] and "Pension" in pg["de"] and "6 months" in pg["en"] and "pension" in pg["en"]
    park = katalog.leistung("bewegt_im_park").leicht  # extern belegt: Hinweis bleibt erhalten
    assert "nicht selbst geprüft" in park["de"] and "not checked" in park["en"]
    assert all("1450" in t for t in katalog.leistung("gesundheitsberatung_1450").leicht.values())
    rg = katalog.leistung("rezeptgebuehrenbefreiung").leicht
    assert "7,55 €" in rg["de"] and "€7.55" in rg["en"]


_BELEGT = "Pflegegeld gibt es ab Stufe 1, wenn die Pflege voraussichtlich sechs Monate dauert."


@pytest.mark.parametrize("text, fehler", [
    ("Pflegegeld gibt es jeden Monat.", "Sätze"),
    ("Eins. Zwei. Drei. Vier. Fünf.", "Sätze"),
    ("Pflegegeld ist Geld für Menschen, die wegen einer Krankheit lange viel Hilfe und Pflege brauchen. Sie stellen den Antrag.", "Wörter"),
    ("Sie brauchen z. B. Hilfe. Sie stellen den Antrag.", "Abkürzung"),
    ("Sie brauchen z.B. Hilfe. Sie stellen den Antrag.", "Abkürzung"),
    ("Fragen Sie die PVA bzw. die SVS. Sie stellen den Antrag.", "Abkürzung"),
    ("Es gibt u. a. Geld. Sie stellen den Antrag.", "Abkürzung"),
    ("Sie brauchen ggf. Hilfe. Sie stellen den Antrag.", "Abkürzung"),
    ("Alles inkl. Pflege. Sie stellen den Antrag.", "Abkürzung"),
    ("Es gibt Geld, d. h. Hilfe. Sie stellen den Antrag.", "Abkürzung"),
    ("Es gibt Geld, Hilfe usw. Sie stellen den Antrag.", "Abkürzung"),
    ("There is money, e.g. for care. You apply.", "Abkürzung"),
    ("Die Pflege dauert 12 Monate. Sie stellen den Antrag.", "Zahl"),
    ("Die Pflege dauert sieben Monate. Sie stellen den Antrag.", "Zahl"),
    ("Sie stellen den Antrag. Die Stelle hilft", "Satzzeichen"),
], ids=["ein_satz", "fuenf_saetze", "satz_zu_lang", "z_b", "z_b_ohne_leerzeichen", "bzw", "u_a", "ggf", "inkl", "d_h", "usw", "e_g",
        "neue_ziffer", "neues_zahlwort", "ohne_satzzeichen"])
def test_pruefe_leichte_sprache_findet_verstoesse(text, fehler):
    verstoesse = katalog.pruefe_leichte_sprache(text, _BELEGT)
    assert any(fehler in v for v in verstoesse), verstoesse


def test_pruefe_leichte_sprache_erlaubt_belegte_zahlen_als_ziffer():
    assert katalog.pruefe_leichte_sprache("Die Pflege dauert mindestens 6 Monate. Pflegegeld gibt es ab Stufe 1.", _BELEGT) == []
    assert katalog.pruefe_leichte_sprache("Brauchen Sie Hilfe? Dann rufen Sie an!", "") == []
    assert katalog.pruefe_leichte_sprache("Rufen Sie an.", "", saetze=(1, 2)) == []


# --- Pflegegeld: Zuständigkeit, Rückfragen, Rechtsstand ----------------------------------------

def test_pflegegeld_rueckfragen_und_formular():
    pg = katalog.leistung("pflegegeld")
    assert pg.rueckfragen == ["versicherung.pension", "pflege.antragsart"]
    assert pg.formular == "PAL080"


def test_pflegegeld_stelle_haengt_vom_pensionstraeger_ab():
    pg = katalog.leistung("pflegegeld")
    assert "PVA" in pg.stelle_fuer({"versicherung.pension": "PVA"})["de"]
    assert "SVS" in pg.stelle_fuer({"versicherung.pension": "SVS"})["de"]
    assert "BVAEB" in pg.stelle_fuer({"versicherung.pension": "BVAEB"})["en"]
    assert "ohne Pension" in pg.stelle_fuer({"versicherung.pension": "keine"})["de"]
    assert pg.stelle_fuer({}) == pg.stelle["name"]
    assert any(q.titel == "BPGG § 22" for q in pg.quellen)


def test_pflegegeld_nennt_betraege_2026_statt_grundbetraegen():
    details = katalog.leistung("pflegegeld").details["de"]
    assert "592,60 €" in details and "206,20 €" in details and "2.214,80 €" in details
    assert "451,80" not in details
    vo = [q for q in katalog.leistung("pflegegeld").quellen if q.fundstelle == "BGBl. II Nr. 263/2025"]
    assert vo and "592,60" in " ".join(q.zitat for q in vo)


# --- Trägerzuständigkeit SVS/BVAEB (extern belegt) ---------------------------------------------

TRAEGERABHAENGIG = ["rehabilitation", "kur", "fahrtkosten", "rezeptgebuehrenbefreiung", "hauskrankenpflege", "heilbehelfe_hilfsmittel",
                    "krankengeld", "wochengeld", "kinderbetreuungsgeld", "unterstuetzungsfonds"]


@pytest.mark.parametrize("lid", TRAEGERABHAENGIG)
def test_svs_und_bvaeb_zustaendigkeit_ist_extern_belegt(lid):
    l = katalog.leistung(lid)
    for traeger, domain in (("SVS", "https://www.svs.at/"), ("BVAEB", "https://www.bvaeb.at/")):
        werte = {"versicherung.krankenversicherung": traeger}
        assert traeger in l.stelle_fuer(werte)["de"] and traeger in l.stelle_fuer(werte)["en"]
        beleg = l.stelle_beleg_fuer(werte)
        assert beleg is not None and beleg.art == "extern" and beleg.url.startswith(domain), (lid, traeger)
    assert l.stelle_beleg_fuer({}) is None
    assert l.stelle_beleg_fuer({"versicherung.krankenversicherung": "unbekannt"}) is None
    assert "www.svs.at" in l.kontakt_fuer({"versicherung.krankenversicherung": "SVS"})
    assert "www.bvaeb.at" in l.kontakt_fuer({"versicherung.krankenversicherung": "BVAEB"})
    assert l.kontakt_fuer({}) == l.stelle["kontakt"]
    assert l.kontakt_fuer({"versicherung.krankenversicherung": "ÖGK"}) == l.stelle["kontakt"]  # ÖGK ohne eigenen Kontakt


def test_kontakt_folgt_der_aufgeloesten_stelle():
    reha = katalog.leistung("rehabilitation")
    assert reha.stelle["kontakt"] == "www.oegk.at"
    assert reha.kontakt_fuer({"versicherung.krankenversicherung": "SVS"}) == "SVS: Tel. 050 808 808 · www.svs.at"
    assert "www.oegk.at" not in reha.kontakt_fuer({"versicherung.krankenversicherung": "SVS"})
    unbekannt = reha.kontakt_fuer({"versicherung.krankenversicherung": "unbekannt"})
    assert all(d in unbekannt for d in ("www.oegk.at", "www.svs.at", "www.bvaeb.at"))
    pg = katalog.leistung("pflegegeld")
    assert "www.pv.at" in pg.kontakt_fuer({"versicherung.pension": "PVA"})
    assert "www.pv.at" in pg.kontakt_fuer({"versicherung.pension": "keine"})  # ohne Pension: PVA (BPGG § 22)
    assert "www.svs.at" in pg.kontakt_fuer({"versicherung.pension": "SVS"})
    assert "www.bvaeb.at" in katalog.leistung("ausgleichszulage").kontakt_fuer({"versicherung.pension": "BVAEB"})
    for l in katalog.alle():
        for je_wert in l.stelle_kontakte.values():
            assert all(k.strip() for k in je_wert.values()), l.id


# Telefonnummern und Websites in stelle_nach.kontakt stehen in diesen lokalen Quellen (Adressteile der Honorarordnung,
# Adressseite PAL 080, Serviceratgeber S. 42).
_KONTAKT_BELEGE = [
    ("Leistungskataloge/Zahnärzte Honorarordnung_2026_aktuellste_Version_MAI_070526.pdf", "PDF-S. 47"),
    ("Anträge und Formulare/PAL080_0125_Mpfl_052026.pdf", "PDF-S. 8"),
    ("Leistungskataloge/Serviceratgeber-2026_Broschuere_A5_OEAM_99-19_klein_korr.pdf", "PDF-S. 42"),
]


@pytest.mark.daten
def test_kontakte_der_traeger_stehen_in_lokalen_quellen():
    belegtext = "".join(_quelltext(datei, seite) for datei, seite in _KONTAKT_BELEGE)
    fehlend = []
    for l in katalog.alle():
        for je_wert in l.stelle_kontakte.values():
            for kontakt in je_wert.values():
                for teil in re.findall(r"Tel\. ([+\d() ]+\d)|(www\.[a-z0-9.-]+)", kontakt):
                    angabe = teil[0] or teil[1]
                    if _kern(angabe) not in belegtext:
                        fehlend.append((l.id, angabe))
    assert not fehlend, fehlend


def test_formularunterlagen_getrennt_von_allgemeinen_unterlagen():
    pzh = katalog.leistung("pflege_zu_hause")
    assert len(pzh.unterlagen_formular) == 5
    assert all("FSW" in u["de"] and "FSW" in u["en"] for u in pzh.unterlagen_formular)
    assert not any("FSW" in u["de"] for u in pzh.unterlagen)
    for l in katalog.alle():
        assert not l.unterlagen_formular or l.formular, l.id


def test_keine_lokal_nicht_geprueft_formulierung_bei_traegern():
    for l in katalog.alle():
        texte = [t[sp] for je_wert in l.stelle_nach.values() for t in je_wert.values() for sp in ("de", "en")]
        texte += [l.stelle["hinweis"]["de"], l.stelle["hinweis"]["en"]]
        assert not any("nicht geprüft" in t or "not verified locally" in t for t in texte), l.id


# --- Szenario- und Regionsfilter ----------------------------------------------------------------

def test_regionalfilter_entfernt_wiener_angebote_fuer_tirol():
    for szenario in katalog.SZENARIEN:
        tirol = katalog.fuer_szenario(szenario, "Tirol")
        assert all(l.oesterreichweit for l in tirol), szenario
    pflege_tirol = {l.id for l in katalog.fuer_szenario("pflege", "Tirol")}
    assert {"pflegegeld", "pflege_zu_hause"} <= pflege_tirol  # mobile Dienste jetzt österreichweit
    assert not {"senioren_wg", "wohn_und_pflegehaus"} & pflege_tirol
    assert "mobile_fruehfoerderung" not in {l.id for l in katalog.fuer_szenario("kind", "Tirol")}


def test_regionalfilter_behaelt_wiener_angebote_fuer_wien():
    wien = {l.id for l in katalog.fuer_szenario("pflege", "wien")}  # Groß-/Kleinschreibung egal
    assert {"pflege_zu_hause", "senioren_wg", "wohn_und_pflegehaus", "pflegegeld"} <= wien


def test_ohne_bundesland_alle_und_oesterreichweite_zuerst():
    liste = katalog.fuer_szenario("pflege")
    ids = [l.id for l in liste]
    assert "pflege_zu_hause" in ids and ids[0] == "pflegegeld"
    regional_ab = next(i for i, l in enumerate(liste) if not l.oesterreichweit)
    assert all(not l.oesterreichweit for l in liste[regional_ab:])


def test_entlassung_beginnt_mit_den_themen_der_dokumentfunktion():
    ids = [l.id for l in katalog.fuer_szenario("entlassung", "Wien")][:len(THEMEN)]
    assert set(THEMEN) == set(ids)


def test_unbekannte_werte_werden_abgelehnt():
    with pytest.raises(ValueError):
        katalog.fuer_szenario("urlaub")
    with pytest.raises(ValueError):
        katalog.fuer_szenario("pflege", "Bayern")
    with pytest.raises(KeyError):
        katalog.leistung("gibt_es_nicht")


def test_fsw_formulare_gelten_nur_in_wien():
    for l in katalog.alle():
        if l.formular and l.formular.startswith("FSW_"):
            assert l.formular_regionen == ["Wien"], l.id
        else:
            assert l.formular_regionen == [], l.id
    pzh = katalog.leistung("pflege_zu_hause")
    assert pzh.oesterreichweit and pzh.formular == "FSW_FOERDERUNG" and pzh.formular_regionen == ["Wien"]


@pytest.mark.parametrize("land", BUNDESLAENDER)
@pytest.mark.parametrize("lid", ["pflege_zu_hause", "sozialhilfe"])
def test_regionale_stelle_fuer_alle_neun_laender(lid, land):
    r = katalog.leistung(lid).regional_fuer(land)
    assert r is not None
    assert r["stelle"]["de"].strip() and r["stelle"]["en"].strip()
    assert r["url"].startswith("https://")
    if lid == "pflege_zu_hause" and land == "Wien":
        assert r["quelle"].art == "formular" and "FSW" in r["quelle"].titel  # lokales FSW-Formular
    else:
        assert r["quelle"].art == "extern" and r["quelle"].url.startswith("https://")


def test_regional_fuer_ohne_land_unbekanntes_land_und_schreibweise():
    pzh = katalog.leistung("pflege_zu_hause")
    assert pzh.regional_fuer(None) is None and pzh.regional_fuer("") is None
    assert pzh.regional_fuer("niederösterreich") == pzh.regional_fuer("Niederösterreich")
    assert katalog.leistung("pflegegeld").regional_fuer("Tirol") is None
    with pytest.raises(ValueError):
        pzh.regional_fuer("Bayern")


@pytest.mark.parametrize("land", BUNDESLAENDER)
def test_einrichtungen_fuer_land_zuerst_und_ohne_fremde_laender(land):
    for lid in ("kur", "rezeptgebuehrenbefreiung", "vorsorgeuntersuchung", "pflegegeld"):
        liste = katalog.leistung(lid).einrichtungen_fuer(land)
        assert liste, lid
        assert all(not e["regionen"] or land in e["regionen"] for e in liste), (lid, land)
        eigene = [i for i, e in enumerate(liste) if e["regionen"]]
        bundesweit = [i for i, e in enumerate(liste) if not e["regionen"]]
        assert eigene and (not bundesweit or max(eigene) < min(bundesweit)), (lid, land)
    kundenservice = katalog.leistung("kur").einrichtungen_fuer(land)[0]
    assert kundenservice["name"]["de"].startswith("ÖGK-Kundenservice") and "Tel." in kundenservice["kontakt"]


def test_einrichtungen_ohne_land_nur_oesterreichweit():
    for l in katalog.alle():
        assert all(not e["regionen"] for e in l.einrichtungen_fuer(None)), l.id
    assert any(e["url"] for e in katalog.leistung("rehabilitation").einrichtungen_fuer(None))


def test_einrichtungen_wo_ein_ort_zaehlt():
    for lid in ("rehabilitation", "kur", "vorsorgeuntersuchung", "impfungen", "pflegeberatung", "pflege_zu_hause", "eltern_kind_pass",
                "familienberatung", "kontrolltermine", "zahngesundheit_kinder"):
        assert katalog.leistung(lid).einrichtungen, lid


# --- Neue Leistungen und Szenario „unterstuetzung“ ---------------------------------------------

def test_kontrolltermine_als_administrative_leistung():
    kt = katalog.leistung("kontrolltermine")
    assert {"entlassung", "pflege"} <= set(kt.szenarien)
    assert kt.termin_anlass == "kontrolle"
    assert "kontrolltermine" in THEMEN


def test_szenario_unterstuetzung_hat_die_sozialen_leistungen():
    ids = [l.id for l in katalog.fuer_szenario("unterstuetzung")]
    assert len(ids) >= 6
    assert {"sozialhilfe", "ausgleichszulage", "familienberatung", "arbeitslosengeld", "notstandshilfe", "unterstuetzungsfonds",
            "rezeptgebuehrenbefreiung", "schuldenberatung"} <= set(ids)
    assert katalog.leistung("ausgleichszulage").beleg == "lokal"  # ASVG/GSVG/BSVG im Korpus
    assert katalog.leistung("sozialhilfe").beleg == "extern"  # Landesrecht nicht im Korpus


def test_termin_anlaesse_passen_zu_den_leistungen():
    erwartet = {"vorsorgeuntersuchung": "vorsorge", "brustkrebs_frueherkennung": "vorsorge", "impfungen": "impfung",
                "zahngesundheit_kinder": "zahn", "eltern_kind_pass": "kind", "kontrolltermine": "kontrolle",
                "gesundheitsberatung_1450": "beschwerden", "familienberatung": "beratung"}
    for lid, anlass in erwartet.items():
        assert katalog.leistung(lid).termin_anlass == anlass, lid


# --- Validierung beim Laden -------------------------------------------------------------------

def _mit(aenderung) -> dict:
    daten = copy.deepcopy(_roh())
    aenderung(daten["leistungen"][0])
    return daten


_QUELLE_LOKAL = {"art": "serviceratgeber", "titel": "SR", "fundstelle": "PDF-S. 1", "datei": "x.pdf", "zitat": "z", "stand": "", "url": ""}


@pytest.mark.parametrize("aenderung", [
    lambda l: l.update(formular="GIBT_ES_NICHT"),
    lambda l: l.update(rueckfragen=["person.lieblingsfarbe"]),
    lambda l: l.update(rueckfragen=["bank.iban"]),  # sensibel
    lambda l: l["kurz"].pop("en"),
    lambda l: l.update(regionen=["Bayern"]),
    lambda l: l.update(quellen=[]),
    lambda l: l["quellen"].append({"art": "extern", "titel": "Web", "url": "https://example.org", "zitat": "x"}),  # beleg bleibt „lokal“
    lambda l: l["stelle_nach"]["versicherung.pension"].update({"AUVA": {"de": "x", "en": "x"}}),
    lambda l: l.update(schritte=[s for s in l["schritte"] if s["id"] != "antrag_unterschreiben"]),
    lambda l: l.pop("stichworte"),
    lambda l: l.update(stichworte=["Pflegegeld"]),
    lambda l: l.update(nutzen_quelle=None),  # nutzen ohne Beleg
    lambda l: l.update(termin_anlass="urlaub"),
    lambda l: l.update(formular_regionen=["Bayern"]),
    lambda l: l.update(regional={"Bayern": {"stelle": {"de": "x", "en": "x"}, "quelle": _QUELLE_LOKAL}}),
    lambda l: l.update(regional={"Tirol": {"stelle": {"de": "x", "en": "x"}}}),  # ohne Quelle
    lambda l: l["einrichtungen"].append({"name": {"de": "x", "en": "x"}, "regionen": [], "quelle": {"art": "extern", "titel": "Web", "zitat": "x"}}),
    lambda l: l["einrichtungen"].append({"name": {"de": "x", "en": "x"}, "regionen": [], "quelle": {**_QUELLE_LOKAL, "url": "https://example.org"}}),
    lambda l: l["stelle_nach"]["versicherung.pension"]["SVS"].update(quelle={"art": "extern", "titel": "SVS", "url": "", "zitat": "x"}),
    lambda l: l["stelle_nach"]["versicherung.pension"]["SVS"].update(kontakt=""),
    lambda l: l["stelle_nach"]["versicherung.pension"]["SVS"].update(kontakt=50808808),
    lambda l: l.pop("unterlagen_formular"),
    lambda l: l.update(unterlagen_formular=[{"de": "nur deutsch"}]),
    lambda l: l.pop("leicht"),
    lambda l: l["leicht"].pop("en"),
    lambda l: l["leicht"].update(de="Pflegegeld gibt es jeden Monat."),  # nur ein Satz
    lambda l: l["leicht"].update(en="Care allowance is money for care and help that you get every month from the institution. You apply."),
    lambda l: l["leicht"].update(de="Pflegegeld gibt es z. B. für Pflege. Sie stellen den Antrag."),
    lambda l: l["leicht"].update(de="Pflegegeld gibt es ab 77 Stunden Pflege. Sie stellen den Antrag."),  # Zahl nicht belegt
], ids=["formular", "slot", "sensibler_slot", "ohne_en", "region", "ohne_quelle", "extern_bei_lokal", "slot_option", "antragsschritt",
        "ohne_stichworte", "stichwort_gross", "nutzen_ohne_quelle", "termin_anlass", "formular_region", "regional_land", "regional_ohne_quelle",
        "einrichtung_extern_ohne_url", "lokal_mit_url", "stelle_nach_beleg", "kontakt_leer", "kontakt_kein_text", "ohne_unterlagen_formular",
        "unterlagen_formular_ohne_en", "ohne_leicht", "leicht_ohne_en", "leicht_ein_satz", "leicht_satz_zu_lang", "leicht_abkuerzung",
        "leicht_neue_zahl"])
def test_validierung_lehnt_fehlerhafte_eintraege_ab(aenderung):
    assert _roh()["leistungen"][0]["id"] == "pflegegeld"
    with pytest.raises(KatalogFehler):
        katalog._baue(_mit(aenderung))


def test_validierung_verlangt_szenariozuordnung():
    daten = copy.deepcopy(_roh())
    for liste in daten["reihenfolge"].values():
        if "kur" in liste:
            liste.remove("kur")
    with pytest.raises(KatalogFehler):
        katalog._baue(daten)


@pytest.mark.parametrize("feld, wert", [("formular_regionen", ["Wien"]), ("unterlagen_formular", [{"de": "x", "en": "x"}])])
def test_validierung_formularfelder_nur_mit_formular(feld, wert):
    daten = copy.deepcopy(_roh())
    eintrag = next(l for l in daten["leistungen"] if l["formular"] is None)
    eintrag[feld] = wert
    with pytest.raises(KatalogFehler):
        katalog._baue(daten)


@pytest.mark.parametrize("aenderung", [
    lambda t: t["anlaesse"].pop("zahn"),
    lambda t: t["anlaesse"]["vorsorge"]["suche"].append("gibt_es_nicht"),
    lambda t: t["anlaesse"]["impfung"].update(wo_quellen=[]),
    lambda t: t["anlaesse"]["kind"]["hinweise"][0].pop("quelle"),
    lambda t: t["suche"]["oegk_termin"].update(url=""),
    lambda t: t["suche"]["oegk_termin"].update(regionen=["Bayern"]),
    lambda t: t["beschwerden_hinweis"].pop("quelle"),
], ids=["anlass_fehlt", "suche_unbekannt", "wo_ohne_beleg", "hinweis_ohne_beleg", "suche_ohne_url", "suche_region", "beschwerden_ohne_beleg"])
def test_termine_validierung_lehnt_fehlerhafte_eintraege_ab(aenderung):
    daten = copy.deepcopy(_termine_roh())
    aenderung(daten)
    with pytest.raises(KatalogFehler):
        katalog._baue_termine(daten)


# --- Szenario-Erkennung -----------------------------------------------------------------------

@pytest.mark.parametrize("text, erwartet", [
    ("Meine Mutter ist chronisch krank und kommt allein nicht mehr zurecht. Was kann ich tun?", "pflege"),
    ("Ich möchte etwas für meine Gesundheit tun.", "gesundheit"),
    ("Ich habe einen Befund/Entlassungsbrief bekommen – was muss ich jetzt erledigen?", "entlassung"),
    ("Ich habe ein Kind und möchte wissen, welche Angebote es gibt.", "kind"),
    ("My mother is chronically ill and can no longer cope on her own. What can I do?", "pflege"),
    ("I want to do something for my health.", "gesundheit"),
    ("I received a medical report / discharge letter – what do I have to do now?", "entlassung"),
    ("I have a child and would like to know which services are available.", "kind"),
    ("Meine Mutter braucht jetzt Hilfe, was muss ich denn da machen?", "pflege"),
    ("Ich habe einen Entlassungsbrief bekommen", "entlassung"),
    ("my mother needs care", "pflege"),
])
def test_erkenne_szenarien_use_case_saetze(text, erwartet):
    assert katalog.erkenne_szenarien(text)[0] == erwartet


# Umgangssprache, österreichischer Dialekt und einfaches Englisch (Regelmodus ohne KI)
UMGANGSSPRACHE = [
    ("Mama schafft's daheim nimma allein, was tun?", "pflege"),
    ("Mei Oma kummt nimma zurecht", "pflege"),
    ("Da Papa kann si nimma söba woschen, wer hüft uns do?", "pflege"),
    ("Mei Opa is dement und vergisst ois", "pflege"),
    ("D'Tochter hilft eh, aber da Papa kummt nimma zurecht", "pflege"),
    ("Bin grad aus'm Spital raus, was muss i jetzt alles erledigen?", "entlassung"),
    ("Mei Vater kummt nächste Woch ausm Krankenhaus hoam", "entlassung"),
    ("Nach da OP brauch i a Reha, wie geht des?", "entlassung"),
    ("Mei Bua is jetzt 3, wos gibt's do fia Angebote?", "kind"),
    ("Mia kriagn a Baby, wos steht uns zua?", "kind"),
    ("Mei Madl is 15 und braucht a Zahnspange", "kind"),
    ("I mecht wos fia mei Gsundheit tuan", "gesundheit"),
    ("I wü mehr Sport mochn und gsünder essn", "gesundheit"),
    ("Wo kann i mi impfen lassen?", "gesundheit"),
    ("I bin arbeitslos und hab ka Göd mehr", "unterstuetzung"),
    ("Ich kann mir die Miete kaum noch leisten – welche Unterstützung gibt es?", "unterstuetzung"),
    ("Ich kann die Miete nicht zahlen", "unterstuetzung"),
    ("Als Alleinerziehende komm ich mit dem Geld nicht aus", "unterstuetzung"),
    ("Meine Pension reicht nicht zum Leben", "unterstuetzung"),
    ("My mum can't manage at home anymore", "pflege"),
    ("Grandma can't live on her own anymore", "pflege"),
    ("My dad came home from hospital yesterday, what do we need to organise?", "entlassung"),
    ("I was just discharged from hospital, what now?", "entlassung"),
    ("We're expecting a baby, what support is there?", "kind"),
    ("I'd like to get healthier and fitter", "gesundheit"),
    ("I can barely afford my rent – what support is available?", "unterstuetzung"),
    ("I lost my job and have debts", "unterstuetzung"),
]


@pytest.mark.parametrize("text, erwartet", UMGANGSSPRACHE)
def test_erkenne_szenarien_umgangssprache_dialekt_englisch(text, erwartet):
    assert katalog.erkenne_szenarien(text)[0] == erwartet


@pytest.mark.parametrize("text", [
    "Ich bin die Tochter und kümmere mich um meinen Vater, der allein nicht mehr zurechtkommt.",
    "Meine Tochter und ich pflegen meine Mutter zu Hause.",
    "Als Sohn möchte ich Pflegegeld für meine Mutter beantragen.",
    "I am her daughter and I look after my father.",
    "D'Tochter hilft eh, aber da Papa kummt nimma zurecht",
])
def test_tochter_als_helfende_person_loest_kein_kind_szenario_aus(text):
    szenarien = katalog.erkenne_szenarien(text)
    assert "kind" not in szenarien
    assert szenarien[0] == "pflege"


def test_tochter_mit_altersangabe_ist_kind_szenario():
    assert katalog.erkenne_szenarien("Meine Tochter ist 4 Jahre alt, gibt es Angebote?") == ["kind"]
    assert katalog.erkenne_szenarien("My little son is 2 – what is available?") == ["kind"]


@pytest.mark.parametrize("text", [
    "Was ist der Unterschied zwischen Kur und Reha?",
    "What is the difference between rehab and a spa stay?",
    "Was ist eine Kur?",
])
def test_sachfrage_oeffnet_kein_szenario(text):
    assert katalog.erkenne_szenarien(text) == []


def test_mehrere_szenarien_nach_staerke_sortiert_und_leertext():
    szenarien = katalog.erkenne_szenarien("Ich wurde aus dem Spital entlassen und brauche Reha; außerdem habe ich ein Baby.")
    assert szenarien[:2] == ["entlassung", "kind"]
    assert katalog.erkenne_szenarien("") == []
    assert katalog.erkenne_szenarien("Wie spät ist es?") == []
    assert katalog.erkenne_szenarien("Meine Mutter ist pflegebedürftig, wie viel Geld bekommt sie?")[0] == "pflege"


# --- Passende Leistungen und Vorsorgehinweise ------------------------------------------------

@pytest.mark.parametrize("text, erwartet", [
    ("Wer zahlt mir die Fahrt zur Bestrahlung?", "fahrtkosten"),
    ("Who pays for transport to radiotherapy?", "fahrtkosten"),
    ("Zahnspange für mein Kind", "zahngesundheit_kinder"),
    ("Pflegegeld beantragen", "pflegegeld"),
    ("Ich brauche einen Rollstuhl", "heilbehelfe_hilfsmittel"),
    ("Kann ich mich von der Rezeptgebühr befreien lassen?", "rezeptgebuehrenbefreiung"),
    ("Wo bekomme ich Heimhilfe?", "pflege_zu_hause"),
    ("Brauche ich für den Kontrolltermin eine Überweisung?", "kontrolltermine"),
    ("Ich bin arbeitslos geworden", "arbeitslosengeld"),
    ("Ich habe Schulden", "schuldenberatung"),
    ("Mammografie Termin", "brustkrebs_frueherkennung"),
])
def test_passende_leistungen_bestes_ergebnis(text, erwartet):
    treffer = katalog.passende_leistungen(text)
    assert treffer and treffer[0][0].id == erwartet


def test_passende_leistungen_sortiert_begrenzt_und_leer():
    treffer = katalog.passende_leistungen("Fahrt zur Reha, Pflegegeld und Rollstuhl", k=2)
    assert len(treffer) == 2
    assert all(score > 0 for _, score in treffer)
    assert treffer[0][1] >= treffer[1][1]
    assert katalog.passende_leistungen("Wie spät ist es?") == []
    assert katalog.passende_leistungen("") == []
    assert katalog.passende_leistungen("Pflegegeld", k=0) == []


@pytest.mark.parametrize("text, erwartet", [
    ("Mein Vater hatte Darmkrebs. Welche Vorsorgeuntersuchungen gibt es?", ["vorsorgeuntersuchung"]),
    ("Meine Mutter hatte Brustkrebs.", ["brustkrebs_frueherkennung", "vorsorgeuntersuchung"]),
    ("In meiner Familie gibt es Herzinfarkte.", ["vorsorgeuntersuchung"]),
    ("Mei Papa hot Zucker", ["vorsorgeuntersuchung"]),
    ("My mother had breast cancer – which screening is there?", ["brustkrebs_frueherkennung", "vorsorgeuntersuchung"]),
    ("Ich habe Diabetes – gibt es ein Programm der ÖGK?", []),  # keine familiäre Erwähnung
    ("Meine Mutter braucht Pflegegeld.", []),
])
def test_vorsorge_hinweise_nur_programme_ohne_risikoaussage(text, erwartet):
    assert katalog.vorsorge_hinweise(text) == erwartet


def test_vorsorge_programme_nennen_ihren_inhalt_laut_quelle():
    vu = " ".join(q.zitat for q in katalog.leistung("vorsorgeuntersuchung").quellen)
    assert "Herz-Kreislauf" in vu or "Darm" in vu
    bk = " ".join(q.zitat for q in katalog.leistung("brustkrebs_frueherkennung").quellen)
    assert re.search(r"45|74", bk)


# --- Terminvorbereitung -------------------------------------------------------------------------

@pytest.mark.parametrize("anlass", katalog.TERMIN_ANLAESSE)
def test_termin_info_fuer_jeden_anlass(anlass):
    info = katalog.termin_info(anlass)
    assert info.anlass == anlass
    assert info.wo["de"].strip() and info.wo["en"].strip()
    assert info.quellen
    assert info.suche and all(s["url"].startswith("https://") and s["quelle"] for s in info.suche)
    assert all(not s["regionen"] for s in info.suche)  # ohne Land nur österreichweite Dienste
    for h in info.hinweise:
        assert h["de"].strip() and h["en"].strip()
    if anlass == "beschwerden":
        assert "1450" in info.beschwerden_hinweis["de"] and "1450" in info.beschwerden_hinweis["en"]
        assert any(q.fundstelle == "PDF-S. 42" for q in info.quellen)
    else:
        assert info.beschwerden_hinweis == {"de": "", "en": ""}


@pytest.mark.parametrize("land", BUNDESLAENDER)
def test_termin_info_mit_land_zeigt_landesdienste_zuerst(land):
    info = katalog.termin_info("vorsorge", land.upper())
    assert land in info.suche[0]["regionen"]
    assert any(s["regionen"] == [land] and "Arztsuche" in s["name"]["de"] for s in info.suche)
    assert all(not s["regionen"] or land in s["regionen"] for s in info.suche)
    eigene = [i for i, s in enumerate(info.suche) if s["regionen"]]
    assert max(eigene) < min(i for i, s in enumerate(info.suche) if not s["regionen"])


def test_termin_info_hinweise_ecard_und_ueberweisung():
    alle = " ".join(h["de"] for a in katalog.TERMIN_ANLAESSE for h in katalog.termin_info(a).hinweise)
    assert "e-card" in alle and "Überweisung" in alle and "Befunde" in alle


def test_termin_info_lehnt_unbekanntes_ab():
    with pytest.raises(ValueError):
        katalog.termin_info("urlaub")
    with pytest.raises(ValueError):
        katalog.termin_info("vorsorge", "Bayern")


# --- Zitate gegen die SV-Box-Quellen ----------------------------------------------------------

def _kern(text: str) -> str:
    # Vergleich ohne Leerraum und Bindestriche (Zeilenumbrüche und Silbentrennung im PDF-Text)
    return re.sub(r"[\s\-\u00ad\u2010\u2011]+", "", text)


@lru_cache(maxsize=None)
def _quelltext(datei: str, fundstelle: str) -> str:
    pfad = config.datei(datei)
    if datei.startswith("Rechtstexte/"):
        nutzdaten = ET.parse(pfad).getroot().find(".//nutzdaten")
        return _kern("".join(nutzdaten.itertext()))
    from pypdf import PdfReader

    seite = int(fundstelle.removeprefix("PDF-S. "))
    return _kern(PdfReader(pfad).pages[seite - 1].extract_text() or "")


@pytest.mark.daten
def test_jedes_lokale_zitat_steht_auf_der_genannten_seite():
    fehlend = []
    quellen = [(l.id, q) for l in katalog.alle() for q in _alle_quellen(l)] + [("termine", q) for q in _termin_quellen()]
    for wo, q in quellen:
        if q.art == "extern":
            continue
        assert config.datei(q.datei).is_file(), q.datei
        if _kern(q.zitat) not in _quelltext(q.datei, q.fundstelle):
            fehlend.append((wo, q.titel, q.fundstelle, q.zitat[:60]))
    assert not fehlend, fehlend


@pytest.mark.daten
def test_rechtsquellen_stand_und_bgbl_passen_zur_datei():
    for l in katalog.alle():
        for q in _alle_quellen(l):
            if q.art != "recht":
                continue
            *_, inkraft = q.datei.removesuffix(".xml").split("=")
            assert q.stand == ("" if inkraft.startswith("1111") else inkraft), q.datei
            pub = next(ET.parse(config.datei(q.datei)).getroot().iter("puborgan")).attrib
            assert f"Nr. {pub['nrpuborg']}/{pub['jahrgang']}" in q.fundstelle, q.datei
