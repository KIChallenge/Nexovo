"""Erstattungskodex: Satzformat, Invarianten Box/Regeltext/IND, Legendenwortlaut, keine Empfehlungssprache."""

from __future__ import annotations

import re

import pytest

from lotse import config, ekodex, pdfquellen
from lotse.models import Quelle

# Empfehlungs-, Therapie- und Dosierungssprache darf in Erklärungen nie vorkommen
_EMPFEHLUNG = re.compile(
    r"empfehl|empfiehl|sollten|nehmen sie|einnehmen|dosis|dosier|therapievorschlag|geeignet|"
    r"recommend|should|\btake\b|\bdose|dosage|suitable|advis",
    re.IGNORECASE,
)


@pytest.fixture(scope="module")
def kodex() -> ekodex.Erstattungskodex:
    return ekodex.lade()


def _rohzeilen(rel: str) -> list[str]:
    with open(config.datei(rel), encoding="cp1252", newline="") as f:
        return [z for z in f.read().split("\r\n") if z]


# -- Format und Invarianten ----------------------------------------------------------------------------------


@pytest.mark.daten
def test_alle_saetze_gelesen_pzn_eindeutig(kodex):
    assert len(kodex) == 6985
    pzns = [e.pzn for e in kodex.eintraege]
    assert len(set(pzns)) == 6985 and all(re.fullmatch(r"\d{7}", p) for p in pzns)
    assert {e.box for e in kodex.eintraege} == {"gruen", "gelb"}


@pytest.mark.daten
def test_box_gelb_genau_bei_regeltext(kodex):
    gelb = {e.pzn for e in kodex.eintraege if e.box == "gelb"}
    mit_regel = {e.pzn for e in kodex.eintraege if e.regeltext}
    assert gelb == mit_regel
    assert len(gelb) == 1330
    re1 = sum(1 for e in kodex.eintraege if "RE1" in e.kennzeichen)
    re2 = sum(1 for e in kodex.eintraege if "RE2" in e.kennzeichen)
    assert (re1, re2) == (856, 474)


@pytest.mark.daten
def test_kennzeichen_ind_genau_bei_indikationstext(kodex):
    ind = {e.pzn for e in kodex.eintraege if "IND" in e.kennzeichen}
    mit_text = {e.pzn for e in kodex.eintraege if e.indtext}
    assert ind == mit_text
    assert len(ind) == 1269


@pytest.mark.daten
def test_bekannte_pzn_box_kennzeichen_packung(kodex):
    e = kodex.pzn("0003582")
    assert (e.box, e.kennzeichen, e.packung) == ("gruen", ["IND"], "100St")
    assert e.name.startswith("Aprednislon 5 mg")
    assert e.quelle.art == "ekodex" and e.quelle.datei == ekodex.MEDIKAMENT
    assert e.quelle.fundstelle.startswith("medikament.txt, Zeile ") and "0003582" in e.quelle.fundstelle
    g = kodex.pzn("1278128")
    assert (g.box, g.kennzeichen) == ("gelb", ["RE1"])
    assert kodex.pzn("87076").kennzeichen == ["RE2"]  # führende Nullen dürfen fehlen
    mehrere = [e for e in kodex.eintraege if len(e.kennzeichen) > 1]
    assert any(e.kennzeichen == ["N", "P"] for e in mehrere)


@pytest.mark.daten
def test_regeltext_mit_semikolon_vollstaendig(kodex):
    roh = {z[1:8]: z for z in _rohzeilen(ekodex.REGELTEXT)}
    mit_semikolon = [p for p, z in roh.items() if z.count(";") > 1]
    assert len(mit_semikolon) == 78
    for pzn in mit_semikolon:
        text = kodex.pzn(pzn).regeltext
        assert text.count(";") == roh[pzn].count(";") - 1  # nur das Trennzeichen fällt weg
        assert text.endswith(" ".join(roh[pzn][11:-1].split())[-40:])
    assert kodex.pzn("1278128").regeltext.endswith("bzw. -ambulanz.")


@pytest.mark.daten
def test_indtext_mit_semikolon_vollstaendig(kodex):
    roh = {z[1:8]: z for z in _rohzeilen(ekodex.INDTEXT)}
    for pzn, zeile in roh.items():
        if zeile.count(";") > 1:
            assert kodex.pzn(pzn).indtext.count(";") == zeile.count(";") - 1


# -- Suche ---------------------------------------------------------------------------------------------------


@pytest.mark.daten
def test_suche_pzn_exakt_und_name(kodex):
    assert [e.pzn for e in kodex.suche("0003582")] == ["0003582"]
    assert [e.pzn for e in kodex.suche("3582")] == ["0003582"]
    assert kodex.suche("9999999") == []
    anfang = kodex.suche("aprednislon", k=10)
    assert anfang and all(e.name.casefold().startswith("aprednislon") for e in anfang)
    teil = kodex.suche("SALBE", k=3)
    assert len(teil) == 3 and all("salbe" in e.name.casefold() for e in teil)
    assert kodex.suche("   ") == []


def test_parse_zeile_feste_spalten():
    zeile = "1234567  000001   " + "Testpräparat 5 mg Tabl.".ljust(100) + "Y  RE2   20St     1740       872"
    assert ekodex.parse_zeile(zeile) == ("1234567", "Testpräparat 5 mg Tabl.", "gelb", ["RE2"], "20St")
    zeile = "7654321  000002   " + "Test Salbe".ljust(100) + "G  N P   30g       490       165"
    assert ekodex.parse_zeile(zeile)[2:] == ("gruen", ["N", "P"], "30g")
    with pytest.raises(ValueError):
        ekodex.parse_zeile("ABCDEFG  000002   " + "x".ljust(100) + "G  30g")


# -- Erklärung laut Legende ----------------------------------------------------------------------------------


@pytest.mark.daten
def test_legendenwortlaut_steht_woertlich_in_der_pdf():
    seiten = pdfquellen.lade_seiten(pdfquellen.LEGENDE)
    assert len(seiten) == 5
    for eintrag in ekodex.legenden_eintraege():
        assert " ".join(eintrag.de.split()) in seiten[eintrag.seite - 1], eintrag.de[:60]


@pytest.mark.daten
def test_erklaerung_administrativ_ohne_empfehlung(kodex):
    kombinationen = {(e.box, tuple(e.kennzeichen)): e for e in kodex.eintraege}
    assert len(kombinationen) >= 20
    for e in kombinationen.values():
        for sprache in ("de", "en"):
            text = e.erklaerung(sprache)
            assert not _EMPFEHLUNG.search(text), (e.pzn, sprache, _EMPFEHLUNG.search(text).group())
            assert ("PDF-S." if sprache == "de" else "PDF p.") in text
    gelb = kodex.pzn("1278128").erklaerung("de")
    assert "Gelber Bereich des EKO" in gelb and "chef- und kontrollärztlichen Dienstes" in gelb
    assert "RE1:" in gelb and "PDF-S. 3" in gelb


@pytest.mark.daten
def test_erklaerung_quellen_verweisen_auf_legendenseiten(kodex):
    e = kodex.pzn("0003582")
    quellen = e.quellen()
    legende = [q for q in quellen if q.datei == pdfquellen.LEGENDE]
    assert [q.fundstelle for q in legende] == ["PDF-S. 2"]  # G und IND stehen beide auf S. 2
    assert all(isinstance(q, Quelle) and len(q.zitat) <= 300 for q in quellen)
    assert e.ind_quelle is not None and e.ind_quelle.fundstelle.startswith("indtext.txt, Zeile ")


@pytest.mark.daten
def test_unbekanntes_kennzeichen_wird_nicht_erfunden(kodex):
    e = next(e for e in kodex.eintraege if "DSX" in e.kennzeichen)
    assert "DSX: Kennzeichen in der lokalen Zeichenerklärung nicht erläutert." in e.erklaerung("de")
    assert "DSX: code not explained in the local EKO legend." in e.erklaerung("en")


@pytest.mark.daten
def test_gruener_bereich_mit_rechtsgrundlage_aus_wissensbasis():
    from lotse import wissen

    e = wissen.wissensbasis().ekodex("0003582")[0]
    assert e.recht and all(q.art == "recht" and q.titel.endswith("§ 5") for q in e.recht)
    gesamt = " ".join(q.zitat for q in e.recht)
    assert "ohne ärztliche Bewilligung des chef- oder kontrollärztlichen Dienstes" in gesamt
    assert gesamt.endswith("beachtet worden ist.")
    assert all(len(q.zitat) <= 300 for q in e.recht)
    assert "German original" in e.erklaerung("en")
    assert wissen.wissensbasis().ekodex("1278128")[0].recht == ()
