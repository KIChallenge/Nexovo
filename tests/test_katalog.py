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


# --- Struktur und Inhalt ----------------------------------------------------------------------

def test_katalog_hat_mindestens_20_leistungen_und_alle_themen():
    ids = {l.id for l in katalog.alle()}
    assert len(ids) >= 20
    assert set(THEMEN) <= ids


def test_alle_texte_zweisprachig_und_kurz_in_einfacher_sprache():
    for l in katalog.alle():
        for feld in (l.titel, l.kurz, l.details, l.stelle["name"]):
            assert feld["de"].strip() and feld["en"].strip(), l.id
        for eintrag in l.unterlagen + l.voraussetzungen + l.schritte:
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
        for q in l.quellen:
            assert len(q.zitat) <= 300, l.id
            if q.art == "recht":
                assert re.fullmatch(r"BGBl\. (I |II )?Nr\. \d+/\d{4}", q.fundstelle), (l.id, q.fundstelle)
                assert re.fullmatch(r".+ (§|Art\.|Anl\.) \w+", q.titel), (l.id, q.titel)
                assert q.datei.startswith("Rechtstexte/"), l.id
            elif q.art in ("serviceratgeber", "formular"):
                assert re.fullmatch(r"PDF-S\. \d+", q.fundstelle), (l.id, q.fundstelle)
            elif q.art == "extern":
                assert q.url.startswith("https://"), l.id


def test_extern_belegte_leistung_ist_gekennzeichnet():
    park = katalog.leistung("bewegt_im_park")
    assert park.beleg == "extern"
    assert all(q.art == "extern" and q.url for q in park.quellen)
    for l in katalog.alle():
        if l.beleg == "lokal":
            assert all(q.art != "extern" for q in l.quellen), l.id


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


# --- Szenario- und Regionsfilter ----------------------------------------------------------------

def test_regionalfilter_entfernt_fsw_angebote_fuer_tirol():
    for szenario in katalog.SZENARIEN:
        tirol = katalog.fuer_szenario(szenario, "Tirol")
        assert all(l.oesterreichweit for l in tirol), szenario
    pflege_tirol = {l.id for l in katalog.fuer_szenario("pflege", "Tirol")}
    assert "pflegegeld" in pflege_tirol
    assert not {"pflege_zu_hause", "senioren_wg", "wohn_und_pflegehaus"} & pflege_tirol
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


# --- Validierung beim Laden -------------------------------------------------------------------

def _mit(aenderung) -> dict:
    daten = copy.deepcopy(_roh())
    aenderung(daten["leistungen"][0])
    return daten


@pytest.mark.parametrize("aenderung", [
    lambda l: l.update(formular="GIBT_ES_NICHT"),
    lambda l: l.update(rueckfragen=["person.lieblingsfarbe"]),
    lambda l: l.update(rueckfragen=["bank.iban"]),  # sensibel
    lambda l: l["kurz"].pop("en"),
    lambda l: l.update(regionen=["Bayern"]),
    lambda l: l.update(quellen=[]),
    lambda l: l["quellen"].append({"art": "extern", "titel": "Web", "url": "https://example.org"}),  # beleg bleibt „lokal“
    lambda l: l["stelle_nach"]["versicherung.pension"].update({"AUVA": {"de": "x", "en": "x"}}),
    lambda l: l.update(schritte=[s for s in l["schritte"] if s["id"] != "antrag_unterschreiben"]),
], ids=["formular", "slot", "sensibler_slot", "ohne_en", "region", "ohne_quelle", "extern_bei_lokal", "slot_option", "antragsschritt"])
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


@pytest.mark.parametrize("text", [
    "Ich bin die Tochter und kümmere mich um meinen Vater, der allein nicht mehr zurechtkommt.",
    "Meine Tochter und ich pflegen meine Mutter zu Hause.",
    "Als Sohn möchte ich Pflegegeld für meine Mutter beantragen.",
    "I am her daughter and I look after my father.",
])
def test_tochter_als_helfende_person_loest_kein_kind_szenario_aus(text):
    szenarien = katalog.erkenne_szenarien(text)
    assert "kind" not in szenarien
    assert szenarien[0] == "pflege"


def test_tochter_mit_altersangabe_ist_kind_szenario():
    assert katalog.erkenne_szenarien("Meine Tochter ist 4 Jahre alt, gibt es Angebote?") == ["kind"]
    assert katalog.erkenne_szenarien("My little son is 2 – what is available?") == ["kind"]


def test_mehrere_szenarien_nach_staerke_sortiert_und_leertext():
    szenarien = katalog.erkenne_szenarien("Ich wurde aus dem Spital entlassen und brauche Reha; außerdem habe ich ein Baby.")
    assert szenarien[:2] == ["entlassung", "kind"]
    assert katalog.erkenne_szenarien("") == []
    assert katalog.erkenne_szenarien("Wie spät ist es?") == []


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
    for l in katalog.alle():
        for q in l.quellen:
            if q.art == "extern":
                continue
            assert config.datei(q.datei).is_file(), q.datei
            if _kern(q.zitat) not in _quelltext(q.datei, q.fundstelle):
                fehlend.append((l.id, q.titel, q.fundstelle, q.zitat[:60]))
    assert not fehlend, fehlend


@pytest.mark.daten
def test_rechtsquellen_stand_und_bgbl_passen_zur_datei():
    for l in katalog.alle():
        for q in l.quellen:
            if q.art != "recht":
                continue
            *_, inkraft = q.datei.removesuffix(".xml").split("=")
            assert q.stand == ("" if inkraft.startswith("1111") else inkraft), q.datei
            pub = next(ET.parse(config.datei(q.datei)).getroot().iter("puborgan")).attrib
            assert f"Nr. {pub['nrpuborg']}/{pub['jahrgang']}" in q.fundstelle, q.datei
